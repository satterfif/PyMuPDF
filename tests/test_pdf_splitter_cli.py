import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "pdf_splitter_cli.py"
SPEC = importlib.util.spec_from_file_location("pdf_splitter_cli", SCRIPT_PATH)
pdf_splitter_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pdf_splitter_cli)


def make_pdf(path, page_count=3):
    with pymupdf.open() as document:
        for page_number in range(1, page_count + 1):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {page_number}")
        document.save(path)


def test_split_pdf_creates_pages_subfolder(tmp_path):
    input_path = tmp_path / "Quarterly Report.pdf"
    make_pdf(input_path)

    output_paths = pdf_splitter_cli.split_pdf(input_path)

    expected_dir = tmp_path / "Quarterly Report" / "pages"
    assert expected_dir.is_dir()
    assert [path.name for path in output_paths] == [
        "page_001.pdf",
        "page_002.pdf",
        "page_003.pdf",
    ]
    assert output_paths[0].parent == expected_dir
    for page_number, output_path in enumerate(output_paths, 1):
        with pymupdf.open(output_path) as split_document:
            assert split_document.page_count == 1
            assert f"Page {page_number}" in split_document[0].get_text()


def test_split_pdf_accepts_an_explicit_existing_output_folder(tmp_path):
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    make_pdf(input_path, page_count=1)

    output_paths = pdf_splitter_cli.split_pdf(input_path, output_dir)

    assert output_paths == [output_dir / "page_001.pdf"]


def test_split_pdf_auto_creates_output_folder(tmp_path):
    input_path = tmp_path / "input.pdf"
    expected_dir = tmp_path / "input" / "pages"
    make_pdf(input_path, page_count=1)

    output_paths = pdf_splitter_cli.split_pdf(input_path)

    assert expected_dir.is_dir()
    assert len(output_paths) == 1
    assert output_paths[0].parent == expected_dir


def test_split_pdf_rejects_a_non_pdf_input(tmp_path):
    input_path = tmp_path / "notes.txt"
    input_path.write_text("not a PDF", encoding="utf-8")
    (tmp_path / "notes").mkdir()

    with pytest.raises(pdf_splitter_cli.SplitterError, match="must be a PDF"):
        pdf_splitter_cli.split_pdf(input_path)


def test_auto_creates_explicit_nested_folder(tmp_path):
    input_path = tmp_path / "input.pdf"
    make_pdf(input_path, page_count=1)
    output_dir = tmp_path / "deep" / "nested" / "output"

    output_paths = pdf_splitter_cli.split_pdf(input_path, output_dir)

    assert output_dir.is_dir()
    assert len(output_paths) == 1


# --pages flag tests

def test_pages_extracts_single_page(tmp_path):
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    make_pdf(input_path, page_count=5)

    output_paths = pdf_splitter_cli.split_pdf(input_path, output_dir, pages="3")

    assert len(output_paths) == 1
    assert output_paths[0].name == "input_pages.pdf"
    with pymupdf.open(output_paths[0]) as doc:
        assert doc.page_count == 1
        assert "Page 3" in doc[0].get_text()


def test_pages_extracts_range(tmp_path):
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    make_pdf(input_path, page_count=10)

    output_paths = pdf_splitter_cli.split_pdf(input_path, output_dir, pages="2-4, 7")

    assert len(output_paths) == 1
    with pymupdf.open(output_paths[0]) as doc:
        assert doc.page_count == 4
        assert "Page 2" in doc[0].get_text()
        assert "Page 3" in doc[1].get_text()
        assert "Page 4" in doc[2].get_text()
        assert "Page 7" in doc[3].get_text()


def test_pages_rejects_out_of_range(tmp_path):
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    make_pdf(input_path, page_count=3)

    with pytest.raises(pdf_splitter_cli.SplitterError, match="out of range"):
        pdf_splitter_cli.split_pdf(input_path, output_dir, pages="5")


def test_pages_rejects_invalid_spec(tmp_path):
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    make_pdf(input_path, page_count=3)

    with pytest.raises(pdf_splitter_cli.SplitterError, match="Invalid page specification"):
        pdf_splitter_cli.split_pdf(input_path, output_dir, pages="abc")


# --json flag tests

def test_json_output_on_success(tmp_path, capsys):
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "input"
    output_dir.mkdir()
    make_pdf(input_path, page_count=2)

    exit_code = pdf_splitter_cli.main([
        str(input_path), "--output-dir", str(output_dir), "--json"
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "ok"
    assert result["pages"] == 2
    assert len(result["files"]) == 2
    assert result["output_dir"] == str(output_dir)


def test_json_output_on_error(tmp_path, capsys):
    input_path = tmp_path / "nonexistent.pdf"

    exit_code = pdf_splitter_cli.main([str(input_path), "--json"])

    assert exit_code == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "does not exist" in result["message"]


# Combined flags

def test_pages_with_json_and_auto_mkdir(tmp_path, capsys):
    input_path = tmp_path / "report.pdf"
    make_pdf(input_path, page_count=5)

    exit_code = pdf_splitter_cli.main([
        str(input_path), "--pages", "1-3", "--json"
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "ok"
    assert result["pages"] == 1  # one output file
    assert "report_pages.pdf" in result["files"][0]

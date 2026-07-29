import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "ocr_merge_cli.py"
SPEC = importlib.util.spec_from_file_location("ocr_merge_cli", SCRIPT_PATH)
ocr_merge_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ocr_merge_cli)


# --- helpers ----------------------------------------------------------------

def make_image_pdf(path, width=612, height=792):
    """A single-page PDF with a drawing but no text layer (image-only stand-in)."""
    with pymupdf.open() as document:
        page = document.new_page(width=width, height=height)
        # A filled rectangle stands in for a scanned image: visible, no text.
        page.draw_rect(pymupdf.Rect(50, 50, width - 50, height - 50),
                       color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
        document.save(path)


def make_text_pdf(path):
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "This page already has text")
        document.save(path)


def ocr_json(lines):
    """Build minimal Dynamics/Azure-shaped OCR JSON from (text, box) tuples."""
    return [{
        "page": 1,
        "lines": [
            {
                "text": text,
                "boundingBox": {
                    "left": box[0], "top": box[1],
                    "width": box[2], "height": box[3],
                },
            }
            for text, box in lines
        ],
    }]


def write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


SAMPLE_LINES = [
    ("Customer Name", (0.02, 0.012, 0.13, 0.014)),
    ("Abnahmeprüfzeugnis", (0.30, 0.10, 0.25, 0.02)),
    ("Österreich", (0.10, 0.50, 0.15, 0.02)),
]


# --- U1: schema adapter -----------------------------------------------------

def test_parse_returns_record_per_nonempty_line():
    data = ocr_json(SAMPLE_LINES)
    lines = ocr_merge_cli.parse_ocr_lines(data)
    assert len(lines) == 3
    assert lines[0].text == "Customer Name"
    assert lines[0].left == pytest.approx(0.02)
    assert lines[0].height == pytest.approx(0.014)


def test_parse_skips_empty_and_whitespace_lines():
    data = ocr_json([
        ("Real text", (0.0, 0.0, 0.2, 0.02)),
        ("", (0.0, 0.1, 0.2, 0.02)),
        ("   ", (0.0, 0.2, 0.2, 0.02)),
    ])
    lines = ocr_merge_cli.parse_ocr_lines(data)
    assert len(lines) == 1
    assert lines[0].text == "Real text"


def test_parse_retains_garbled_text_verbatim():
    data = ocr_json([("Salte / page", (0.0, 0.0, 0.2, 0.02))])
    lines = ocr_merge_cli.parse_ocr_lines(data)
    assert lines[0].text == "Salte / page"


def test_parse_rejects_non_array_top_level():
    with pytest.raises(ocr_merge_cli.OcrMergeError, match="top-level array"):
        ocr_merge_cli.parse_ocr_lines({"lines": []})


def test_parse_rejects_missing_lines_key():
    with pytest.raises(ocr_merge_cli.OcrMergeError, match="no 'lines'"):
        ocr_merge_cli.parse_ocr_lines([{"page": 1}])


def test_parse_rejects_out_of_range_coordinate():
    data = ocr_json([("x", (5.0, 0.0, 0.2, 0.02))])
    with pytest.raises(ocr_merge_cli.OcrMergeError, match="outside"):
        ocr_merge_cli.parse_ocr_lines(data)


def test_parse_rejects_line_missing_boundingbox():
    data = [{"lines": [{"text": "no box here"}]}]
    with pytest.raises(ocr_merge_cli.OcrMergeError, match="no boundingBox"):
        ocr_merge_cli.parse_ocr_lines(data)


def test_parse_allows_slightly_negative_rounding():
    data = ocr_json([("x", (-0.001, 0.0, 0.2, 0.02))])
    lines = ocr_merge_cli.parse_ocr_lines(data)
    assert len(lines) == 1


# --- U2: coordinate mapping and width-fit -----------------------------------

@pytest.fixture(scope="module")
def font():
    return pymupdf.Font(fontfile=ocr_merge_cli.resolve_font_path())


def test_placement_maps_top_left_near_page_top(font):
    line = ocr_merge_cli.OcrLine("Hi", 0.0, 0.0, 0.2, 0.02)
    placement = ocr_merge_cli.compute_placement(line, 612, 792, font)
    # baseline y = (top + height) * page_height, near the very top of the page
    assert placement.baseline_point.y == pytest.approx(0.02 * 792)


def test_placement_maps_bottom_near_page_bottom(font):
    line = ocr_merge_cli.OcrLine("Hi", 0.0, 0.99, 0.2, 0.005)
    placement = ocr_merge_cli.compute_placement(line, 612, 792, font)
    assert placement.baseline_point.y == pytest.approx((0.99 + 0.005) * 792)


def test_placement_x_scales_with_page_width(font):
    line = ocr_merge_cli.OcrLine("Hi", 0.5, 0.5, 0.2, 0.02)
    narrow = ocr_merge_cli.compute_placement(line, 300, 792, font)
    wide = ocr_merge_cli.compute_placement(line, 600, 792, font)
    # baseline x = left * page_width (morph pivots on it, no pre-divide).
    assert narrow.baseline_point.x == pytest.approx(0.5 * 300)
    assert wide.baseline_point.x == pytest.approx(0.5 * 600)


def test_hscale_stretches_short_line(font):
    # A short string in a wide box should scale up (>1).
    line = ocr_merge_cli.OcrLine("ab", 0.0, 0.0, 0.9, 0.02)
    placement = ocr_merge_cli.compute_placement(line, 612, 792, font)
    assert placement.h_scale > 1.0


def test_hscale_compresses_long_line(font):
    # A long string in a narrow box should scale down (<1).
    line = ocr_merge_cli.OcrLine("a very long line of text " * 3, 0.0, 0.0, 0.05, 0.02)
    placement = ocr_merge_cli.compute_placement(line, 612, 792, font)
    assert placement.h_scale < 1.0


def test_hscale_clamped_for_degenerate_box(font):
    line = ocr_merge_cli.OcrLine("x", 0.0, 0.0, 0.0, 0.02)
    placement = ocr_merge_cli.compute_placement(line, 612, 792, font)
    assert ocr_merge_cli._MIN_HSCALE <= placement.h_scale <= ocr_merge_cli._MAX_HSCALE


# --- U3 + U4: end-to-end merge ----------------------------------------------

def test_merge_produces_searchable_pdf(tmp_path):
    pdf = tmp_path / "page_005.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "page_005.json"
    write_json(js, ocr_json(SAMPLE_LINES))

    out = ocr_merge_cli.merge_ocr(pdf, js)

    assert out == tmp_path / "final_page_005.pdf"
    with pymupdf.open(out) as doc:
        # Embedded-font extraction renders spaces as U+00A0; normalize for the
        # copy-fidelity check. Search is the authoritative searchability contract.
        text = doc[0].get_text().replace("\xa0", " ")
        assert "Customer Name" in text
        assert doc[0].search_for("Customer Name")
        # A Unicode TTF must be embedded (not base-14) so non-ASCII survives.
        assert doc[0].get_fonts(), "expected an embedded font"


def test_merge_roundtrips_non_ascii(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "p.json"
    write_json(js, ocr_json([("Österreich", (0.1, 0.5, 0.15, 0.02))]))

    out = ocr_merge_cli.merge_ocr(pdf, js)
    with pymupdf.open(out) as doc:
        assert "Österreich" in doc[0].get_text()


def test_merge_preserves_image_pixels(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "p.json"
    write_json(js, ocr_json(SAMPLE_LINES))

    with pymupdf.open(pdf) as before_doc:
        before = before_doc[0].get_pixmap().tobytes()

    out = ocr_merge_cli.merge_ocr(pdf, js)
    with pymupdf.open(out) as after_doc:
        after = after_doc[0].get_pixmap().tobytes()

    # Invisible text (render mode 3) must not change any rendered pixel.
    assert before == after


def test_merge_places_text_near_source_box(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_image_pdf(pdf, width=612, height=792)
    js = tmp_path / "p.json"
    write_json(js, ocr_json([("Heat Number", (0.1, 0.2, 0.2, 0.02))]))

    out = ocr_merge_cli.merge_ocr(pdf, js)
    with pymupdf.open(out) as doc:
        words = doc[0].get_text("words")
    assert words, "expected placed words"
    # x0 of the first word should land near left * page_width (0.1 * 612 ~ 61).
    x0 = min(w[0] for w in words)
    assert x0 == pytest.approx(0.1 * 612, abs=15)


def test_merge_handles_many_lines(tmp_path):
    pdf = tmp_path / "page_005.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "page_005.json"
    many = [(f"line {i}", (0.05, 0.01 + i * 0.008, 0.3, 0.006)) for i in range(100)]
    write_json(js, ocr_json(many))

    out = ocr_merge_cli.merge_ocr(pdf, js)
    with pymupdf.open(out) as doc:
        page = doc[0]
        text = page.get_text().replace("\xa0", " ")
    assert "line 0" in text
    assert "line 99" in text


# --- U4: failure behavior ---------------------------------------------------

def test_merge_rejects_pdf_with_existing_text_layer(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_text_pdf(pdf)
    js = tmp_path / "p.json"
    write_json(js, ocr_json(SAMPLE_LINES))

    with pytest.raises(ocr_merge_cli.OcrMergeError, match="already contains a text layer"):
        ocr_merge_cli.merge_ocr(pdf, js)
    assert not (tmp_path / "final_p.pdf").exists()


def test_merge_rejects_bad_json(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "p.json"
    js.write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(ocr_merge_cli.OcrMergeError, match="Could not read OCR JSON"):
        ocr_merge_cli.merge_ocr(pdf, js)
    assert not (tmp_path / "final_p.pdf").exists()


def test_merge_rejects_out_of_range_coords_no_output(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "p.json"
    write_json(js, ocr_json([("x", (5.0, 0.0, 0.2, 0.02))]))

    with pytest.raises(ocr_merge_cli.OcrMergeError, match="outside"):
        ocr_merge_cli.merge_ocr(pdf, js)
    assert not (tmp_path / "final_p.pdf").exists()


def test_merge_rejects_missing_pdf(tmp_path):
    js = tmp_path / "p.json"
    write_json(js, ocr_json(SAMPLE_LINES))
    with pytest.raises(ocr_merge_cli.OcrMergeError, match="does not exist"):
        ocr_merge_cli.merge_ocr(tmp_path / "nope.pdf", js)


def test_merge_rejects_non_pdf_input(tmp_path):
    notpdf = tmp_path / "notes.txt"
    notpdf.write_text("hi", encoding="utf-8")
    js = tmp_path / "p.json"
    write_json(js, ocr_json(SAMPLE_LINES))
    with pytest.raises(ocr_merge_cli.OcrMergeError, match="must be a PDF"):
        ocr_merge_cli.merge_ocr(notpdf, js)


# --- U4: CLI wiring ---------------------------------------------------------

def test_main_success_exit_zero(tmp_path, capsys):
    pdf = tmp_path / "page_005.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "page_005.json"
    write_json(js, ocr_json(SAMPLE_LINES))

    exit_code = ocr_merge_cli.main([str(pdf), str(js)])

    assert exit_code == 0
    assert (tmp_path / "final_page_005.pdf").exists()
    assert "Wrote searchable PDF" in capsys.readouterr().out


def test_main_structural_error_exit_one(tmp_path, capsys):
    pdf = tmp_path / "p.pdf"
    make_text_pdf(pdf)
    js = tmp_path / "p.json"
    write_json(js, ocr_json(SAMPLE_LINES))

    exit_code = ocr_merge_cli.main([str(pdf), str(js)])

    assert exit_code == 1
    assert "OCR merge failed" in capsys.readouterr().err
    assert not (tmp_path / "final_p.pdf").exists()


def test_main_custom_output_dir(tmp_path):
    pdf = tmp_path / "p.pdf"
    make_image_pdf(pdf)
    js = tmp_path / "p.json"
    write_json(js, ocr_json(SAMPLE_LINES))
    outdir = tmp_path / "out"

    exit_code = ocr_merge_cli.main([str(pdf), str(js), "--output-dir", str(outdir)])

    assert exit_code == 0
    assert (outdir / "final_p.pdf").exists()

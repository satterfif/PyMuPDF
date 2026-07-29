# Reference: PDF Splitter CLI

`scripts/pdf_splitter_cli.py` splits one PDF into one single-page PDF per source page, or extracts a chosen page range into a single file. It emits plain text by default and structured JSON with `--json`, for automation such as Power Automate Desktop. It is a standalone tool, not part of the built `pymupdf` wheel.

## Invocation

```bash
python scripts/pdf_splitter_cli.py <input_pdf> [--output-dir DIR] [--pages RANGE] [--json]
```

## Arguments

| Argument | Type | Default | Effect |
|----------|------|---------|--------|
| `input_pdf` | path (positional, required) | — | The source PDF. Must exist and have a `.pdf` suffix. |
| `--output-dir DIR` | path | `<input-without-.pdf>/pages` | Folder for the output files. Created automatically (including parents) if absent. |
| `--pages RANGE` | string | unset | Extract only these pages into one file instead of splitting every page. See "Page ranges" below. |
| `--json` | flag | off | Emit a JSON result object to stdout instead of a human line. |

## Behavior

**Split mode (no `--pages`).** Writes one file per page, named `page_NNN.pdf`, zero-padded to at least 3 digits (wider when the page count needs it — e.g. a 1000-page PDF uses `page_0001.pdf`). Default output folder is a `pages/` subfolder beside a folder named after the input: `Report.pdf` → `Report/pages/page_001.pdf`.

**Extract mode (`--pages`).** Writes a single file named `<stem>_pages.pdf` containing the selected pages in the order the range specifies.

Writes are atomic: each file is written to a temp name and then `os.replace`d into place, so an interrupted run never leaves a partial `page_NNN.pdf`.

## Page ranges

`--pages` accepts comma-separated tokens. Each token is either a single 1-based page number or an inclusive `start-end` range:

```
--pages "1-5, 8, 10-15"
```

Rules:
- Page numbers are 1-based.
- A range's `start` must be ≥ 1, `end` must be ≤ the document's page count, and `start ≤ end`.
- An out-of-range page, a reversed range, or a non-numeric token raises `SplitterError`.

## Parallelism

Splitting is I/O-bound (each page is opened, copied, saved). For documents with **50 or more pages** (`_PARALLEL_THRESHOLD`), the splitter uses a `ThreadPoolExecutor` capped at `min(8, cpu_count)` workers (`_MAX_WORKERS`); each worker opens its own document handle. Below the threshold it runs sequentially — the per-thread doc-open cost outweighs the benefit on small PDFs. This threaded path is the documented exception to PyMuPDF's "no multithreading" rule (see [explanation-design.md](explanation-design.md)).

## Exit codes and errors

| Exit | Meaning |
|------|---------|
| `0` | Success. |
| `1` | A `SplitterError` (bad input, out-of-range pages, write failure). |

`SplitterError` is raised for: a missing input file, a non-`.pdf` input, a password-protected PDF, a zero-page PDF, an invalid `--pages` spec, or a per-page write failure.

## JSON output (`--json`)

Success:

```json
{
  "status": "ok",
  "input": "C:\\Documents\\Report.pdf",
  "pages": 3,
  "output_dir": "C:\\Documents\\Report\\pages",
  "files": ["...page_001.pdf", "...page_002.pdf", "...page_003.pdf"]
}
```

`pages` is the count of output **files** (so it is `1` in `--pages` extract mode). Error:

```json
{ "status": "error", "message": "Page 5 out of range: document has 3 pages" }
```

With `--json`, errors are still reported on stdout as JSON and the process exits `1`.

## Public functions (for importers, e.g. the GUI)

- `split_pdf(input_path, output_dir=None, pages=None) -> list[Path]` — the core entry point. Returns the list of output paths. Raises `SplitterError`.
- `parse_page_ranges(spec, page_count) -> list[int]` — parses a `--pages` string into 0-based indices.
- `SplitterError` — the user-facing error type.
- `main(argv=None) -> int` — the CLI entry; returns the exit code.

## Examples

```bash
# Split every page into <input>/pages/
python scripts/pdf_splitter_cli.py "Invoices.pdf"

# Extract pages 1-3 and 7 into one Report_pages.pdf, in a chosen folder
python scripts/pdf_splitter_cli.py "Report.pdf" --pages "1-3, 7" --output-dir "C:/Out"

# Machine-readable result for automation
python scripts/pdf_splitter_cli.py "Invoices.pdf" --json
```

## Related

- [How to split a PDF](howto-split-pdf.md)
- [Tutorial: from scanned PDF to searchable PDF](tutorial-scan-to-searchable.md)
- [Reference: OCR Merge CLI](reference-ocr-merge-cli.md)
- Tests: `tests/test_pdf_splitter_cli.py`

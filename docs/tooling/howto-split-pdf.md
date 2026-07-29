# How to split a PDF into pages

Split one PDF into a folder of single-page PDFs, or pull a chosen page range into a single file.

## Prerequisites

- Python 3.10+ with `pymupdf` importable (`python -c "import pymupdf"`).
- The repo checked out; run commands from the repo root.

## Split every page into its own file

1. Run the splitter with just the input PDF:

   ```bash
   python scripts/pdf_splitter_cli.py "Invoices.pdf"
   ```

2. Find the output in a `pages/` subfolder named after the input:

   ```
   Invoices/pages/page_001.pdf
   Invoices/pages/page_002.pdf
   ...
   ```

   Files are `page_NNN.pdf`, zero-padded to at least 3 digits.

## Send output to a specific folder

```bash
python scripts/pdf_splitter_cli.py "Invoices.pdf" --output-dir "C:/Output"
```

The folder is created (with parents) if it doesn't exist.

## Extract a page range into one file

To pull specific pages into a single PDF instead of splitting every page:

```bash
python scripts/pdf_splitter_cli.py "Report.pdf" --pages "1-5, 8, 10-15"
```

This writes one file, `Report_pages.pdf`, containing pages 1–5, 8, and 10–15 in that order. Page numbers are 1-based; ranges are inclusive.

## Get a machine-readable result

For automation, add `--json` to print a result object instead of a text line:

```bash
python scripts/pdf_splitter_cli.py "Invoices.pdf" --json
```

```json
{ "status": "ok", "input": "...Invoices.pdf", "pages": 12, "output_dir": "...", "files": ["..."] }
```

## Verification

Confirm the output count matches the page count:

```bash
python scripts/pdf_splitter_cli.py "Invoices.pdf" --json
# read "pages": N and check that N files exist in output_dir
```

Or open a couple of the `page_NNN.pdf` files and confirm each has exactly one page.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Input PDF does not exist` | Wrong path. | Check the path; quote paths with spaces. |
| `Input file must be a PDF` | Input isn't `.pdf`. | Point at a real PDF. |
| `Password-protected PDF is not supported` | The PDF is encrypted. | Remove the password first, then split. |
| `Invalid page range '...'` / `out of range` | `--pages` names a page beyond the document, a reversed range, or a non-number. | Use 1-based numbers within the page count, `start ≤ end`. |
| Slow on a huge PDF | Expected below 50 pages (sequential). | At 50+ pages it threads automatically; nothing to configure. |

## Related

- [Reference: PDF Splitter CLI](reference-pdf-splitter-cli.md) — every flag and its behavior
- [How to make an image PDF searchable](howto-make-searchable.md)
- [How to run the splitter GUI and Power Automate](howto-gui-and-automation.md)

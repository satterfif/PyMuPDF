# PDF Automation Tooling

Standalone command-line tools in `scripts/` for splitting PDFs and making scanned pages searchable. These are separate from the core `pymupdf` binding — they build on it but are not part of the built wheel. See [../../CLAUDE.md](../../CLAUDE.md) for how they fit the repo.

## What's here

- **PDF Splitter CLI** (`scripts/pdf_splitter_cli.py`) — split a PDF into one file per page, or extract a page range; emits JSON for automation.
- **OCR Merge CLI** (`scripts/ocr_merge_cli.py`) — overlay existing OCR results onto an image-only PDF page to make it searchable.
- **Splitter GUI** (`scripts/pdf_splitter_gui.py`) — a local Flask app for hand-testing the splitter.
- **Portable exe** (`release/PDFSplitter-Portable/`) — a PyInstaller build for Power Automate Desktop.

## Start here

**First time here?** Open the self-contained HTML guide — no setup, opens in any browser:

- [Getting Started guide (HTML)](getting-started.html)

**Prefer a step-by-step walkthrough?** Follow the tutorial end to end:

- [Tutorial: from a scanned PDF to searchable pages](tutorial-scan-to-searchable.md)

## Documentation map

The docs follow the [Diataxis](https://diataxis.fr/) framework — pick by what you need right now.

| I want to… | Read |
|------------|------|
| Learn the whole flow from scratch | [Tutorial: scan to searchable](tutorial-scan-to-searchable.md) |
| Split a PDF into pages | [How to split a PDF](howto-split-pdf.md) |
| Make an image PDF searchable | [How to make an image PDF searchable](howto-make-searchable.md) |
| Run the GUI or wire up Power Automate | [How to run the GUI and Power Automate](howto-gui-and-automation.md) |
| Look up every splitter flag | [Reference: PDF Splitter CLI](reference-pdf-splitter-cli.md) |
| Look up the OCR merge schema and flags | [Reference: OCR Merge CLI](reference-ocr-merge-cli.md) |
| Understand *why* it's built this way | [Explanation: design decisions](explanation-design.md) |

## Tests

- `tests/test_pdf_splitter_cli.py`
- `tests/test_ocr_merge_cli.py`

Run them with the repo's Python 3.12 environment, e.g. `pytest tests/test_ocr_merge_cli.py`.

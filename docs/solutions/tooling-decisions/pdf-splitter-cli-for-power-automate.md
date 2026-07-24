---
title: PDF Splitter CLI for Power Automate Desktop
date: 2026-07-24
category: tooling-decisions
module: pdf-splitter
problem_type: tooling_decision
component: tooling
severity: medium
applies_when:
  - Splitting multi-page PDFs into individual pages in automation workflows
  - Integrating PDF processing with Power Automate Desktop flows
  - Needing a portable CLI tool that outputs structured JSON for orchestrators
tags: [pdf, splitter, power-automate, cli, pymupdf, pyinstaller, flask]
---

# PDF Splitter CLI for Power Automate Desktop

## Context

Power Automate Desktop workflows needed a portable executable for splitting PDFs into individual pages — similar to the existing AutoPDFRotate-CLI.exe pattern. The built-in Power Automate PDF actions support page extraction by range but lack one-page-per-file splitting with structured output. A standalone CLI tool that auto-creates output directories, reports results as JSON, and exits with meaningful codes integrates cleanly with the "Run application and wait" action pattern.

## Guidance

### Architecture

The tool is structured as three layers:

| Layer | File | Role |
|-------|------|------|
| Core CLI | `scripts/pdf_splitter_cli.py` | Argparse + PyMuPDF split logic |
| Testing GUI | `scripts/pdf_splitter_gui.py` | Flask web UI with upload + job polling |
| Portable exe | `release/PDFSplitter-Portable/PDFSplitter-CLI.exe` | PyInstaller one-file build |

### Output Convention

```
Input:  Invoices.pdf
Output: Invoices/pages/page_001.pdf
        Invoices/pages/page_002.pdf
        Invoices/pages/page_003.pdf
```

The output folder (`{input_stem}/pages/`) is created automatically. Files are named `page_NNN.pdf` with zero-padded numbers.

### CLI Flags

```
PDFSplitter-CLI.exe <input.pdf> [--output-dir DIR] [--pages RANGE] [--json]
```

- `--output-dir` — Override output location (created if missing)
- `--pages "1-5, 8, 10-15"` — Extract specific pages into a single output file
- `--json` — Machine-parseable JSON output instead of plain text

### Key Implementation Patterns

**Atomic writes** — Each page is written via a temp file then `os.replace()`, preventing corruption on crash:

```python
temporary_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
try:
    output_document.save(temporary_path, garbage=4, deflate=True)
    os.replace(temporary_path, output_path)
finally:
    temporary_path.unlink(missing_ok=True)
```

**Page range parsing** — Accepts comma-separated tokens, each a number or range:

```python
parse_page_ranges("1-5, 8, 10-15", page_count=20)
# Returns: [0, 1, 2, 3, 4, 7, 9, 10, 11, 12, 13, 14]
```

**JSON output contract:**

```json
{"status": "ok", "input": "...", "pages": 5, "output_dir": "...", "files": [...]}
{"status": "error", "message": "..."}
```

### Flask GUI Pitfalls (Windows)

1. **Use `@app.route(..., methods=["POST"])` instead of `@app.post()`** — The shorthand decorator causes silent 404s on multipart file uploads in Flask 3.1.x when the live WSGI server (not test client) handles requests on Windows.

2. **Do not use tkinter file dialogs from Flask** — tkinter requires the main thread; Flask handles requests on worker threads. Use HTML `<input type="file">` with FormData upload instead.

3. **Kill zombie processes before restarting** — Flask dev server doesn't always release the port on Windows. Multiple listeners on the same port cause requests to hit stale code. Check with `netstat -ano | grep <port>` and `taskkill //PID <pid> //F`.

### PyInstaller Build

```
# Spec: build/pdfsplitter-pyinstaller/PDFSplitter-CLI.spec
python -m PyInstaller --clean --noconfirm PDFSplitter-CLI.spec
cp dist/PDFSplitter-CLI.exe ../../release/PDFSplitter-Portable/
```

The spec uses `console=True` and `upx=True` for a compressed single-file exe (~40MB with PyMuPDF bundled).

## Why This Matters

A portable exe that auto-creates directories and outputs JSON eliminates friction in Power Automate Desktop flows:

- No "Create folder" action needed before splitting
- No stderr parsing for error detection — JSON gives structured error messages
- Exit code 0/1 maps directly to PA's "If exit code equals" condition
- The `--pages` flag covers the "extract subset" use case without a separate tool
- Atomic writes prevent partial output on timeout or crash

## When to Apply

- Building CLI tools intended for Power Automate Desktop integration
- Any tool where the caller needs machine-parseable output alongside human-readable defaults
- PDF manipulation workflows where PyMuPDF is already a dependency
- Situations requiring portable Windows executables from Python scripts

## Examples

### Power Automate Desktop — Split all pages

```
System.RunApplication.RunApplicationAndWaitToComplete
    ApplicationPath: $'''C:\...\PDFSplitter-CLI.exe'''
    CommandLineArguments: $'''"%CurrentItem.FullName%" --json'''
    WorkingDirectory: $'''C:\...\PDFSplitter-Portable'''
    WindowStyle: System.ProcessWindowStyle.Hidden
    Timeout: 600
    ProcessId=> AppProcessId
    ExitCode=> AppExitCode
```

### Power Automate Desktop — Extract specific pages

```
CommandLineArguments: $'''"%CurrentItem.FullName%" --pages "1-3" --output-dir "%OutputFolder%" --json'''
```

### Running the testing GUI

```bash
cd scripts
set OPEN_BROWSER=1
set UV_LINK_MODE=copy
uv run pdf_splitter_gui.py
# Opens browser at http://127.0.0.1:8766
```

Or with the bat launcher: `scripts/start-splitter-gui.bat`

## Related Issues

- Follows the same pattern as `auto-pdf-rotate` project's CLI/GUI architecture
- Uses PyMuPDF's `insert_pdf(from_page, to_page)` for lossless page extraction

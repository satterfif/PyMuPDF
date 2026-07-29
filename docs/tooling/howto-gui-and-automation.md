# How to run the splitter GUI and Power Automate

Two ways to drive the PDF splitter without typing CLI commands: a local Flask GUI for hand-testing, and a portable exe for Power Automate Desktop.

## Run the local testing GUI

The GUI (`scripts/pdf_splitter_gui.py`) is a small Flask app for dragging in a PDF and watching it split. It declares its own dependencies inline (PEP 723) and runs under `uv` — no manual virtualenv.

### Prerequisites

- [`uv`](https://docs.astral.sh/uv/) installed and on `PATH`.

### Steps

1. On Windows, double-click or run the launcher:

   ```bat
   scripts\start-splitter-gui.bat
   ```

   It sets `OPEN_BROWSER=1`, `cd`s into `scripts/`, and runs `uv run pdf_splitter_gui.py`. `uv` installs Flask + PyMuPDF into an ephemeral environment on first run.

2. On macOS/Linux (or to run it directly):

   ```bash
   OPEN_BROWSER=1 uv run scripts/pdf_splitter_gui.py
   ```

3. A browser opens to `http://127.0.0.1:8766`. Upload a PDF and start a split; the page polls job status and reports the output folder and file count when done.

### How it works (so you can debug it)

- Uploads are saved under the OS temp dir (`pdf_splitter_uploads/`), capped at 500 MB.
- Each split runs in a background thread; progress is tracked per job id in memory.
- The GUI imports `split_pdf` and `SplitterError` directly from `pdf_splitter_cli.py` — it is a thin front end over the same core the CLI uses.

### Verification

Split a known PDF and confirm the reported file count matches its page count, and that the output folder contains that many `page_NNN.pdf` files.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `uv: command not found` | `uv` not installed. | Install `uv`, reopen the shell. |
| Browser doesn't open | `OPEN_BROWSER` not set. | Visit `http://127.0.0.1:8766` manually, or set `OPEN_BROWSER=1`. |
| Port already in use | 8766 taken. | Stop the other process; the port is fixed in the script. |
| "File must be a PDF" | Non-PDF upload. | Upload a `.pdf`. |

## Drive the splitter from Power Automate Desktop

The `release/PDFSplitter-Portable/` folder ships a standalone `PDFSplitter-CLI.exe` (PyInstaller build) plus setup notes, so no Python install is needed on the automation machine.

### Steps

1. In Power Automate Desktop, add a **Run application** (wait for completion) action.

2. Configure it:

   - **ApplicationPath:** the full path to `PDFSplitter-CLI.exe` in `release/PDFSplitter-Portable/`.
   - **CommandLineArguments:** `"%CurrentItem.FullName%" --json`
   - **WorkingDirectory:** the `release/PDFSplitter-Portable/` folder.
   - Run with a hidden window.

3. Inspect the action's **ExitCode** output.

### Verification

- **ExitCode 0** = success. The PDF was split; parse the JSON on stdout for `output_dir` and `files` if the flow needs them.
- **Any nonzero ExitCode** = failure. Route the item to a review branch. The JSON `message` field explains what went wrong.

The same exit-code contract applies to the OCR merge CLI if you deploy it the same way: 0 means the page was made searchable, nonzero means a structural anomaly the flow should flag (see [reference-ocr-merge-cli.md](reference-ocr-merge-cli.md#exit-codes-and-errors)).

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Exit code 1, JSON `status: error` | Bad input (missing file, non-PDF, out-of-range pages). | Read `message`; fix the input or the page range. |
| Antivirus blocks the exe | Unsigned PyInstaller binary. | Allowlist the exe on the automation machine. |
| Nothing on stdout | Forgot `--json`. | Add `--json` so the flow can parse a result. |

## Related

- [How to split a PDF](howto-split-pdf.md) — the CLI the GUI and exe wrap
- [Reference: PDF Splitter CLI](reference-pdf-splitter-cli.md) — the `--json` contract these depend on
- `release/PDFSplitter-Portable/POWER-AUTOMATE-SETUP.md` and `README.txt` — shipped setup notes

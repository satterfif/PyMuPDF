PDFSplitter CLI
===============

Split a PDF into one single-page PDF per source page:

    PDFSplitter-CLI.exe "C:\Documents\Invoices.pdf"

Output is saved to a folder named after the PDF, with a "pages" subfolder
created automatically:

    C:\Documents\Invoices\pages\page_001.pdf
    C:\Documents\Invoices\pages\page_002.pdf
    C:\Documents\Invoices\pages\page_003.pdf

The output folder is created if it does not exist. Existing output files
with the same names are replaced.

Options
-------

--output-dir <folder>
    Save output to a specific folder instead of the default:

    PDFSplitter-CLI.exe "C:\Documents\Invoices.pdf" --output-dir "C:\Output"

    The folder is created if it does not exist.

--pages <range>
    Extract specific pages into a single output file instead of splitting
    every page. Accepts comma-separated page numbers and ranges (1-based):

    PDFSplitter-CLI.exe "C:\Documents\Report.pdf" --pages "1-5, 8, 10-15"

    Produces one file: Report_pages.pdf containing the selected pages.

--json
    Output results as JSON to stdout instead of plain text. Useful for
    automation workflows that need to parse the result programmatically.

    Success: {"status": "ok", "input": "...", "pages": N, "output_dir": "...", "files": [...]}
    Error:   {"status": "error", "message": "..."}

Flags can be combined:

    PDFSplitter-CLI.exe "C:\Documents\Report.pdf" --pages "1-3" --output-dir "C:\Out" --json

Power Automate Desktop
----------------------

ApplicationPath:
    C:\Users\satterfif\Documents\GitHub\PyMuPDF\release\PDFSplitter-Portable\PDFSplitter-CLI.exe

CommandLineArguments:
    "%CurrentItem.FullName%" --json

WorkingDirectory:
    C:\Users\satterfif\Documents\GitHub\PyMuPDF\release\PDFSplitter-Portable

Use Run application and wait to complete with a hidden window and inspect the
ExitCode output. Exit code 0 means success; any nonzero value means failure.

With --json, parse stdout using "Convert JSON to custom object" for structured
access to the output file list and directory.

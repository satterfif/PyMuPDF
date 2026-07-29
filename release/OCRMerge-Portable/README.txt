OCR Merge CLI
=============

Make a scanned, image-only PDF page searchable by merging in OCR results you
already have. The output looks identical to the scan, but you can search and
copy its text.

    OCRMerge-CLI.exe "C:\Documents\page_001.pdf" "C:\Documents\page_001_formatted.json"

Output is written next to the input PDF as final_<name>.pdf:

    C:\Documents\final_page_001.pdf

This tool does NOT run OCR. It expects the OCR results to already exist as a
JSON file (the kind Microsoft Dynamics / Azure produces) that you pass as the
second argument.

Arguments
---------

<input_pdf> (required)
    The scanned, image-only PDF page. Must be a single page with no existing
    text layer.

<input_json> (required)
    The OCR JSON for that page (Dynamics/Azure shape: a top-level array whose
    first element has a "lines" array; each line has "text" and a
    "boundingBox" with normalized left/top/width/height).

--output-dir <folder>
    Write final_<name>.pdf to a specific folder instead of next to the input:

    OCRMerge-CLI.exe "page_001.pdf" "page_001_formatted.json" --output-dir "C:\Searchable"

    The folder is created if it does not exist.

--font <path-to-ttf>
    Embed a specific Unicode TrueType font. By default a system font is used
    automatically. Pass this if the tool reports it could not find one, or if
    your documents contain accented / non-Latin text:

    OCRMerge-CLI.exe "page_001.pdf" "page_001_formatted.json" --font "C:\Windows\Fonts\segoeui.ttf"

Behavior
--------

- The page image is never modified. The OCR text is added as an invisible
  layer on top, so the page looks exactly the same but is searchable.
- Garbled or misspelled OCR text is placed as-is. Text quality never causes a
  failure.
- Empty or whitespace-only lines are skipped.
- A Unicode font is embedded so accented / non-English text stays searchable.

Exit codes (for automation)
----------------------------

    0   Success. final_<name>.pdf was written.
    1   A structural problem. NOTHING was written. The message on screen
        (stderr) says which condition failed.

Exit 1 happens when the JSON is unreadable or the wrong shape, a coordinate is
out of range, the PDF already has a text layer, the PDF is missing / not a PDF
/ password-protected, or no usable font was found. Garbled OCR text is NOT a
failure.

One pair per run. To process a folder, loop over the PDFs and pass each one's
matching JSON. See POWER-AUTOMATE-SETUP.md for ready-to-paste flows.

Power Automate Desktop
----------------------

ApplicationPath:
    C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe

CommandLineArguments:
    "%CurrentItem.FullName%" "%JsonPath%"

    where JsonPath is derived per page, e.g.:
    SET JsonPath TO $'''%CurrentItem.Directory%\%CurrentItem.NameWithoutExtension%_formatted.json'''

WorkingDirectory:
    C:\Tools\OCRMerge-Portable

Use "Run application and wait to complete" with a hidden window and inspect the
ExitCode output. Exit code 0 means success; any nonzero value means failure.

Full setup, paste-ready flows, and error handling: see POWER-AUTOMATE-SETUP.md.

# OCR Merge — Power Automate Desktop Setup

Overlay existing OCR results onto scanned, image-only PDF pages so they become searchable — driven from Power Automate Desktop with no Python install required.

## What this tool does

For one image-only PDF page plus its OCR JSON (Microsoft Dynamics / Azure Read shape), it writes `final_<name>.pdf`: the same page image, now with an invisible, searchable text layer. It does **not** run OCR — it expects the JSON to already exist beside each PDF.

## Prerequisites

- Windows 10/11 with Power Automate Desktop installed
- `OCRMerge-CLI.exe` copied to a stable local path (not a network drive)
- For each page, a PDF and its matching OCR JSON in the same folder

## Recommended Installation Path

```
C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe
C:\Tools\OCRMerge-Portable\README.txt
```

Copy the entire `OCRMerge-Portable` folder to a permanent location. Do not run from a temp directory or a path that syncs to OneDrive — cloud sync can lock the exe during execution.

## The one thing that's different from the splitter

The OCR Merge tool takes **two** inputs that must be paired: a PDF and its JSON. Your flow loops over the PDFs and derives the JSON path for each. The JSON is expected to sit beside the PDF with a `_formatted.json` suffix on the base name, e.g.:

```
page_001.pdf   ->   page_001_formatted.json
page_002.pdf   ->   page_002_formatted.json
```

If your OCR export uses a different suffix (e.g. plain `page_001.json`), adjust the `SET JsonPath` line in the patterns below.

## Command shape

```
OCRMerge-CLI.exe "<pdf-path>" "<json-path>" [--output-dir "<dir>"] [--font "<ttf>"]
```

There is no `--json` result flag — this tool reports success or failure through its **exit code** only:

| Exit code | Meaning | What the flow should do |
|-----------|---------|-------------------------|
| 0 | Success — `final_<name>.pdf` was written | Continue |
| 1 | A structural problem; **nothing was written** | Route the file to a review branch |

"Structural problem" means the JSON is unreadable or off-shape, a coordinate is out of range, the PDF already has a text layer, the PDF is missing / not a PDF / password-protected, or no usable font was found. Garbled OCR text is **not** a failure — the tool places whatever text the OCR produced and still exits 0.

## Flow Setup

### Action: Run Application

Add a **"Run application"** action with these settings:

| Setting | Value |
|---------|-------|
| Application path | `C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe` |
| Command line arguments | `"%CurrentItem.FullName%" "%JsonPath%"` |
| Working directory | `C:\Tools\OCRMerge-Portable` |
| Window style | Hidden |
| After application launch | Wait for application to complete |
| Timeout | 600 |

**Output variables:**
- `AppProcessId` — process ID (not usually needed)
- `AppExitCode` — 0 = success, 1 = error

## Common Flow Patterns

### Pattern 1: Make every scanned page in a folder searchable

Loops over all PDFs in a folder, derives each JSON path, and merges. Output `final_*.pdf` lands beside each source PDF.

```
Folder.GetFiles Folder: $'''C:\Input\pages''' FileFilter: $'''*.pdf''' IncludeSubfolders: False Files=> Files

LOOP FOREACH CurrentItem IN Files
    SET JsonPath TO $'''%CurrentItem.Directory%\%CurrentItem.NameWithoutExtension%_formatted.json'''
    IF File.IfFileExists.IfFileExists File: $'''%JsonPath%''' Exists=> JsonExists THEN
    END
    IF JsonExists THEN
        System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" "%JsonPath%"''' WorkingDirectory: $'''C:\Tools\OCRMerge-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
        IF AppExitCode <> 0 THEN
            Display.ShowMessageDialog.ShowMessage Title: $'''OCR Merge Error''' Message: $'''Failed on: %CurrentItem.FullName% (exit %AppExitCode%)''' Icon: Display.Icon.Error Buttons: Display.Buttons.OK ButtonPressed=> ButtonPressed
        END
    ELSE
        Display.ShowMessageDialog.ShowMessage Title: $'''OCR Merge — missing JSON''' Message: $'''No OCR JSON for: %CurrentItem.FullName%''' Icon: Display.Icon.Warning Buttons: Display.Buttons.OK ButtonPressed=> ButtonPressed
    END
END
```

### Pattern 2: Route successes and failures to different folders

Move each `final_*.pdf` to a "searchable" output folder on success; move the source to a "review" folder on failure.

```
Folder.GetFiles Folder: $'''C:\Input\pages''' FileFilter: $'''*.pdf''' IncludeSubfolders: False Files=> Files

LOOP FOREACH CurrentItem IN Files
    SET JsonPath TO $'''%CurrentItem.Directory%\%CurrentItem.NameWithoutExtension%_formatted.json'''
    System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" "%JsonPath%" --output-dir "C:\Output\searchable"''' WorkingDirectory: $'''C:\Tools\OCRMerge-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
    IF AppExitCode = 0 THEN
        # final_<name>.pdf was written to C:\Output\searchable
    ELSE
        File.Move Files: $'''%CurrentItem.FullName%''' Destination: $'''C:\Output\review''' IfFileExists: File.IfExists.Overwrite
    END
END
```

### Pattern 3: Pin a font for non-English documents

If the automation machine reports "No Unicode-capable TTF font found", or your documents contain accented / non-Latin text, pass a specific font. The tool embeds it so that text stays searchable and copyable.

```
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" "%JsonPath%" --font "C:\Windows\Fonts\segoeui.ttf"''' WorkingDirectory: $'''C:\Tools\OCRMerge-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
```

### Pattern 4: Split, then make searchable (combined with PDF Splitter)

Split a multi-page scan into pages, then merge each page's OCR JSON. Assumes the splitter has already produced `page_NNN.pdf` files and your OCR step has produced `page_NNN_formatted.json` beside them.

```
# Step 1: split the multi-page scan
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" --output-dir "C:\Work\pages" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> SplitPid ExitCode=> SplitExit

# (OCR step happens here — produces page_NNN_formatted.json in C:\Work\pages)

# Step 2: merge OCR onto each split page
Folder.GetFiles Folder: $'''C:\Work\pages''' FileFilter: $'''page_*.pdf''' IncludeSubfolders: False Files=> PageFiles
LOOP FOREACH CurrentItem IN PageFiles
    SET JsonPath TO $'''%CurrentItem.Directory%\%CurrentItem.NameWithoutExtension%_formatted.json'''
    System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\OCRMerge-Portable\OCRMerge-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" "%JsonPath%"''' WorkingDirectory: $'''C:\Tools\OCRMerge-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> MergePid ExitCode=> MergeExit
END
```

## Output Structure

Given input `C:\Input\pages\page_001.pdf` and `C:\Input\pages\page_001_formatted.json`, with no `--output-dir`:

```
C:\Input\pages\
├── page_001.pdf                (original, untouched)
├── page_001_formatted.json     (OCR input, untouched)
└── final_page_001.pdf          (new — searchable)
```

With `--output-dir "C:\Output\searchable"`:

```
C:\Output\searchable\
└── final_page_001.pdf
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — `final_<name>.pdf` written |
| 1 | Structural error — nothing written; the message on stderr says which condition failed |

## Error Handling

Messages the tool prints to stderr on exit 1:

| Error | Cause | Fix |
|-------|-------|-----|
| `Input PDF does not exist: ...` | PDF path wrong or file deleted | Check the path variable |
| `Input JSON does not exist: ...` | JSON path wrong, or the `_formatted.json` suffix doesn't match your export | Adjust the `SET JsonPath` line |
| `Input file must be a PDF: ...` | Non-PDF passed | Add a `*.pdf` file filter |
| `Invalid OCR JSON: ...` | JSON unreadable or off-shape | Confirm it's the OCR export for that page |
| `... is outside the normalized 0-1 range` | Coordinates aren't normalized 0–1 | Check the OCR export settings |
| `PDF already contains a text layer: ...` | The page is already searchable | Skip it — no merge needed |
| `Password-protected PDF is not supported` | Encrypted PDF | Remove the password first |
| `No Unicode-capable TTF font found` | No system font at the default paths | Pass `--font "C:\Windows\Fonts\segoeui.ttf"` |

To capture the exact stderr message in a variable, use the **"Run DOS command"** action instead of "Run application" — it exposes standard output/error as variables.

## Troubleshooting

**"The system cannot find the file specified"**
- Check the exe path for typos
- Keep the exe on a local drive, not a network share or OneDrive-synced folder
- Run the exe once manually from Command Prompt to confirm it works

**Every file fails with "Input JSON does not exist"**
- Your OCR export suffix probably isn't `_formatted.json`. Edit the `SET JsonPath` line to match (e.g. drop `_formatted`, or change the extension).

**Exit code 1 but you can't see why**
- Switch the action to "Run DOS command" and read the captured stderr — it names the exact condition.

**Timeout on large batches**
- The tool processes one page per run; a dense page with ~100+ text lines is still fast. If a single run times out, raise the Timeout value and check antivirus isn't scanning the exe on every launch.

**Output looks searchable but some words are garbled**
- That's OCR quality, not a tool fault. The tool faithfully places whatever text the OCR produced.

# PDF Splitter — Power Automate Desktop Setup

## Prerequisites

- Windows 10/11 with Power Automate Desktop installed
- `PDFSplitter-CLI.exe` copied to a stable local path (not a network drive)

## Recommended Installation Path

```
C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe
C:\Tools\PDFSplitter-Portable\README.txt
```

Copy the entire `PDFSplitter-Portable` folder to a permanent location. Do not run from a temp directory or a path that syncs to OneDrive — cloud sync can lock the exe during execution.

## Flow Setup

### Action: Run Application

Add a **"Run application"** action with these settings:

| Setting | Value |
|---------|-------|
| Application path | `C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe` |
| Command line arguments | `"%CurrentItem.FullName%" --json` |
| Working directory | `C:\Tools\PDFSplitter-Portable` |
| Window style | Hidden |
| After application launch | Wait for application to complete |
| Timeout | 600 |

**Output variables:**
- `AppProcessId` — process ID (not usually needed)
- `AppExitCode` — 0 = success, 1 = error

### Paste-Ready Action Text

Copy this directly into a Power Automate Desktop flow (Edit → Paste):

```
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
```

## Common Flow Patterns

### Pattern 1: Split All Pages in a Folder

Splits every PDF in a folder. Output goes to `{filename}/pages/page_001.pdf`, etc.

```
Folder.GetFiles Folder: $'''C:\Input''' FileFilter: $'''*.pdf''' IncludeSubfolders: False Files=> Files

LOOP FOREACH CurrentItem IN Files
    System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
    IF AppExitCode <> 0 THEN
        Display.ShowMessageDialog.ShowMessage Title: $'''PDF Split Error''' Message: $'''Failed to split: %CurrentItem.FullName%''' Icon: Display.Icon.Error Buttons: Display.Buttons.OK ButtonPressed=> ButtonPressed
    END
END
```

### Pattern 2: Split and Route to Specific Output Folder

Sends all split pages to a single shared output folder.

```
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" --output-dir "C:\Output\SplitPages" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
```

### Pattern 3: Extract Specific Pages

Extract pages 1–3 from a PDF (produces a single combined file).

```
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" --pages "1-3" --output-dir "C:\Output" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode
```

### Pattern 4: Parse JSON Output

Use the JSON output to get the list of created files.

```
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessId ExitCode=> AppExitCode StandardOutput=> JsonOutput

Variables.ConvertJsonToCustomObject Json: $'''%JsonOutput%''' CustomObject=> SplitResult

IF SplitResult.status = $'''ok''' THEN
    # SplitResult.pages = number of output files
    # SplitResult.output_dir = folder containing the split files
    # SplitResult.files = list of output file paths
END
```

> **Note:** To capture StandardOutput, use the **"Run DOS command"** or **"Run process"** action variant instead of "Run application" — it exposes stdout as a variable.

### Pattern 5: Combined with AutoPDFRotate

Run rotation correction first, then split the corrected output.

```
# Step 1: Auto-rotate
System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\AutoPDFRotate-Portable\AutoPDFRotate-CLI.exe''' CommandLineArguments: $'''"%CurrentItem.FullName%"''' WorkingDirectory: $'''C:\Tools\AutoPDFRotate-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessIdRotate ExitCode=> ExitCodeRotate

# Step 2: Split the corrected file
SET CorrectedFile TO $'''%CurrentItem.Directory%\%CurrentItem.NameWithoutExtension%_corrected_orientation.pdf'''

System.RunApplication.RunApplicationAndWaitToComplete ApplicationPath: $'''C:\Tools\PDFSplitter-Portable\PDFSplitter-CLI.exe''' CommandLineArguments: $'''"%CorrectedFile%" --json''' WorkingDirectory: $'''C:\Tools\PDFSplitter-Portable''' WindowStyle: System.ProcessWindowStyle.Hidden Timeout: 600 ProcessId=> AppProcessIdSplit ExitCode=> ExitCodeSplit
```

## Output Structure

Given input `C:\Input\Invoices.pdf`:

```
C:\Input\
├── Invoices.pdf              (original, untouched)
└── Invoices\
    └── pages\
        ├── page_001.pdf
        ├── page_002.pdf
        └── page_003.pdf
```

With `--output-dir "C:\Output"`:

```
C:\Output\
├── page_001.pdf
├── page_002.pdf
└── page_003.pdf
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — all pages split |
| 1 | Error — check stderr or JSON output for details |

## Error Handling

Common errors returned in JSON `message` field:

| Error | Cause | Fix |
|-------|-------|-----|
| `Input PDF does not exist: ...` | File path wrong or file deleted | Check the path variable |
| `Input file must be a PDF: ...` | Non-PDF file passed | Add a file filter (*.pdf) |
| `Password-protected PDF is not supported` | Encrypted PDF | Remove password first |
| `PDF contains no pages` | Corrupt or empty PDF | Skip the file |
| `Page N out of range` | --pages references a non-existent page | Check page count first |

## Troubleshooting

**"The system cannot find the file specified"**
- Check that the exe path has no typos
- Ensure the path is not on a network drive that disconnects
- Try running the exe manually from Command Prompt first

**Timeout (process never completes)**
- Large PDFs (500+ pages) may need a longer timeout
- Check if antivirus is scanning/blocking the exe
- Run once manually to verify it works outside Power Automate

**Exit code 1 but no visible error**
- Add `--json` to capture the error message in stdout
- Or check Task Manager for zombie processes on the port

**Output folder not created**
- Ensure the exe has write permission to the target directory
- Cloud-synced folders (OneDrive/SharePoint) may interfere — use a local path

# Tutorial: from a scanned PDF to searchable pages

By the end of this tutorial you'll have taken a multi-page scanned PDF, split it into single pages, and turned one page into a **searchable** PDF you can Ctrl+F — using only the two tools in `scripts/`. You'll see a real result within the first three commands.

This is the end-to-end path the tools were built for: a folder of scanned documents (mill certificates, invoices) that you want to find text in.

## What you'll need

- Python 3.10+ with `pymupdf` importable — check with `python -c "import pymupdf"`.
- A scanned, image-only PDF to practice on. We'll call it `scanned.pdf`.
- Its OCR results as Dynamics/Azure-style JSON (one JSON per page). If you don't have OCR output yet, that step is upstream of these tools — they consume OCR, they don't produce it.
- Run everything from the repo root.

## Step 1: Split the scan into single pages

```bash
python scripts/pdf_splitter_cli.py scanned.pdf
```

You immediately get a folder of one-page PDFs:

```
scanned/pages/page_001.pdf
scanned/pages/page_002.pdf
scanned/pages/page_003.pdf
...
```

That's your first visible result — open `scanned/pages/page_001.pdf` and you'll see page 1 on its own. Right now it's still image-only: try to select text and nothing happens.

## Step 2: Confirm a page has no text yet

Prove the starting state so the change in Step 3 is unmistakable:

```bash
python -c "import pymupdf; print(repr(pymupdf.open('scanned/pages/page_001.pdf')[0].get_text()))"
```

You'll see an empty or whitespace-only string — the page carries no searchable text. That's exactly what the OCR merge step fixes.

## Step 3: Merge OCR results to make the page searchable

Point the OCR merge tool at the page and its OCR JSON. (Match your JSON's filename — here we assume `page_001_formatted.json`.)

```bash
python scripts/ocr_merge_cli.py scanned/pages/page_001.pdf page_001_formatted.json
```

It prints:

```
Wrote searchable PDF: .../final_page_001.pdf
```

You now have `final_page_001.pdf` — visually identical to the scan, but searchable.

## Step 4: See it work

Search the new file for a word you can read on the page:

```bash
python -c "import pymupdf; p=pymupdf.open('final_page_001.pdf')[0]; print(p.search_for('the'))"
```

A non-empty list of rectangles means the word was found and located on the page. Open `final_page_001.pdf` in any PDF viewer, press Ctrl+F, and search a word you see — the highlight lands on the printed text, even though the text layer itself is invisible.

## Step 5: Do the whole folder

One page proves the flow; a folder is a loop. Bash:

```bash
for pdf in scanned/pages/page_*.pdf; do
  json="${pdf%.pdf}_formatted.json"
  [ -f "$json" ] && python scripts/ocr_merge_cli.py "$pdf" "$json"
done
```

Each page becomes a `final_page_NNN.pdf`. In an automation tool like Power Automate Desktop, the same loop runs off exit codes instead — see [How to run the splitter GUI and Power Automate](howto-gui-and-automation.md).

## What you built

You took an opaque scanned PDF and turned it into searchable pages:

1. **Split** the scan into single pages (`pdf_splitter_cli.py`).
2. **Merged** each page's existing OCR results into an invisible text layer (`ocr_merge_cli.py`), so the pages are searchable without changing how they look.

The scan is unchanged to the eye; the text is now findable and copyable. From here:

- Dig into every flag: [Reference: PDF Splitter CLI](reference-pdf-splitter-cli.md), [Reference: OCR Merge CLI](reference-ocr-merge-cli.md).
- Understand *why* the text layer is invisible and width-scaled: [Explanation: tooling design decisions](explanation-design.md).
- Wire it into automation: [How to run the splitter GUI and Power Automate](howto-gui-and-automation.md).

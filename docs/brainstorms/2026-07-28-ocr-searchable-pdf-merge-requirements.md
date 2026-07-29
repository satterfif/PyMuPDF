---
date: 2026-07-28
topic: ocr-searchable-pdf-merge
---

# OCR Searchable-PDF Merge — Requirements

## Summary

A standalone CLI tool (sibling to `scripts/pdf_splitter_cli.py`) that takes one image-only PDF page plus its OCR JSON and writes a `final_<name>.pdf` carrying an invisible, searchable text layer whose selection visibly tracks the printed words. It consumes existing OCR results (Microsoft Dynamics / Azure Read style JSON) rather than running OCR itself.

## Problem Frame

Scanned document pages (e.g. `page_005.pdf`) are image-only: they can't be searched, and text can't be copied. OCR has already been run against these pages and the results saved as JSON alongside each PDF, but the JSON lives separately from the PDF — nothing in the retrieval workflow benefits from it. The cost is that a folder of scanned mill certificates and purchase documents is opaque to search: finding a heat number or PO across pages means opening and eyeballing each one. The OCR text and per-line coordinates already exist; they just need to be married back onto the image so the page becomes searchable in place.

## Key Decisions

- **Line-level placement with height-sizing plus horizontal scaling (the "OCR sandwich").** Each OCR line is placed as one invisible run: the font is sized from the line box's height, then horizontally scaled so the run spans the box width. This keeps the selection band the correct height *and* makes it track the printed line, rather than merely being findable somewhere on the page. This is the technique Tesseract and OCRmyPDF use.

- **Embed a Unicode-capable font, not base-14 `helv`.** The source data contains German and accented characters (e.g. "Österreich", "Abnahmeprüfzeugnis"). A base-14 font would silently drop or mangle those glyphs, breaking search and copy on exactly the text that needs it. A font with a correct `ToUnicode` map is required so copied/searched text is faithful Unicode.

- **Strict on structural anomalies, tolerant of text quality.** OCR text is inherently noisy — garbled words are normal and are placed as-is. The tool fails loudly (exits non-zero, writes nothing) only on structural problems that mean the JSON and PDF cannot be reconciled. This separation is deliberate: a quality gate keyed on text noise would reject the everyday case the tool exists to serve.

- **The image is never modified.** Text is drawn as an overlay on top of the existing page content; the scanned image XObject is left untouched.

## Requirements

**Core behavior**

R1. Given one image-only PDF page and one OCR JSON file, the tool writes a single output PDF named `final_<input-stem>.pdf` in the input PDF's directory.

R2. The output PDF is visually identical to the input (same image, unmodified) plus an invisible text layer (PDF text render mode 3).

R3. Every non-empty OCR line is placed as one invisible text run positioned at its bounding box, so the text is searchable (Ctrl+F) and copy/paste yields the line text.

R4. Each placed line's invisible text is sized from its box height and horizontally scaled to span its box width, so selection highlighting visibly overlays the printed line.

R5. Text is rendered with an embedded Unicode-capable font so non-ASCII characters in the OCR text are searchable and copy correctly.

**Input handling**

R6. The tool reads the Dynamics/Azure OCR JSON shape: a top-level array whose element carries a `lines` array, each line having `text` and a `boundingBox` with normalized (0–1) `left`, `top`, `width`, `height`.

R7. Normalized coordinates are converted to PDF points against the page's dimensions, honoring the page's top-left origin, with the text baseline placed at the box bottom.

R8. Empty or whitespace-only lines are silently skipped (not an error).

R9. Garbled or misspelled OCR text is placed verbatim — text quality is never a reason to fail or drop a line.

**Failure behavior**

R10. On any structural anomaly the tool exits non-zero and writes no output file. Structural anomalies are: JSON unreadable or not matching the expected schema; bounding-box coordinates well outside the normalized 0–1 range; or the input PDF already containing a real text layer.

R11. Error output identifies which structural condition failed, in a message a human reviewing an automation failure can act on.

R12. The tool operates on exactly one PDF+JSON pair per invocation.

## Key Flows

- F1. Single-page merge (happy path)
  - **Trigger:** Tool invoked with a PDF path and a JSON path.
  - **Steps:** Validate paths and PDF openability; parse and validate the OCR JSON; confirm the PDF page has no existing text layer; for each non-empty line, map its normalized box to page points, size and scale the invisible run, and place it; save `final_<stem>.pdf` alongside the input.
  - **Outcome:** A searchable PDF whose selection tracks the printed text; exit zero.

- F2. Structural failure
  - **Trigger:** JSON fails to parse/validate, coordinates are out of range, or the PDF already has a text layer.
  - **Steps:** Emit an actionable error identifying the condition; write nothing; exit non-zero.
  - **Outcome:** The calling automation detects failure by exit code and flags the page for a human.

## Acceptance Examples

- AE1. **Covers R3, R4, R5.** Given `page_005.pdf` and `page_005_formatted.json` with 107 lines including "Abnahmeprüfzeugnis", when merged, then `final_page_005.pdf` opens visually unchanged, Ctrl+F for "Abnahmeprüfzeugnis" finds it, and selecting it highlights over the printed word.

- AE2. **Covers R8, R9.** Given a JSON containing a garbled line ("Salte / page") and an empty-text line, when merged, then the garbled line is placed verbatim and searchable, the empty line is skipped, and the tool exits zero.

- AE3. **Covers R10.** Given a PDF that already contains selectable text, when the tool runs, then it exits non-zero, writes no `final_*.pdf`, and reports that a text layer already exists.

- AE4. **Covers R10.** Given a JSON whose bounding boxes carry values well outside 0–1, when the tool runs, then it exits non-zero and writes no output.

## Scope Boundaries

**Deferred for later**

- Batch / folder mode. One PDF+JSON pair per invocation; the calling automation (e.g. Power Automate Desktop) loops over the `pages/` directory. Auto-pairing across the observed naming variance (`page_001.json` vs `page_005_formatted.json`) belongs to a later batch mode if one is built.
- Per-word selection highlighting. The JSON carries only line-level boxes, so word positions would be inferred by distributing measured character widths across the line box — unreliable on tabular rows (columnar data isn't evenly spaced). Revisit if line-level selection proves too coarse in practice, or if word-level OCR becomes available.
- A text-quality gate (e.g. fail when more than X% of lines are empty or below a confidence threshold). "Strict" covers structure only; quality thresholds are a separate, unadded knob.

**Outside this scope**

- Running OCR. The tool consumes existing OCR JSON; it does not invoke Tesseract or any OCR engine. PyMuPDF's built-in `Pixmap.pdfocr_save()` re-OCRs and would ignore the supplied JSON.
- Page skew / polygon correction. The `boundingBox` polygon and any page-skew angle are not used in v1; boxes are treated as axis-aligned rectangles.

## Dependencies / Assumptions

- Depends on PyMuPDF's invisible-text support: `render_mode=3` (confirmed `src/__init__.py:15524`), placement via `TextWriter` / `Page.write_text` (`src/__init__.py:16905`, `17254`) or `Page.insert_text`, with the image preserved via `overlay=True`. PyMuPDF's Python API uses a top-left origin, matching the JSON's coordinate convention (no y-flip).
- Follows the standalone-tooling conventions of `scripts/pdf_splitter_cli.py`: argparse entry point, a dedicated error type, path validation, not part of the built wheel.
- Assumes each input PDF is a single page. Multi-page inputs are not a considered case in v1.
- Assumes the OCR JSON corresponds to the PDF page passed in — pairing is the caller's responsibility.

## Sources / Research

- OCR JSON sample and shape: `page_005_formatted.json` (Dynamics CRM `expando` wrapper; 107 lines; normalized boxes; non-ASCII text).
- Existing tool to mirror: `scripts/pdf_splitter_cli.py`.
- Prior ideation: `docs/ideation/searchable-pdf-ocr-merge.html`.
- PyMuPDF capabilities: `src/__init__.py` — `render_mode` / `Tr` operator (`15524`), `TextWriter` (`16905`), `TextWriter.write_text` (`17254`), `get_text_length` (`22713`), `Font.text_length` (`8502`).
- Technique reference: invisible-text "OCR sandwich" (PDF text render mode 3) as used by Tesseract / OCRmyPDF; horizontal scaling to fit line width.

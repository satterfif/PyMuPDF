# How to make an image PDF searchable

Turn a scanned, image-only PDF page into a searchable PDF by merging in OCR results you already have. The output looks identical to the scan but you can Ctrl+F and copy its text.

## Prerequisites

- Python 3.10+ with `pymupdf` importable.
- A single-page image PDF (e.g. `page_005.pdf`) with **no** existing text layer.
- The matching OCR JSON (Dynamics/Azure Read shape) for that page (e.g. `page_005_formatted.json`). See [reference-ocr-merge-cli.md](reference-ocr-merge-cli.md#input-json-schema) for the exact shape.
- A Unicode-capable TrueType font available (a system font is used by default; see below if none is found).

## Merge one page

1. Run the tool with the PDF and its JSON:

   ```bash
   python scripts/ocr_merge_cli.py page_005.pdf page_005_formatted.json
   ```

2. Find `final_page_005.pdf` beside the input. On success the tool prints:

   ```
   Wrote searchable PDF: .../final_page_005.pdf
   ```

## Choose the output folder

```bash
python scripts/ocr_merge_cli.py page_005.pdf page_005_formatted.json --output-dir "C:/searchable"
```

## Pin a specific font

If the auto-detected font isn't what you want, or the tool reports no font was found, pass one:

```bash
python scripts/ocr_merge_cli.py page_005.pdf page_005_formatted.json --font "C:/Windows/Fonts/segoeui.ttf"
```

Use a Unicode-capable TTF — it's embedded so non-ASCII text (accents, umlauts) stays searchable.

## Verification

Open the output and confirm the text layer works:

```bash
python -c "import pymupdf; d=pymupdf.open('final_page_005.pdf'); p=d[0]; print(bool(p.search_for('Customer'))); print([f[3] for f in p.get_fonts()])"
```

- `search_for(...)` returning a non-empty list means the text is searchable.
- `get_fonts()` listing an embedded font (e.g. `Arial Regular`) confirms the Unicode font embedded.

Or just open the PDF in a viewer, Ctrl+F for a word you can see on the page, and confirm the highlight lands on it.

## Process a whole folder

The tool does one pair per run by design; loop in your shell. Bash:

```bash
for pdf in pages/page_*.pdf; do
  json="${pdf%.pdf}_formatted.json"
  [ -f "$json" ] && python scripts/ocr_merge_cli.py "$pdf" "$json"
done
```

For Power Automate Desktop, see [How to run the splitter GUI and Power Automate](howto-gui-and-automation.md) — the same exit-code contract applies (0 = done, non-zero = flag for review).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `PDF already contains a text layer` | The page isn't image-only (it has real or prior OCR text). | Don't re-OCR; the page is already searchable. If it's incidental vector text, that page isn't a merge target. |
| `Invalid OCR JSON: ...` | JSON is unreadable or off-schema (no top-level array, no `lines`, missing `boundingBox`). | Confirm the JSON matches the Dynamics/Azure shape in the reference. |
| `... is outside the normalized 0-1 range` | A coordinate is far outside 0–1 (beyond ±0.05). | The JSON isn't normalized as expected; check the OCR export settings. |
| `No Unicode-capable TTF font found` | No system font at the built-in candidate paths. | Pass `--font <path-to-ttf>`. |
| Searchable but garbled words | OCR quality, not a tool bug. | Expected — garbled text is placed verbatim; text quality never fails a page. |
| `get_text()` shows `\xa0` between words | Embedded-font extraction uses non-breaking spaces. | Not a bug — search and copy-into-search normalize it. |

## Related

- [Reference: OCR Merge CLI](reference-ocr-merge-cli.md) — schema, coordinate rules, exit codes
- [Explanation: tooling design decisions](explanation-design.md) — why the layer is invisible and width-scaled
- [Tutorial: from scanned PDF to searchable PDF](tutorial-scan-to-searchable.md) — the full split → OCR → merge flow

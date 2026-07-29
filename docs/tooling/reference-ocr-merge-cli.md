# Reference: OCR Merge CLI

`scripts/ocr_merge_cli.py` takes one image-only PDF page plus its OCR JSON and writes `final_<stem>.pdf`: the same page image, plus an invisible, searchable text layer whose selection tracks the printed words. It consumes existing OCR results (Microsoft Dynamics / Azure Read style JSON) — it does not run OCR itself. It is a standalone tool, not part of the built `pymupdf` wheel.

## Invocation

```bash
python scripts/ocr_merge_cli.py <input_pdf> <input_json> [--output-dir DIR] [--font TTF]
```

## Arguments

| Argument | Type | Default | Effect |
|----------|------|---------|--------|
| `input_pdf` | path (positional, required) | — | The image-only source PDF. Must exist, end in `.pdf`, be a single page, and have no existing text layer. |
| `input_json` | path (positional, required) | — | The OCR JSON for that page. Must exist and match the expected schema. |
| `--output-dir DIR` | path | the input PDF's directory | Where `final_<stem>.pdf` is written. Created automatically if absent. |
| `--font TTF` | path | first available system TTF | A Unicode-capable TrueType font to embed. |

Exactly one PDF+JSON pair is processed per invocation; the caller loops over a folder.

## Input JSON schema

The parser expects the Dynamics/Azure `expando` shape: a **non-empty top-level array** whose first element carries a `lines` array. Each line has a `text` string and a `boundingBox` with normalized (0–1, top-left origin) `left`, `top`, `width`, `height`:

```json
[
  {
    "page": 1,
    "lines": [
      {
        "text": "Customer Name",
        "boundingBox": { "left": 0.0208, "top": 0.0121, "width": 0.1302, "height": 0.0141 }
      }
    ]
  }
]
```

Extra keys (the `@odata.type` noise Dynamics emits, the polygon inside `boundingBox`) are ignored.

## Behavior

For each non-empty line, the tool:
1. Maps the normalized box to PDF points against the page size (top-left origin, no y-flip; baseline at box bottom).
2. Sizes the font from the box height.
3. Computes a horizontal scale so the run spans the box width, clamped to `[0.1, 10]`.
4. Places the line with `page.insert_text(..., render_mode=3)` (invisible), morphed by `Matrix(h_scale, 0, 0, 1, 0, 0)` about the baseline so only width is scaled — glyph height stays fixed and the selection band tracks the printed line.

The page image is drawn over, never modified (`overlay=True`). Output is written atomically (temp file then `os.replace`), so a failed run leaves no partial `final_*.pdf`.

**Tolerant of text quality.** Garbled or misspelled OCR text is placed verbatim. Empty or whitespace-only lines are silently skipped. Text quality never fails a page.

## Coordinate tolerance

Coordinates slightly outside 0–1 (rounding, e.g. `-0.001`) are accepted; a value beyond `±COORD_TOLERANCE` (0.05) is a structural anomaly. So `1.03` passes, `5.0` fails.

## Font embedding

A Unicode-capable TrueType font is **embedded** (not referenced) so non-ASCII OCR text (e.g. "Österreich") gets a correct `ToUnicode` map and searches/copies faithfully. Base-14 fonts like Helvetica would drop or mangle those glyphs, so the tool refuses to fall back to one: if no usable TTF is found it fails with a clear message rather than degrading silently.

Font resolution order: `--font` if given, else the first existing path among a built-in candidate list (`arial.ttf`, `segoeui.ttf` on Windows; DejaVu Sans / Arial on Linux/macOS). If none exists, `OcrMergeError` asks you to pass `--font`.

## Exit codes and errors

| Exit | Meaning |
|------|---------|
| `0` | Success — `final_<stem>.pdf` written. |
| `1` | An `OcrMergeError` (structural anomaly or bad input); no output written. |

Strict-on-structure: the tool exits `1` and writes nothing when the JSON is unreadable or off-schema, a coordinate is out of range, the input PDF already has a text layer, the PDF is missing / non-`.pdf` / password-protected / zero-page, or no embeddable font is found.

## A note on extracted whitespace

Embedded-font extraction renders inter-word spaces as U+00A0 (non-breaking space) in `page.get_text()`. MuPDF's search normalizes this, so `page.search_for("Customer Name")` and Ctrl+F both work; only a raw `get_text()` string comparison sees the `\xa0`. This is expected, not a defect.

## Public functions (for importers)

- `merge_ocr(input_pdf, input_json, output_dir=None, font_path=None) -> Path` — the core entry point. Returns the output path. Raises `OcrMergeError`.
- `parse_ocr_lines(data) -> list[OcrLine]` — pure JSON → line records; validates schema and coordinate range.
- `compute_placement(line, page_width, page_height, font) -> Placement` — pure geometry: baseline point, font size, horizontal scale.
- `apply_text_layer(page, lines, font_path) -> None` — places the invisible layer on an open page.
- `resolve_font_path(font_path=None) -> str` — resolves a usable TTF or raises.
- `OcrMergeError` — the user-facing error type.
- `main(argv=None) -> int` — the CLI entry; returns the exit code.

## Examples

```bash
# Merge one page's OCR JSON; writes final_page_005.pdf beside the input
python scripts/ocr_merge_cli.py page_005.pdf page_005_formatted.json

# Pin a specific Unicode font and output folder
python scripts/ocr_merge_cli.py page_005.pdf page_005_formatted.json \
  --font "C:/Windows/Fonts/segoeui.ttf" --output-dir "C:/searchable"
```

## Related

- [How to make an image PDF searchable](howto-make-searchable.md)
- [Tutorial: from scanned PDF to searchable PDF](tutorial-scan-to-searchable.md)
- [Explanation: tooling design decisions](explanation-design.md)
- Tests: `tests/test_ocr_merge_cli.py`

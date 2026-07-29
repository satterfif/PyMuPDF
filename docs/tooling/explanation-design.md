# Explanation: PDF tooling design decisions

The `scripts/` PDF tools (splitter and OCR merge) are small, but a few choices in them are non-obvious. This doc explains *why* they work the way they do. For *what* they do, see the reference docs.

## Why these tools live in `scripts/`, not in the wheel

PyMuPDF ships as a library. These are end-user CLIs built on top of it for a specific automation need (splitting scanned batches, making them searchable) driven by Power Automate Desktop. Keeping them in `scripts/` — outside `src/` and the built wheel — means they can depend on the library, evolve on their own cadence, and carry automation-specific concerns (JSON output, exit-code contracts, a Flask test GUI) without adding surface area or dependencies to the package every `pip install pymupdf` pulls.

## Why the splitter uses threads (the documented exception)

PyMuPDF's cardinal rule is **no multithreading** — the core binding is not thread-safe for concurrent work on a shared document, and parallel document work should use multiprocessing.

The splitter is the one documented exception. Splitting is I/O-bound: each page is opened, copied into a fresh one-page document, and saved. The win comes from overlapping those saves, not from CPU parallelism.

The safety condition that makes threading acceptable here: **each worker opens its own document handle.** No `Document` object is shared across threads. Under that constraint the "no multithreading" rule doesn't bite — the rule is about shared mutable document state, which never occurs.

### Trade-off

Threading has real setup cost: each worker pays a per-thread document-open. On a small PDF that cost dominates the I/O savings. So the splitter only threads at **50+ pages** (`_PARALLEL_THRESHOLD`) and caps workers at `min(8, cpu_count)`. Below the threshold it runs sequentially. The threshold is a deliberate "don't pay for parallelism you won't recoup" line, not a hard limit.

## Why the OCR layer is invisible text, not redrawn text

The OCR merge tool's job is to make a *scanned image* searchable without changing how it looks. The scan is the source of truth for appearance; the OCR text is only there so search and copy work.

The standard technique is the **"OCR sandwich"**: draw the recognized text in PDF render mode 3 (`Tr 3` — neither filled nor stroked, so it paints nothing) on top of the image. The glyphs contribute to the text/selection model but are invisible. This is what Tesseract and OCRmyPDF produce.

```
   image PDF                 OCR JSON (line boxes)
   ┌──────────────┐          text + normalized box
   │ (scanned     │                │
   │  page image) │   overlay      ▼
   │              │ ◄─── invisible text, render mode 3
   └──────────────┘          you SEE the image,
                             you SEARCH the text
```

The image content stream is drawn over (`overlay=True`), never edited — verified in tests by asserting the rendered pixmap is byte-identical before and after.

## Why selection has to be scaled to the box width

The OCR JSON gives a bounding box per line, but the recognized string rarely has the same natural width as the printed line at any given font size. If you place the text at its natural width, the invisible selection rectangle drifts away from the printed words — search still finds the text, but highlighting lands in the wrong place.

The fix: size the font from the box **height**, then apply a **horizontal-only scale** so the run spans the box **width**. Height stays fixed (so the selection band is the right height), width is stretched or compressed to match the print.

### Why `insert_text` with a morph, not `TextWriter` with a single emit

The first design used one `TextWriter` accumulating all lines, emitted once. That has no seam for a *per-line* horizontal scale: `TextWriter.append` hardcodes a uniform text matrix (x and y scale together), and `write_text`'s `matrix` argument is a single page-global transform applied to every run at once. Neither can carry a different horizontal scale per line.

The working design places each line with `page.insert_text(..., render_mode=3, morph=(baseline, Matrix(h_scale, 0, 0, 1, 0, 0)))`. The anisotropic matrix scales x while leaving y fixed; morphing about the baseline point pivots on the left edge, so position is preserved and only width changes.

### Trade-off

One `insert_text` per line means ~100 content-stream insertions on a dense page instead of one emit. That is the accepted cost of correct per-line width-fit. It embeds the font only once (subsequent calls reuse the registered `ocrfont`), so the per-line cost is the insertion, not re-embedding. If a real batch ever proves too slow, the fallback is grouping lines that share a horizontal-scale bucket into fewer emits — not needed unless measured.

## Why "strict on structure, tolerant of text"

OCR text is inherently noisy — garbled words like "Salte / page" are normal and expected. If the tool failed on bad text, it would fail on the everyday case it exists to serve. So text quality never fails a page: garbled text is placed verbatim, empty lines are skipped.

What *does* fail loudly (exit non-zero, write nothing) is **structural** breakage — unreadable/off-schema JSON, coordinates wildly outside 0–1, or a PDF that already has a text layer. These mean the JSON and PDF can't be reconciled, and in an automation pipeline that should stop and flag for a human rather than produce silently-wrong output.

This split matters because the tool feeds Power Automate, which branches on exit code alone. A garbled-but-present page is a success (exit 0); a page whose inputs don't reconcile is a failure (exit 1) the flow can route to review.

## Why a Unicode font is embedded, and why it won't fall back to Helvetica

The sample data is full of non-ASCII (German mill certificates: "Österreich", "Abnahmeprüfzeugnis"). A base-14 font like Helvetica lacks a proper `ToUnicode` map for those glyphs, so search and copy — the whole point of the feature — would silently break on exactly the text that needs them.

So the tool embeds a real Unicode TrueType font and **refuses** to fall back to a base-14 font: if no embeddable TTF is found it fails with a clear message. Failing loudly beats shipping a "searchable" PDF where the interesting words aren't searchable.

## Related

- [Reference: PDF Splitter CLI](reference-pdf-splitter-cli.md)
- [Reference: OCR Merge CLI](reference-ocr-merge-cli.md)
- [Tutorial: from scanned PDF to searchable PDF](tutorial-scan-to-searchable.md)

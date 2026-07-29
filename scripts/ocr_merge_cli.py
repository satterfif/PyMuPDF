#!/usr/bin/env python3
"""Merge OCR JSON onto an image-only PDF page to make it searchable.

Consumes existing OCR results (Microsoft Dynamics / Azure Read style JSON) with
line-level, normalized (0-1) bounding boxes and overlays an invisible,
searchable text layer onto the matching image PDF, producing ``final_<stem>.pdf``.

Standalone tool, mirroring ``scripts/pdf_splitter_cli.py``. Not part of the wheel.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

import pymupdf


# Coordinates outside [-COORD_TOLERANCE, 1 + COORD_TOLERANCE] are treated as a
# structural anomaly. A little slack absorbs rounding; 5.0 does not.
COORD_TOLERANCE = 0.05

# Clamp for the per-line horizontal scale so a one-character line in a wide box
# (or a near-zero-width box) cannot produce an absurd transform.
_MIN_HSCALE = 0.1
_MAX_HSCALE = 10.0

# Candidate Unicode-capable TTFs to embed, in preference order. The first that
# exists and loads is used. If none is available the tool fails loudly rather
# than silently falling back to a base-14 font with poor non-ASCII fidelity.
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


class OcrMergeError(Exception):
    """A user-facing OCR-merge error (structural anomaly or bad input)."""


# --- U1: OCR JSON schema adapter --------------------------------------------

class OcrLine:
    """One OCR line: text plus a normalized (0-1) bounding box."""

    __slots__ = ("text", "left", "top", "width", "height")

    def __init__(self, text, left, top, width, height):
        self.text = text
        self.left = left
        self.top = top
        self.width = width
        self.height = height


def _coerce_float(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OcrMergeError(
            f"Invalid OCR JSON: bounding-box '{field}' is not a number: {value!r}"
        )
    return float(value)


def parse_ocr_lines(data):
    """Parse Dynamics/Azure OCR JSON into a list of OcrLine records.

    *data* is the already-parsed JSON (a top-level list). Empty/whitespace lines
    are skipped. Structurally invalid input or out-of-range coordinates raise
    OcrMergeError. Garbled text is preserved verbatim.
    """
    if not isinstance(data, list) or not data:
        raise OcrMergeError(
            "Invalid OCR JSON: expected a non-empty top-level array"
        )

    page_obj = data[0]
    if not isinstance(page_obj, dict) or "lines" not in page_obj:
        raise OcrMergeError(
            "Invalid OCR JSON: first element has no 'lines' array"
        )

    raw_lines = page_obj["lines"]
    if not isinstance(raw_lines, list):
        raise OcrMergeError("Invalid OCR JSON: 'lines' is not an array")

    lines = []
    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            raise OcrMergeError(f"Invalid OCR JSON: line {index} is not an object")

        text = raw.get("text", "")
        if not isinstance(text, str):
            raise OcrMergeError(f"Invalid OCR JSON: line {index} 'text' is not a string")
        if not text.strip():
            continue

        box = raw.get("boundingBox")
        if not isinstance(box, dict):
            raise OcrMergeError(f"Invalid OCR JSON: line {index} has no boundingBox")

        try:
            left = _coerce_float(box["left"], "left")
            top = _coerce_float(box["top"], "top")
            width = _coerce_float(box["width"], "width")
            height = _coerce_float(box["height"], "height")
        except KeyError as error:
            raise OcrMergeError(
                f"Invalid OCR JSON: line {index} boundingBox missing {error}"
            ) from error

        for name, value in (("left", left), ("top", top),
                            ("width", width), ("height", height)):
            if value < -COORD_TOLERANCE or value > 1.0 + COORD_TOLERANCE:
                raise OcrMergeError(
                    f"Invalid OCR JSON: line {index} '{name}'={value} is outside "
                    f"the normalized 0-1 range"
                )

        lines.append(OcrLine(text, left, top, width, height))

    return lines


# --- U2: Coordinate mapping and width-fit core ------------------------------

class Placement:
    """Computed placement for one line: baseline point, font size, x-scale."""

    __slots__ = ("baseline_point", "fontsize", "h_scale")

    def __init__(self, baseline_point, fontsize, h_scale):
        self.baseline_point = baseline_point
        self.fontsize = fontsize
        self.h_scale = h_scale


def compute_placement(line, page_width, page_height, font):
    """Return a Placement for *line* against a page of the given size.

    Pure geometry, no PDF opened. The font size comes from the box height; the
    horizontal scale stretches the run to the box width. The scale is applied at
    emit time as a morph about the baseline point (Matrix(h_scale, 0, 0, 1, 0, 0)),
    which pivots on the left edge, so the baseline x needs no adjustment.
    """
    fontsize = line.height * page_height
    if fontsize <= 0:
        fontsize = 1.0  # degenerate zero-height box; keep a placeable run

    box_width_pt = line.width * page_width
    natural_width = font.text_length(line.text, fontsize=fontsize)

    if natural_width <= 0 or box_width_pt <= 0:
        h_scale = 1.0
    else:
        h_scale = box_width_pt / natural_width

    h_scale = max(_MIN_HSCALE, min(_MAX_HSCALE, h_scale))

    baseline_x = line.left * page_width
    baseline_y = (line.top + line.height) * page_height
    return Placement(pymupdf.Point(baseline_x, baseline_y), fontsize, h_scale)


# --- U3: Invisible text-layer writer ----------------------------------------

def resolve_font_path(font_path=None):
    """Return a usable Unicode-capable TTF path, or raise OcrMergeError.

    Uses *font_path* if given, otherwise the first existing system TTF. Fails
    loudly rather than falling back to a base-14 font, which would drop or
    mangle non-ASCII glyphs.
    """
    candidates = (font_path,) if font_path else _FONT_CANDIDATES
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    if font_path:
        raise OcrMergeError(f"Font file not found: {font_path}")
    raise OcrMergeError(
        "No Unicode-capable TTF font found. Pass --font <path-to-ttf> to specify one."
    )


def apply_text_layer(page, lines, font_path):
    """Overlay *lines* as an invisible, width-fitted text layer on *page*.

    Each line is placed with page.insert_text under render mode 3 and morphed by
    Matrix(h_scale, 0, 0, 1, 0, 0) about its baseline, so it carries its own
    horizontal scale while glyph height stays fixed. A custom fontname forces
    the TTF to embed so non-ASCII text round-trips (base-14 would drop it). The
    image content is untouched (overlay=True).

    Note: embedded-font extraction renders inter-word spaces as U+00A0
    (non-breaking space) in get_text(); MuPDF's search normalizes this, so
    searchability and copy-into-search are unaffected.
    """
    font = pymupdf.Font(fontfile=font_path)
    page_width = page.rect.width
    page_height = page.rect.height
    for line in lines:
        placement = compute_placement(line, page_width, page_height, font)
        page.insert_text(
            placement.baseline_point,
            line.text,
            fontsize=placement.fontsize,
            fontfile=font_path,
            fontname="ocrfont",
            render_mode=3,
            morph=(placement.baseline_point,
                   pymupdf.Matrix(placement.h_scale, 0, 0, 1, 0, 0)),
            overlay=True,
        )


# --- U4: CLI entry point and orchestration ----------------------------------

def _validate_paths(input_pdf, input_json, output_dir):
    input_pdf = Path(input_pdf).expanduser().resolve()
    if not input_pdf.is_file():
        raise OcrMergeError(f"Input PDF does not exist: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise OcrMergeError(f"Input file must be a PDF: {input_pdf}")

    input_json = Path(input_json).expanduser().resolve()
    if not input_json.is_file():
        raise OcrMergeError(f"Input JSON does not exist: {input_json}")

    if output_dir is None:
        output_dir = input_pdf.parent
    else:
        output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    return input_pdf, input_json, output_dir


def _load_json(input_json):
    try:
        with open(input_json, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise OcrMergeError(f"Could not read OCR JSON {input_json}: {error}") from error


def merge_ocr(input_pdf, input_json, output_dir=None, font_path=None):
    """Merge one OCR JSON onto one image PDF, writing final_<stem>.pdf.

    Returns the output path. Raises OcrMergeError on any structural anomaly,
    having written no output file.
    """
    input_pdf, input_json, output_dir = _validate_paths(input_pdf, input_json, output_dir)

    data = _load_json(input_json)
    lines = parse_ocr_lines(data)
    resolved_font = resolve_font_path(font_path)

    try:
        source = pymupdf.open(input_pdf)
    except Exception as error:  # noqa: BLE001
        raise OcrMergeError(f"Could not open PDF: {input_pdf}: {error}") from error

    output_path = output_dir / f"final_{input_pdf.stem}.pdf"
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with source:
            if source.needs_pass:
                raise OcrMergeError(
                    f"Password-protected PDF is not supported: {input_pdf}"
                )
            if source.page_count == 0:
                raise OcrMergeError(f"PDF contains no pages: {input_pdf}")

            page = source[0]
            if page.get_text("text").strip():
                raise OcrMergeError(
                    f"PDF already contains a text layer: {input_pdf}"
                )

            apply_text_layer(page, lines, resolved_font)
            source.save(temporary_path, garbage=3, deflate=True)
        os.replace(temporary_path, output_path)
    finally:
        Path(temporary_path).unlink(missing_ok=True)

    return output_path


def create_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Merge OCR JSON onto an image-only PDF page to produce a searchable "
            "final_<name>.pdf with an invisible text layer."
        )
    )
    parser.add_argument("input_pdf", help="Path to the image-only source PDF")
    parser.add_argument("input_json", help="Path to the OCR JSON for that page")
    parser.add_argument(
        "--output-dir",
        help="Output folder (default: the input PDF's directory)",
    )
    parser.add_argument(
        "--font",
        help="Path to a Unicode-capable TTF to embed (default: a system font)",
    )
    return parser


def main(argv=None):
    arguments = create_parser().parse_args(argv)
    try:
        output_path = merge_ocr(
            arguments.input_pdf,
            arguments.input_json,
            output_dir=arguments.output_dir,
            font_path=arguments.font,
        )
    except OcrMergeError as error:
        print(f"OCR merge failed: {error}", file=sys.stderr)
        return 1

    print(f"Wrote searchable PDF: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

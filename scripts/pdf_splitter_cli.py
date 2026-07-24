#!/usr/bin/env python3
"""Split a PDF into one single-page PDF per source page."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import sys
import uuid

import pymupdf


# Cap parallel workers — each opens its own doc handle and does I/O.
_MAX_WORKERS = min(8, max(1, os.cpu_count() or 4))

# Minimum page count to justify thread pool overhead.
# Below this, sequential is faster due to per-thread doc-open cost.
_PARALLEL_THRESHOLD = 50


class SplitterError(Exception):
    """A user-facing PDF splitting error."""


def parse_page_ranges(spec, page_count):
    """Parse a page range string like '1-5, 8, 10-15' into 0-based indices.

    Accepts comma-separated tokens, each being a single page number or a
    hyphen-separated range (inclusive on both ends, 1-based).
    """
    pages = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        match = re.match(r"^(\d+)\s*-\s*(\d+)$", token)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start < 1 or end > page_count or start > end:
                raise SplitterError(
                    f"Invalid page range '{token}': must be 1-{page_count}"
                )
            pages.extend(range(start - 1, end))
        elif token.isdigit():
            page_num = int(token)
            if page_num < 1 or page_num > page_count:
                raise SplitterError(
                    f"Page {page_num} out of range: document has {page_count} pages"
                )
            pages.append(page_num - 1)
        else:
            raise SplitterError(
                f"Invalid page specification '{token}': "
                f"use page numbers or ranges like '1-5, 8, 10-15'"
            )
    if not pages:
        raise SplitterError("No pages specified")
    return pages


def _validate_paths(input_path, output_dir):
    input_path = Path(input_path).expanduser().resolve()
    if not input_path.is_file():
        raise SplitterError(f"Input PDF does not exist: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        raise SplitterError(f"Input file must be a PDF: {input_path}")

    if output_dir is None:
        output_dir = input_path.with_suffix("") / "pages"
    else:
        output_dir = Path(output_dir).expanduser().resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    return input_path, output_dir


def _save_page(source_document, page_index, output_path):
    """Save a single page using a shared source document (sequential path)."""
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with pymupdf.open() as output_document:
            output_document.insert_pdf(
                source_document,
                from_page=page_index,
                to_page=page_index,
            )
            output_document.save(temporary_path, garbage=2, deflate=True)
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _save_page_parallel(source_path, page_index, output_path):
    """Save a single page using its own document handle (thread-safe)."""
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with pymupdf.open(source_path) as source_document:
            with pymupdf.open() as output_document:
                output_document.insert_pdf(
                    source_document,
                    from_page=page_index,
                    to_page=page_index,
                )
                output_document.save(temporary_path, garbage=2, deflate=True)
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _save_pages(source_document, page_indices, output_path):
    """Save multiple pages into a single output PDF."""
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with pymupdf.open() as output_document:
            for page_index in page_indices:
                output_document.insert_pdf(
                    source_document,
                    from_page=page_index,
                    to_page=page_index,
                )
            output_document.save(temporary_path, garbage=4, deflate=True)
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def split_pdf(input_path, output_dir=None, pages=None):
    """Split *input_path* into PDFs in the specified folder.

    The output folder is created automatically if it does not exist.
    If *pages* is provided (a page range string), extract only those pages
    into a single output file instead of splitting every page individually.
    """
    input_path, output_dir = _validate_paths(input_path, output_dir)

    try:
        source_document = pymupdf.open(input_path)
    except Exception as error:
        raise SplitterError(f"Could not open PDF: {input_path}: {error}") from error

    output_paths = []
    with source_document:
        if source_document.needs_pass:
            raise SplitterError(f"Password-protected PDF is not supported: {input_path}")
        if source_document.page_count == 0:
            raise SplitterError(f"PDF contains no pages: {input_path}")

        if pages:
            # Extract specific pages into a single output file
            page_indices = parse_page_ranges(pages, source_document.page_count)
            output_name = f"{input_path.stem}_pages.pdf"
            output_path = output_dir / output_name
            try:
                _save_pages(source_document, page_indices, output_path)
            except Exception as error:
                raise SplitterError(
                    f"Could not write pages to {output_path}: {error}"
                ) from error
            output_paths.append(output_path)
        else:
            # Split every page into individual files
            page_count = source_document.page_count
            number_width = max(3, len(str(page_count)))
            page_outputs = []
            for page_index in range(page_count):
                page_number = page_index + 1
                output_name = f"page_{page_number:0{number_width}d}.pdf"
                page_outputs.append((page_index, output_dir / output_name))

            if page_count >= _PARALLEL_THRESHOLD:
                # Parallel: each thread opens its own doc handle
                errors = {}
                with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(
                            _save_page_parallel, input_path, idx, path
                        ): (idx, path)
                        for idx, path in page_outputs
                    }
                    for future in as_completed(futures):
                        idx, path = futures[future]
                        exc = future.exception()
                        if exc:
                            errors[idx] = exc
                if errors:
                    first_idx = min(errors)
                    raise SplitterError(
                        f"Could not write page {first_idx + 1}: {errors[first_idx]}"
                    )
                output_paths = [path for _, path in page_outputs]
            else:
                # Sequential for small PDFs
                for page_index, output_path in page_outputs:
                    try:
                        _save_page(source_document, page_index, output_path)
                    except Exception as error:
                        raise SplitterError(
                            f"Could not write page {page_index + 1} to {output_path}: {error}"
                        ) from error
                    output_paths.append(output_path)

    return output_paths


def create_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Split a PDF into one file per page. By default, output is written "
            "to an existing sibling folder named after the input file."
        )
    )
    parser.add_argument("input_pdf", help="Path to the source PDF")
    parser.add_argument(
        "--output-dir",
        help="Existing output folder (default: input path without .pdf)",
    )
    parser.add_argument(
        "--pages",
        help="Page range to extract, e.g. '1-5, 8, 10-15' (produces one output file)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON to stdout",
    )
    return parser


def main(argv=None):
    arguments = create_parser().parse_args(argv)
    try:
        output_paths = split_pdf(
            arguments.input_pdf,
            arguments.output_dir,
            pages=arguments.pages,
        )
    except SplitterError as error:
        if arguments.json_output:
            json.dump(
                {"status": "error", "message": str(error)},
                sys.stdout,
                indent=2,
            )
            print()
        else:
            print(f"PDF split failed: {error}", file=sys.stderr)
        return 1

    if arguments.json_output:
        result = {
            "status": "ok",
            "input": str(Path(arguments.input_pdf).resolve()),
            "pages": len(output_paths),
            "output_dir": str(output_paths[0].parent),
            "files": [str(p) for p in output_paths],
        }
        json.dump(result, sys.stdout, indent=2)
        print()
    else:
        print(
            f"Split {arguments.input_pdf} into {len(output_paths)} file(s) "
            f"in {output_paths[0].parent}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

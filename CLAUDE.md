# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyMuPDF is a Python binding for MuPDF — a high-performance PDF/document rendering engine by Artifex. The package is published as `pymupdf` on PyPI (the legacy `fitz` import still works but is deprecated). Version is generated at build time into `src/_build.py`.

## Build & Development

### Prerequisites
- Python 3.10–3.14 (`.python-version` specifies 3.12)
- SWIG and libclang (auto-handled during build)
- MuPDF is downloaded automatically during build unless overridden

### Building
```bash
# Standard install (downloads MuPDF automatically)
pip install .

# Developer build/test script (auto-creates venv if needed)
python scripts/test.py build

# Build with local MuPDF checkout
python scripts/test.py -m mupdf build

# Debug build
python scripts/test.py -b debug build
```

### Testing
```bash
# Run full test suite (after building)
pytest tests/

# Run a single test file
pytest tests/test_general.py

# Run a specific test function
pytest tests/test_general.py::test_haslinks

# Run tests matching a pattern
pytest -k "test_haslinks"

# Build + test via dev script
python scripts/test.py build test

# Dev script with test filter
python scripts/test.py test -k test_haslinks
```

Test dependencies are installed automatically by `tests/conftest.py` on first run: pytest, fontTools, pymupdf-fonts, flake8, pylint, codespell, mypy, pipcl, pillow, psutil.

### Linting
```bash
pytest tests/test_flake8.py    # flake8
pytest tests/test_pylint.py    # pylint
pytest tests/test_codespell.py # codespell
```

### Docs
```bash
# Build Sphinx HTML docs (run from docs/)
sphinx-build -b html . build/html
```

## Architecture

### Two implementations
- **`src/`** — Current "rebased" implementation built on MuPDF's C++ Python bindings. This is the active codebase.
- **`src_classic/`** — Legacy SWIG-based implementation. Kept for reference only.

### Key source files in `src/`
| File | Role |
|------|------|
| `__init__.py` (~950KB) | Core module: all main classes (Document, Page, Pixmap, TextPage, etc.) |
| `extra.i` | SWIG interface for the small C extension (`extra`) used by the rebased impl |
| `table.py` (~112KB) | Table detection and extraction engine |
| `_table_refine.py`, `_table_spans.py`, `_table_union.py`, `_table_headers.py` | Table processing sub-modules |
| `utils.py` | Utility functions |
| `_apply_pages.py` | Multiprocessing helper for concurrent page processing |
| `_wxcolors.py` | Named color definitions |
| `pymupdf.py` | Re-export shim (`from . import *`) |
| `fitz_table.py`, `fitz_utils.py` | Legacy `fitz.*` import shims |
| `__main__.py` | CLI entry point (`pymupdf` command) |
| `fitz___init__.py` | Legacy `import fitz` compatibility shim |

### Build system
- `pyproject.toml` declares `pipcl` as the PEP 517 build backend
- `setup.py` (53KB) handles: MuPDF download/build, SWIG extension compilation, wheel packaging
- `scripts/test.py` is the developer build/test orchestrator (auto-venv, build, test, cibuildwheel)

### PDF Splitter tooling (`scripts/`)
A standalone CLI tool (separate from the core binding) that splits a PDF into
one single-page PDF per page, emitting structured JSON for automation
(e.g. Power Automate Desktop). Not part of the built wheel.

| File | Role |
|------|------|
| `scripts/pdf_splitter_cli.py` | CLI entry point; page-range parsing, parallel splitting |
| `scripts/ocr_merge_cli.py` | CLI that overlays an invisible OCR text layer (Dynamics/Azure JSON) onto an image PDF to make it searchable |
| `scripts/pdf_splitter_gui.py` | `uv`-run Flask GUI for local testing (PEP 723 inline deps) |
| `scripts/start-splitter-gui.bat` | Windows launcher for the GUI |
| `tests/test_pdf_splitter_cli.py` | Splitter tests (loads the CLI via `importlib`) |
| `tests/test_ocr_merge_cli.py` | OCR merge tests (loads the CLI via `importlib`) |
| `release/PDFSplitter-Portable/` | PyInstaller portable exe + Power Automate setup docs |
| `docs/tooling/` | Full Diataxis docs for both CLIs (tutorial, how-tos, reference, design) |

- Docs: `docs/tooling/README.md` (start there) — Diataxis tutorial/how-to/reference/explanation for both CLIs
- Run tests: `pytest tests/test_pdf_splitter_cli.py` and `pytest tests/test_ocr_merge_cli.py`
- Run the GUI: `scripts/start-splitter-gui.bat` (or `uv run scripts/pdf_splitter_gui.py`)
- Uses `ThreadPoolExecutor` intentionally for I/O-bound splitting — each worker
  opens its own doc handle. This is the documented exception to the
  "no multithreading" rule below.

### Test conventions
- Tests live in `tests/test_*.py`; resources in `tests/resources/`
- Regression tests are named by issue number (e.g., `test_4936.py`)
- `conftest.py` provides an `autouse` fixture that validates: empty MuPDF warnings buffer, no `_globals` mutations, stable `JM_annot_id_stem`, no `log()` calls, no `set_small_glyph_heights()` left set. FD leak detection runs on Linux but currently only logs (does not fail).
- Config: `pytest.ini` at repo root

### Key environment variables
| Variable | Purpose |
|----------|---------|
| `PYMUPDF_SETUP_MUPDF_BUILD` | Override MuPDF source location |
| `PYMUPDF_SETUP_MUPDF_BUILD_TYPE` | `release` (default), `debug`, or `memento` |
| `PYMUPDF_SETUP_MUPDF_TESSERACT` | Set to `0` to disable Tesseract OCR |
| `PYMUPDF_SETUP_PY_LIMITED_API` | If not `0`, build for Python stable ABI |

## Documented Solutions

`docs/solutions/` — documented solutions to past problems and tooling decisions, organized by category with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas.

## Important Notes

- `import pymupdf` is the canonical import; `import fitz` is deprecated
- The core `src/__init__.py` is enormous (~950KB) — most PyMuPDF classes live in this single file
- Core binding: no multithreading — use multiprocessing for parallel document work. (Exception: the standalone PDF Splitter CLI uses threads for I/O-bound page splitting with per-thread doc handles.)
- `scripts/test.py` auto-creates a venv if not already inside one

## Code Style

- No type annotations in core `src/__init__.py` — match the existing untyped style
- `# noqa` comments suppress specific flake8/pylint warnings where intentional
- Legacy shim files use `from X import *` patterns — leave them as-is
- Test functions named `test_NNNN` correspond to GitHub issue numbers

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec

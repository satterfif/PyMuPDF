# Repository Guidelines

## Project Structure & Module Organization

PyMuPDF is a Python binding for the MuPDF document engine. Active package code
lives in `src/`; core APIs are concentrated in `src/__init__.py`, while table
extraction is split across `table.py` and `_table_*.py`. Treat `src_classic/` as
legacy reference code unless a change explicitly targets the classic build.
Tests are under `tests/`, with fixtures and sample documents in
`tests/resources/`. Sphinx documentation lives in `docs/`, including static
assets in `docs/_static/`. Build and release helpers are in `scripts/`.

## Build, Test, and Development Commands

- `python -m pip install .` builds and installs the package through the
  `pipcl` PEP 517 backend; MuPDF is downloaded during the build by default.
- `python scripts/test.py build test` creates a development environment as
  needed, builds PyMuPDF, and runs the test suite.
- `pytest tests/test_general.py::test_haslinks` runs one focused test; use
  `pytest -k haslinks` for name-based filtering.
- `pytest tests/test_flake8.py tests/test_pylint.py tests/test_codespell.py`
  runs the repository's Python quality checks.
- From `docs/`, `sphinx-build -b html . build/html` builds the documentation.

Use Python 3.10–3.14; `.python-version` selects 3.12 for local tooling.

## Coding Style & Naming Conventions

Follow the surrounding Python style: four-space indentation, `snake_case` for
functions and variables, `PascalCase` for classes, and descriptive module
names. Prefer `import pymupdf`; the `fitz` import is deprecated. Keep changes
focused because several source modules are intentionally large. Flake8 and
Pylint rules are encoded in their corresponding tests, including documented
project-specific exclusions. Write documentation in reStructuredText and use
the substitutions defined in `docs/header.rst` for product names.

## Testing Guidelines

Add pytest tests as `tests/test_*.py`. Name issue regressions after the issue
when useful, for example `test_4936.py`, and keep reusable inputs in
`tests/resources/`. Run the narrowest relevant test first, then the full suite
for broad or core changes. There is no stated numeric coverage threshold;
regression behavior and platform compatibility are the priority.

## Commit & Pull Request Guidelines

Recent commits use concise, imperative summaries, often prefixed by scope:
`src/table.py: fix empty table handling` or `tests/: add test_4936()`. Reference
issues (`#4670`) when applicable. Pull requests should target `main`, explain
the user-visible effect, link related issues, and list exact tests run. Include
screenshots or rendered output for visual documentation changes, and keep
unrelated refactors in separate changes.

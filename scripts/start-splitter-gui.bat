@echo off
cd /d "%~dp0"
set OPEN_BROWSER=1
set UV_LINK_MODE=copy
uv run pdf_splitter_gui.py
pause

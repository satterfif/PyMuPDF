# /// script
# requires-python = ">=3.10"
# dependencies = ["flask", "pymupdf"]
# ///
"""Flask-based testing GUI for the PDF Splitter CLI."""

import os
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_splitter_cli import split_pdf, SplitterError

APP_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = APP_ROOT / "scripts" / "splitter_gui" / "templates"
STATIC_DIR = APP_ROOT / "scripts" / "splitter_gui" / "static"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "pdf_splitter_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR),
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

JOBS = {}
JOBS_LOCK = threading.Lock()


def set_job(job_id, **values):
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {}).update(values)


def process_split(job_id, source, output_dir):
    started_at = time.time()
    try:
        import pymupdf
        doc = pymupdf.open(source)
        total = doc.page_count
        doc.close()

        set_job(
            job_id,
            status="processing",
            total=total,
            current=0,
            progress=0,
            elapsed_seconds=0,
            message=f"Splitting {total} pages...",
        )

        output_paths = split_pdf(source, output_dir)

        elapsed = round(time.time() - started_at, 1)
        set_job(
            job_id,
            status="done",
            progress=100,
            current=len(output_paths),
            elapsed_seconds=elapsed,
            output_count=len(output_paths),
            output_dir=str(output_paths[0].parent) if output_paths else str(output_dir),
            message=f"Split into {len(output_paths)} file(s)",
        )
    except SplitterError as exc:
        set_job(
            job_id,
            status="error",
            elapsed_seconds=round(time.time() - started_at, 1),
            message=str(exc),
        )
    except Exception as exc:
        set_job(
            job_id,
            status="error",
            elapsed_seconds=round(time.time() - started_at, 1),
            message=f"Unexpected error: {exc}",
        )


@app.get("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def handle_upload():
    """Accept a PDF file upload and save it to a temp location."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "message": "No file uploaded"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "message": "File must be a PDF"}), 400

    # Save with a unique prefix to avoid collisions
    safe_name = Path(file.filename).name
    upload_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    file.save(upload_path)
    return jsonify({"ok": True, "source": str(upload_path), "name": safe_name})


@app.route("/api/split", methods=["POST"])
def api_split():
    payload = request.get_json(silent=True) or {}
    source = payload.get("source")
    output_dir = payload.get("output_dir")

    if not source:
        return jsonify({"ok": False, "message": "No source PDF specified"}), 400

    source_path = Path(source)
    if not source_path.is_file():
        return jsonify({"ok": False, "message": f"File not found: {source}"}), 400

    if output_dir:
        output_path = Path(output_dir)
        if not output_path.is_dir():
            return jsonify({"ok": False, "message": f"Output folder does not exist: {output_dir}"}), 400
    else:
        # Default: create a temp output folder named after the PDF
        output_path = UPLOAD_DIR / source_path.stem
        output_path.mkdir(exist_ok=True)

    job_id = uuid.uuid4().hex
    set_job(
        job_id,
        status="queued",
        progress=0,
        current=0,
        total=0,
        elapsed_seconds=0,
        source=str(source_path),
        output_dir=str(output_path),
        message="Queued",
    )
    worker = threading.Thread(
        target=process_split,
        args=(job_id, str(source_path), output_path),
        daemon=True,
    )
    worker.start()
    return jsonify({"ok": True, "job_id": job_id})


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)


if __name__ == "__main__":
    if os.environ.get("OPEN_BROWSER") == "1":
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8766")).start()
    app.run(host="127.0.0.1", port=8766, threaded=True)

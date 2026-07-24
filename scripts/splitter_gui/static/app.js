const dropzone = document.querySelector("#dropzone");
const fileInput = document.querySelector("#fileInput");
const uploadBtn = document.querySelector("#uploadBtn");
const splitBtn = document.querySelector("#splitBtn");
const outputPath = document.querySelector("#outputPath");
const fileName = document.querySelector("#fileName");
const progressBox = document.querySelector("#progressBox");
const result = document.querySelector("#result");
const error = document.querySelector("#error");
const message = document.querySelector("#message");
const percent = document.querySelector("#percent");
const bar = document.querySelector("#bar");
const summary = document.querySelector("#summary");
const savedDir = document.querySelector("#savedDir");
const elapsed = document.querySelector("#elapsed");
const pageCount = document.querySelector("#pageCount");
const status = document.querySelector("#status");

let timer = null;
let displayedElapsed = 0;
let uploadedSource = null;

// Upload button click
uploadBtn.addEventListener("click", event => {
  event.stopPropagation();
  fileInput.click();
});

// File input change
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) handleFile(file);
});

// Drag and drop
dropzone.addEventListener("dragover", event => {
  event.preventDefault();
  dropzone.classList.add("drag-over");
});

dropzone.addEventListener("dragleave", event => {
  if (!dropzone.contains(event.relatedTarget)) {
    dropzone.classList.remove("drag-over");
  }
});

dropzone.addEventListener("drop", event => {
  event.preventDefault();
  dropzone.classList.remove("drag-over");
  const file = event.dataTransfer?.files?.[0];
  if (file) handleFile(file);
});

// Split button
splitBtn.addEventListener("click", startSplit);

async function handleFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showError("Please select a PDF file.");
    return;
  }

  error.classList.add("hidden");
  result.classList.add("hidden");
  fileName.textContent = `Uploading: ${file.name}...`;
  splitBtn.disabled = true;

  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/upload", { method: "POST", body: formData });
    const body = await response.json();

    if (!body.ok) {
      showError(body.message || "Upload failed");
      fileName.textContent = "Click or drag a PDF file here";
      return;
    }

    uploadedSource = body.source;
    fileName.textContent = body.name;
    splitBtn.disabled = false;
  } catch (e) {
    showError(e.message);
    fileName.textContent = "Click or drag a PDF file here";
  }
}

async function startSplit() {
  if (!uploadedSource) return;
  error.classList.add("hidden");
  result.classList.add("hidden");
  splitBtn.disabled = true;

  const payload = { source: uploadedSource };
  if (outputPath.value.trim()) payload.output_dir = outputPath.value.trim();

  try {
    const response = await fetch("/api/split", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!body.ok) {
      showError(body.message || "Split failed");
      splitBtn.disabled = false;
      return;
    }

    progressBox.classList.remove("hidden");
    displayedElapsed = 0;
    updateTimeDisplay();
    clearInterval(timer);
    timer = setInterval(() => {
      displayedElapsed += 1;
      updateTimeDisplay();
    }, 1000);
    poll(body.job_id);
  } catch (e) {
    showError(e.message);
    splitBtn.disabled = false;
  }
}

async function poll(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || "Job not found");
    renderJob(job);
    if (job.status === "done") {
      clearInterval(timer);
      splitBtn.disabled = false;
      return;
    }
    if (job.status === "error") {
      throw new Error(job.message || "Processing failed");
    }
    setTimeout(() => poll(jobId), 500);
  } catch (e) {
    showError(e.message);
    splitBtn.disabled = false;
  }
}

function renderJob(job) {
  message.textContent = job.message || "Processing...";
  displayedElapsed = Math.max(displayedElapsed, job.elapsed_seconds || 0);
  updateTimeDisplay();
  percent.textContent = `${job.progress || 0}%`;
  bar.style.width = `${job.progress || 0}%`;
  pageCount.textContent = job.total ? `${job.current || 0} / ${job.total}` : "--";
  status.textContent = job.status === "done" ? "Complete" : job.status === "error" ? "Failed" : "Processing";

  if (job.status === "done") {
    summary.textContent = `Split into ${job.output_count} file(s) in ${formatDuration(job.elapsed_seconds)}`;
    savedDir.textContent = `Output: ${job.output_dir}`;
    result.classList.remove("hidden");
  }
}

function showError(text) {
  clearInterval(timer);
  error.textContent = text;
  error.classList.remove("hidden");
  splitBtn.disabled = !uploadedSource;
}

function updateTimeDisplay() {
  elapsed.textContent = formatDuration(displayedElapsed);
}

function formatDuration(seconds) {
  const value = Math.max(0, Math.round(seconds || 0));
  const minutes = Math.floor(value / 60);
  const secs = value % 60;
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

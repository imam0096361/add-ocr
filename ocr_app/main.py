from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .docx_builder import export_all
from .models import DocumentLayout
from .ocr import extract_layout
from .pdf_render import render_pdf_pages
from .settings import api_key_source, clear_api_key, masked_api_key, save_api_key
from .storage import (
    DEMO_DIRECT_MATTER,
    JOBS_DIR,
    create_job_dir,
    ensure_dirs,
    list_jobs,
    read_layout,
    save_demo_pdf,
    save_upload,
    write_layout,
    write_meta,
)
from .validation import validate_layout


app = FastAPI(title="OCR to Editable Word")
ensure_dirs()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")


@app.get("/api/demo-pdfs")
def demo_pdfs() -> list[dict[str, str]]:
    if not DEMO_DIRECT_MATTER.exists():
        return []
    return [{"name": p.name, "path": str(p)} for p in sorted(DEMO_DIRECT_MATTER.glob("*.pdf"))]


@app.get("/api/jobs")
def jobs() -> list[dict[str, str]]:
    return list_jobs()


@app.get("/api/settings")
def settings() -> dict[str, object]:
    masked = masked_api_key()
    return {"has_gemini_api_key": bool(masked), "masked_gemini_api_key": masked, "source": api_key_source()}


@app.post("/api/settings/gemini-key")
async def save_gemini_key(payload: dict[str, str]) -> dict[str, object]:
    api_key = (payload.get("api_key") or "").strip()
    if len(api_key) < 12:
        raise HTTPException(status_code=400, detail="Gemini API key is too short.")
    save_api_key(api_key)
    return settings()


@app.delete("/api/settings/gemini-key")
def delete_gemini_key() -> dict[str, object]:
    clear_api_key()
    return settings()


@app.post("/api/jobs")
async def create_job(
    file: UploadFile | None = File(default=None),
    demo_pdf: str | None = Form(default=None),
    model: str = Form(default="gemini-3-flash-preview"),
    force_demo: bool = Form(default=False),
) -> dict[str, object]:
    job_dir = create_job_dir()
    if demo_pdf:
        source = (DEMO_DIRECT_MATTER / demo_pdf).resolve()
        if not source.exists() or DEMO_DIRECT_MATTER.resolve() not in source.parents:
            raise HTTPException(status_code=404, detail="Demo PDF not found.")
        pdf_path = save_demo_pdf(job_dir, source)
        filename = source.name
    elif file:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Upload a PDF file.")
        pdf_path = save_upload(job_dir, file.filename, await file.read())
        filename = file.filename
    else:
        raise HTTPException(status_code=400, detail="Upload a PDF or choose a demo PDF.")

    write_meta(job_dir, filename=filename, status="processing")
    pages = render_pdf_pages(pdf_path, job_dir / "pages")
    layout = extract_layout(pdf_path, pages, model=model, force_demo=force_demo)
    layout.warnings = validate_layout(layout)
    write_layout(job_dir, layout)
    write_meta(job_dir, filename=filename, status="ready")
    return {"job_id": job_dir.name, "layout": layout.model_dump()}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job_dir = _job_dir(job_id)
    layout = read_layout(job_dir)
    return {"job_id": job_id, "layout": layout.model_dump()}


@app.put("/api/jobs/{job_id}/layout")
async def update_layout(job_id: str, payload: dict) -> dict[str, object]:
    job_dir = _job_dir(job_id)
    try:
        layout = DocumentLayout.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    layout.warnings = validate_layout(layout)
    write_layout(job_dir, layout)
    return {"job_id": job_id, "layout": layout.model_dump()}


@app.post("/api/jobs/{job_id}/export")
def export_job(job_id: str, include_bijoy: bool = True) -> dict[str, object]:
    job_dir = _job_dir(job_id)
    layout = read_layout(job_dir)
    result = export_all(layout, job_dir / "exports", include_bijoy=include_bijoy)
    return result


@app.get("/api/jobs/{job_id}/download/{name}")
def download(job_id: str, name: str) -> FileResponse:
    job_dir = _job_dir(job_id)
    allowed = {
        "faithful": job_dir / "exports" / "faithful.docx",
        "editable-faithful": job_dir / "exports" / "editable-faithful.docx",
        "column-ready": job_dir / "exports" / "column-ready.docx",
        "bijoy": job_dir / "exports" / "column-ready-bijoy.docx",
    }
    path = allowed.get(name)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Export not found. Run export first.")
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/api/jobs/{job_id}/page/{page_name}")
def page_image(job_id: str, page_name: str) -> FileResponse:
    job_dir = _job_dir(job_id)
    path = (job_dir / "pages" / page_name).resolve()
    if not path.exists() or (job_dir / "pages").resolve() not in path.parents:
        raise HTTPException(status_code=404, detail="Page image not found.")
    return FileResponse(path)


def _job_dir(job_id: str) -> Path:
    if not job_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid job id.")
    job_dir = (JOBS_DIR / job_id).resolve()
    if not job_dir.exists() or JOBS_DIR.resolve() not in job_dir.parents:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_dir


@app.exception_handler(Exception)
async def unhandled_exception(_, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})

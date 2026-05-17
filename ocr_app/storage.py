from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from .models import DocumentLayout


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
DEMO_DIRECT_MATTER = ROOT / "abc" / "Direct Matter"
DEMO_PREPARE_MATTER = ROOT / "abc" / "Prepare Matter"


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def create_job_dir() -> Path:
    ensure_dirs()
    job_dir = JOBS_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True)
    (job_dir / "pages").mkdir()
    (job_dir / "artifacts").mkdir()
    (job_dir / "exports").mkdir()
    return job_dir


def save_upload(job_dir: Path, filename: str, data: bytes) -> Path:
    suffix = Path(filename).suffix.lower() or ".pdf"
    dest = job_dir / f"input{suffix}"
    dest.write_bytes(data)
    return dest


def save_demo_pdf(job_dir: Path, source: Path) -> Path:
    dest = job_dir / source.name
    shutil.copy2(source, dest)
    return dest


def layout_path(job_dir: Path) -> Path:
    return job_dir / "layout.json"


def write_layout(job_dir: Path, layout: DocumentLayout) -> None:
    layout_path(job_dir).write_text(layout.model_dump_json(indent=2), encoding="utf-8")


def read_layout(job_dir: Path) -> DocumentLayout:
    return DocumentLayout.model_validate_json(layout_path(job_dir).read_text(encoding="utf-8"))


def list_jobs() -> list[dict[str, str]]:
    ensure_dirs()
    items: list[dict[str, str]] = []
    for path in sorted(JOBS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        meta_path = path / "meta.json"
        meta = {"id": path.name, "filename": "unknown"}
        if meta_path.exists():
            meta.update(json.loads(meta_path.read_text(encoding="utf-8")))
        items.append(meta)
    return items


def write_meta(job_dir: Path, **meta: str) -> None:
    (job_dir / "meta.json").write_text(json.dumps({"id": job_dir.name, **meta}, indent=2), encoding="utf-8")

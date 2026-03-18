from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .models import ApprovalRequest, JobCreate, JobRunRequest
from . import repository as repo
from .runner import approve_and_continue, start_job

app = FastAPI(title="Dashboard Orchestrator MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def api_hello() -> dict[str, str]:
    return {"message": "Hello from the Dashboard Orchestrator!"}


@app.get("/api/jobs")
def api_list_jobs() -> list[dict]:
    return repo.list_jobs()


@app.post("/api/jobs")
def api_create_job(payload: JobCreate) -> dict:
    job_id = repo.create_job(payload.model_dump())
    job = repo.get_job(job_id)
    assert job is not None
    return job


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: int) -> dict:
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/run")
def api_run_job(job_id: int, payload: JobRunRequest | None = None) -> dict:
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    ok = start_job(job_id, reset=(payload.reset_failed_steps if payload else True))
    if not ok:
        raise HTTPException(status_code=409, detail="Job is already running")
    return {"started": True, "job_id": job_id}


@app.post("/api/jobs/{job_id}/approve")
def api_approve_job(job_id: int, payload: ApprovalRequest) -> dict:
    ok = approve_and_continue(job_id, payload.approved)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "approved": payload.approved}

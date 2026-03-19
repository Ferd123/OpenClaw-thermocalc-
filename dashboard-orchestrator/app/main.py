from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import repository as repo
from .database import init_db
from .model_exec import ModelExecutionError, execute_model
from .models import (
    ApprovalRequest,
    CompareRequest,
    JobCreate,
    JobRunRequest,
    RerunRequest,
    RunCreate,
    SelectRunRequest,
    SessionCreate,
    TaskCreate,
)
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
    repo.seed_v2_catalog()


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


@app.get("/api/v2/providers")
def api_v2_list_providers() -> list[dict]:
    return repo.list_providers()


@app.get("/api/v2/models")
def api_v2_list_models() -> list[dict]:
    return repo.list_models()


@app.get("/api/v2/metrics/summary")
def api_v2_metrics_summary() -> dict:
    return repo.get_metrics_summary()


@app.get("/api/v2/sessions")
def api_v2_list_sessions(include_archived: bool = False) -> list[dict]:
    return repo.list_sessions(include_archived=include_archived)


@app.post("/api/v2/sessions")
def api_v2_create_session(payload: SessionCreate) -> dict:
    session_id = repo.create_session(payload.model_dump())
    session = repo.get_session(session_id)
    assert session is not None
    return session


@app.get("/api/v2/sessions/{session_id}")
def api_v2_get_session(session_id: int) -> dict:
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/api/v2/sessions/{session_id}/archive")
def api_v2_archive_session(session_id: int) -> dict:
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    repo.archive_session(session_id)
    return {"ok": True, "status": "archived", "session_id": session_id}


@app.delete("/api/v2/sessions/{session_id}")
def api_v2_delete_session(session_id: int) -> dict:
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    repo.delete_session(session_id)
    return {"ok": True, "deleted": True, "session_id": session_id}


@app.get("/api/v2/tasks")
def api_v2_list_tasks(session_id: int | None = None, include_archived: bool = False) -> list[dict]:
    return repo.list_tasks(session_id=session_id, include_archived=include_archived)


@app.post("/api/v2/tasks")
def api_v2_create_task(payload: TaskCreate) -> dict:
    session = repo.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    task_id = repo.create_task(payload.model_dump())
    task = repo.get_task(task_id)
    assert task is not None
    return task


@app.get("/api/v2/tasks/{task_id}")
def api_v2_get_task(task_id: int) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/v2/tasks/{task_id}/archive")
def api_v2_archive_task(task_id: int) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    repo.archive_task(task_id)
    return {"ok": True, "status": "archived", "task_id": task_id}


@app.delete("/api/v2/tasks/{task_id}")
def api_v2_delete_task(task_id: int) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    repo.delete_task(task_id)
    return {"ok": True, "deleted": True, "task_id": task_id}


@app.get("/api/v2/tasks/{task_id}/runs")
def api_v2_list_runs(task_id: int) -> list[dict]:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return repo.list_runs(task_id)


@app.post("/api/v2/tasks/{task_id}/runs")
def api_v2_create_run(task_id: int, payload: RunCreate) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    input_text = payload.input or task["input"]
    run_id = repo.create_run(
        task_id,
        {
            "provider": payload.provider,
            "model": payload.model,
            "input": input_text,
            "prompt_snapshot": payload.prompt_snapshot or input_text,
            "status": "pending",
            "output": payload.output,
            "error": payload.error,
            "latency_ms": payload.latency_ms,
            "cost_estimate": payload.cost_estimate,
            "tokens_in": payload.tokens_in,
            "tokens_out": payload.tokens_out,
        },
    )

    if payload.execute:
        repo.update_run(run_id, status="running", started_at=repo.now_iso())
        try:
            result = execute_model(payload.provider, payload.model, input_text)
            repo.update_run(
                run_id,
                status="success",
                output=result.output,
                latency_ms=result.latency_ms,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_estimate=result.cost_estimate,
                error_message=None,
                finished_at=repo.now_iso(),
            )
        except ModelExecutionError as exc:
            repo.update_run(
                run_id,
                status="error",
                error_message=str(exc),
                finished_at=repo.now_iso(),
            )

    run = repo.get_run(run_id)
    task = repo.get_task(task_id)
    assert run is not None and task is not None
    return {"run": run, "task": task}


@app.delete("/api/v2/runs/{run_id}")
def api_v2_delete_run(run_id: int) -> dict:
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    repo.delete_run(run_id)
    return {"ok": True, "deleted": True, "run_id": run_id}


@app.post("/api/v2/runs/{run_id}/rerun")
def api_v2_rerun(run_id: int, payload: RerunRequest) -> dict:
    original = repo.get_run(run_id)
    if not original:
        raise HTTPException(status_code=404, detail="Run not found")
    task = repo.get_task(original["task_id"])
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    new_run_id = repo.create_run(
        original["task_id"],
        {
            "provider": original["provider"],
            "model": original["model"],
            "input": original.get("input_text") or task["input"],
            "prompt_snapshot": original.get("prompt_snapshot") or original.get("input_text") or task["input"],
            "status": "pending",
        },
    )
    if payload.execute:
        repo.update_run(new_run_id, status="running", started_at=repo.now_iso())
        try:
            result = execute_model(original["provider"], original["model"], original.get("input_text") or task["input"])
            repo.update_run(
                new_run_id,
                status="success",
                output=result.output,
                latency_ms=result.latency_ms,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_estimate=result.cost_estimate,
                finished_at=repo.now_iso(),
                error_message=None,
            )
        except ModelExecutionError as exc:
            repo.update_run(new_run_id, status="error", error_message=str(exc), finished_at=repo.now_iso())
    run = repo.get_run(new_run_id)
    assert run is not None
    return {"run": run, "source_run_id": run_id}


@app.post("/api/v2/tasks/{task_id}/selected-run")
def api_v2_set_selected_run(task_id: int, payload: SelectRunRequest) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    run_ids = {run["id"] for run in task["runs"]}
    if payload.run_id not in run_ids:
        raise HTTPException(status_code=404, detail="Run not found for task")
    repo.select_run(task_id, payload.run_id)
    task = repo.get_task(task_id)
    assert task is not None
    return task


@app.post("/api/v2/tasks/{task_id}/compare")
def api_v2_compare_task(task_id: int, payload: CompareRequest) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    created_runs: list[dict] = []
    for item in payload.models:
        run_id = repo.create_run(
            task_id,
            {
                "provider": item.provider,
                "model": item.model,
                "input": task["input"],
                "prompt_snapshot": task["input"],
                "status": "pending",
            },
        )
        if payload.execute:
            repo.update_run(run_id, status="running", started_at=repo.now_iso())
            try:
                result = execute_model(item.provider, item.model, task["input"])
                repo.update_run(
                    run_id,
                    status="success",
                    output=result.output,
                    latency_ms=result.latency_ms,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_estimate=result.cost_estimate,
                    error_message=None,
                    finished_at=repo.now_iso(),
                )
            except ModelExecutionError as exc:
                repo.update_run(run_id, status="error", error_message=str(exc), finished_at=repo.now_iso())
        run = repo.get_run(run_id)
        if run:
            created_runs.append(run)

    return {"task_id": task_id, "runs": created_runs}

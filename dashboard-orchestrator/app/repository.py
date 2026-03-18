from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .database import get_conn, row_to_dict, rows_to_dicts


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------
# Legacy MVP repository
# -----------------------------

def create_job(payload: dict[str, Any]) -> int:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (title, description, status, requires_approval, current_step, approved_for_step2, final_result, error, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, 0, 0, NULL, NULL, ?, ?)
            """,
            (payload["title"], payload["description"], int(payload["requires_approval"]), ts, ts),
        )
        job_id = cur.lastrowid
        for i, step in enumerate(payload["steps"], start=1):
            conn.execute(
                """
                INSERT INTO job_steps (job_id, step_order, name, agent, prompt, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (job_id, i, step["name"], step["agent"], step["prompt"]),
            )
        conn.execute(
            "INSERT INTO job_logs (job_id, step_order, level, message, created_at) VALUES (?, NULL, 'info', 'Job created', ?)",
            (job_id, now_iso()),
        )
        return int(job_id)


def list_jobs() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    return rows_to_dicts(rows)


def get_job(job_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        job = row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
        if not job:
            return None
        steps = rows_to_dicts(conn.execute("SELECT * FROM job_steps WHERE job_id = ? ORDER BY step_order", (job_id,)).fetchall())
        logs = rows_to_dicts(conn.execute("SELECT * FROM job_logs WHERE job_id = ? ORDER BY id", (job_id,)).fetchall())
    job["steps"] = steps
    job["logs"] = logs
    return job


def update_job(job_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now_iso()
    clauses = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {clauses} WHERE id = ?", values)


def update_step(job_id: int, step_order: int, **fields: Any) -> None:
    if not fields:
        return
    clauses = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [job_id, step_order]
    with get_conn() as conn:
        conn.execute(f"UPDATE job_steps SET {clauses} WHERE job_id = ? AND step_order = ?", values)


def add_log(job_id: int, step_order: int | None, level: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO job_logs (job_id, step_order, level, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, step_order, level, message, now_iso()),
        )


def reset_job_for_rerun(job_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'pending', current_step = 0, approved_for_step2 = 0, final_result = NULL, error = NULL,
                started_at = NULL, finished_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), job_id),
        )
        conn.execute(
            """
            UPDATE job_steps
            SET status = 'pending', output = NULL, started_at = NULL, finished_at = NULL
            WHERE job_id = ?
            """,
            (job_id,),
        )
        conn.execute("DELETE FROM job_logs WHERE job_id = ?", (job_id,))
        conn.execute(
            "INSERT INTO job_logs (job_id, step_order, level, message, created_at) VALUES (?, NULL, 'info', 'Job reset for rerun', ?)",
            (job_id, now_iso()),
        )


# -----------------------------
# V2 orchestrator repository
# -----------------------------

V2_PROVIDERS = [
    {
        "name": "openai",
        "auth_type": "api_key",
        "status": "connected",
        "available_models": ["openai/gpt-4o", "openai/gpt-4o-mini"],
    },
    {
        "name": "gemini",
        "auth_type": "oauth",
        "status": "connected",
        "available_models": ["gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"],
    },
]

V2_MODELS = [
    {
        "id": "openai/gpt-4o",
        "provider": "openai",
        "label": "GPT-4o",
        "capabilities": ["general", "coding"],
        "cost_level": "medium",
        "latency_class": "medium",
        "supports_multimodal": True,
        "enabled": True,
    },
    {
        "id": "openai/gpt-4o-mini",
        "provider": "openai",
        "label": "GPT-4o mini",
        "capabilities": ["general", "fast"],
        "cost_level": "low",
        "latency_class": "fast",
        "supports_multimodal": True,
        "enabled": True,
    },
    {
        "id": "gemini/gemini-2.5-pro",
        "provider": "gemini",
        "label": "Gemini 2.5 Pro",
        "capabilities": ["research", "general", "multimodal"],
        "cost_level": "medium",
        "latency_class": "medium",
        "supports_multimodal": True,
        "enabled": True,
    },
    {
        "id": "gemini/gemini-2.5-flash",
        "provider": "gemini",
        "label": "Gemini 2.5 Flash",
        "capabilities": ["general", "fast", "multimodal"],
        "cost_level": "low",
        "latency_class": "fast",
        "supports_multimodal": True,
        "enabled": True,
    },
]


def seed_v2_catalog() -> None:
    with get_conn() as conn:
        for provider in V2_PROVIDERS:
            conn.execute(
                """
                INSERT OR REPLACE INTO providers_v2 (name, auth_type, status, available_models, last_check_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    provider["name"],
                    provider["auth_type"],
                    provider["status"],
                    json.dumps(provider["available_models"]),
                    now_iso(),
                ),
            )
        for model in V2_MODELS:
            conn.execute(
                """
                INSERT OR REPLACE INTO models_v2 (id, provider, label, capabilities, cost_level, latency_class, supports_multimodal, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model["id"],
                    model["provider"],
                    model["label"],
                    json.dumps(model["capabilities"]),
                    model["cost_level"],
                    model["latency_class"],
                    int(model["supports_multimodal"]),
                    int(model["enabled"]),
                ),
            )


def _loads_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _hydrate_session(row: dict[str, Any]) -> dict[str, Any]:
    row["context_refs"] = _loads_json(row.get("context_refs"), [])
    return row


def _hydrate_task(row: dict[str, Any]) -> dict[str, Any]:
    row["tags"] = _loads_json(row.get("tags"), [])
    row["requested_models"] = _loads_json(row.get("requested_models"), [])
    row["approval_required"] = bool(row.get("approval_required"))
    return row


def _hydrate_provider(row: dict[str, Any]) -> dict[str, Any]:
    row["available_models"] = _loads_json(row.get("available_models"), [])
    return row


def _hydrate_model(row: dict[str, Any]) -> dict[str, Any]:
    row["capabilities"] = _loads_json(row.get("capabilities"), [])
    row["supports_multimodal"] = bool(row.get("supports_multimodal"))
    row["enabled"] = bool(row.get("enabled"))
    return row


def create_session(payload: dict[str, Any]) -> int:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions_v2 (title, work_mode, output_mode, active_model, status, context_refs, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                payload["title"],
                payload["work_mode"],
                payload["output_mode"],
                payload.get("active_model"),
                json.dumps(payload.get("context_refs", [])),
                ts,
                ts,
            ),
        )
        return int(cur.lastrowid)


def list_sessions() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sessions_v2 ORDER BY id DESC").fetchall()
    return [_hydrate_session(dict(r)) for r in rows]


def get_session(session_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM sessions_v2 WHERE id = ?", (session_id,)).fetchone())
    return _hydrate_session(row) if row else None


def create_task(payload: dict[str, Any]) -> int:
    ts = now_iso()
    approval_status = "pending" if payload.get("approval_required") else "not_required"
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks_v2 (
                session_id, title, type, input, tags, status, priority, routing_strategy,
                requested_models, approval_required, approval_status, created_at, updated_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                payload["session_id"],
                payload["title"],
                payload["type"],
                payload["input"],
                json.dumps(payload.get("tags", [])),
                payload.get("priority", "normal"),
                payload.get("routing_strategy", "automatic"),
                json.dumps(payload.get("requested_models", [])),
                int(payload.get("approval_required", False)),
                approval_status,
                ts,
                ts,
            ),
        )
        return int(cur.lastrowid)


def list_tasks(session_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if session_id is None:
            rows = conn.execute("SELECT * FROM tasks_v2 ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks_v2 WHERE session_id = ? ORDER BY id DESC", (session_id,)).fetchall()
    return [_hydrate_task(dict(r)) for r in rows]


def get_task(task_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        task = row_to_dict(conn.execute("SELECT * FROM tasks_v2 WHERE id = ?", (task_id,)).fetchone())
        if not task:
            return None
        runs = rows_to_dicts(conn.execute("SELECT * FROM runs_v2 WHERE task_id = ? ORDER BY id", (task_id,)).fetchall())
        artifacts = rows_to_dicts(conn.execute("SELECT * FROM artifacts_v2 WHERE task_id = ? ORDER BY id", (task_id,)).fetchall())
    hydrated = _hydrate_task(task)
    hydrated["runs"] = runs
    hydrated["artifacts"] = artifacts
    return hydrated


def create_run(task_id: int, payload: dict[str, Any]) -> int:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs_v2 (
                task_id, provider, model, status, prompt_snapshot, output, error_message,
                latency_ms, cost, tokens_in, tokens_out, score, started_at, finished_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload["provider"],
                payload["model"],
                payload.get("status", "queued"),
                payload.get("prompt_snapshot", ""),
                payload.get("output"),
                payload.get("error_message"),
                payload.get("latency_ms"),
                payload.get("cost"),
                payload.get("tokens_in"),
                payload.get("tokens_out"),
                payload.get("score"),
                payload.get("started_at"),
                payload.get("finished_at"),
                ts,
            ),
        )
        run_id = int(cur.lastrowid)
        conn.execute("UPDATE tasks_v2 SET status = 'running', updated_at = ? WHERE id = ?", (ts, task_id))
        return run_id


def select_run(task_id: int, run_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks_v2 SET selected_run_id = ?, status = 'completed', updated_at = ?, completed_at = ? WHERE id = ?",
            (run_id, now_iso(), now_iso(), task_id),
        )


def list_runs(task_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM runs_v2 WHERE task_id = ? ORDER BY id", (task_id,)).fetchall()
    return rows_to_dicts(rows)


def list_providers() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM providers_v2 ORDER BY name").fetchall()
    return [_hydrate_provider(dict(r)) for r in rows]


def list_models() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM models_v2 WHERE enabled = 1 ORDER BY provider, id").fetchall()
    return [_hydrate_model(dict(r)) for r in rows]


def get_metrics_summary() -> dict[str, Any]:
    with get_conn() as conn:
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions_v2").fetchone()[0]
        total_tasks = conn.execute("SELECT COUNT(*) FROM tasks_v2").fetchone()[0]
        total_runs = conn.execute("SELECT COUNT(*) FROM runs_v2").fetchone()[0]
        total_cost = conn.execute("SELECT COALESCE(SUM(cost), 0) FROM runs_v2 WHERE cost IS NOT NULL").fetchone()[0]
        avg_latency = conn.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM runs_v2 WHERE latency_ms IS NOT NULL").fetchone()[0]
    return {
        "sessions": total_sessions,
        "tasks": total_tasks,
        "runs": total_runs,
        "total_cost": total_cost,
        "avg_latency_ms": avg_latency,
    }

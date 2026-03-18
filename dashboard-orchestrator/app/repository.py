from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .database import get_conn, row_to_dict, rows_to_dicts


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

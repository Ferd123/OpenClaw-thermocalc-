from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "orchestrator.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                requires_approval INTEGER NOT NULL DEFAULT 0,
                current_step INTEGER NOT NULL DEFAULT 0,
                approved_for_step2 INTEGER NOT NULL DEFAULT 0,
                final_result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                name TEXT NOT NULL,
                agent TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                output TEXT,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                step_order INTEGER,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                work_mode TEXT NOT NULL,
                output_mode TEXT NOT NULL,
                active_model TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                context_refs TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                input TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                routing_strategy TEXT NOT NULL DEFAULT 'automatic',
                requested_models TEXT NOT NULL DEFAULT '[]',
                selected_run_id INTEGER,
                approval_required INTEGER NOT NULL DEFAULT 0,
                approval_status TEXT NOT NULL DEFAULT 'not_required',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions_v2(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                prompt_snapshot TEXT NOT NULL DEFAULT '',
                output TEXT,
                error_message TEXT,
                latency_ms INTEGER,
                cost REAL,
                tokens_in INTEGER,
                tokens_out INTEGER,
                score REAL,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks_v2(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                role TEXT NOT NULL,
                path TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks_v2(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS providers_v2 (
                name TEXT PRIMARY KEY,
                auth_type TEXT NOT NULL,
                status TEXT NOT NULL,
                available_models TEXT NOT NULL DEFAULT '[]',
                last_check_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS models_v2 (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                label TEXT NOT NULL,
                capabilities TEXT NOT NULL DEFAULT '[]',
                cost_level TEXT NOT NULL,
                latency_class TEXT NOT NULL,
                supports_multimodal INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    return data


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

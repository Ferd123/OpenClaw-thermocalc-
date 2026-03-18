from __future__ import annotations

import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import repository as repo

RUN_LOCKS: dict[int, threading.Lock] = {}
BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


class AgentRunner:
    def run(self, agent: str, prompt: str, context: str) -> str:
        cli = shutil.which(agent)
        combined_prompt = prompt if not context else f"{prompt}\n\nContext from previous step:\n{context}"
        if cli:
            try:
                if agent == "gemini":
                    proc = subprocess.run([cli, "-p", combined_prompt], capture_output=True, text=True, timeout=180)
                else:
                    proc = subprocess.run([cli, combined_prompt], capture_output=True, text=True, timeout=180)
                text = (proc.stdout or proc.stderr).strip()
                return text or f"{agent} executed with no textual output"
            except Exception as exc:
                return f"[{agent} CLI fallback error] {exc}"
        stamp = datetime.now(timezone.utc).isoformat()
        return f"[{stamp}] Mock {agent} result\nPrompt: {prompt}\n\nContext:\n{context or '(none)'}"


runner = AgentRunner()


def start_job(job_id: int, reset: bool = True) -> bool:
    lock = RUN_LOCKS.setdefault(job_id, threading.Lock())
    if lock.locked():
        return False
    if reset:
        repo.reset_job_for_rerun(job_id)
    thread = threading.Thread(target=_run_job, args=(job_id, lock), daemon=True)
    thread.start()
    return True


def _run_job(job_id: int, lock: threading.Lock) -> None:
    with lock:
        job = repo.get_job(job_id)
        if not job:
            return
        repo.update_job(job_id, status="running", started_at=repo.now_iso(), error=None)
        repo.add_log(job_id, None, "info", "Job execution started")

        previous_output = ""
        for step in job["steps"]:
            step_order = step["step_order"]
            if step_order == 2 and job["requires_approval"] and not job["approved_for_step2"]:
                repo.update_job(job_id, status="waiting_approval", current_step=1)
                repo.add_log(job_id, 2, "warning", "Waiting for manual approval before step 2")
                return

            repo.update_job(job_id, current_step=step_order)
            repo.update_step(job_id, step_order, status="running", started_at=repo.now_iso())
            repo.add_log(job_id, step_order, "info", f"Running step {step_order} with agent '{step['agent']}'")
            try:
                output = runner.run(step["agent"], step["prompt"], previous_output)
                repo.update_step(job_id, step_order, status="completed", output=output, finished_at=repo.now_iso())
                repo.add_log(job_id, step_order, "info", f"Step {step_order} completed")
                previous_output = output
                _write_step_result(job_id, step_order, output)
            except Exception as exc:
                repo.update_step(job_id, step_order, status="failed", finished_at=repo.now_iso())
                repo.update_job(job_id, status="failed", error=str(exc), finished_at=repo.now_iso())
                repo.add_log(job_id, step_order, "error", f"Step {step_order} failed: {exc}")
                return

        repo.update_job(job_id, status="completed", final_result=previous_output, finished_at=repo.now_iso(), current_step=2)
        repo.add_log(job_id, None, "info", "Job execution completed")
        _write_final_result(job_id, previous_output)


def approve_and_continue(job_id: int, approved: bool) -> bool:
    job = repo.get_job(job_id)
    if not job:
        return False
    if not approved:
        repo.update_job(job_id, status="rejected", error="Step 2 approval rejected", finished_at=repo.now_iso())
        repo.add_log(job_id, 2, "warning", "Step 2 approval rejected")
        return True
    repo.update_job(job_id, approved_for_step2=1, status="running")
    repo.add_log(job_id, 2, "info", "Step 2 approved manually")
    thread = threading.Thread(target=_resume_step_two, args=(job_id,), daemon=True)
    thread.start()
    return True


def _resume_step_two(job_id: int) -> None:
    job = repo.get_job(job_id)
    if not job:
        return
    step1 = next((s for s in job["steps"] if s["step_order"] == 1), None)
    step2 = next((s for s in job["steps"] if s["step_order"] == 2), None)
    if not step1 or not step2:
        return
    previous_output = step1.get("output") or ""
    repo.update_job(job_id, current_step=2)
    repo.update_step(job_id, 2, status="running", started_at=repo.now_iso())
    repo.add_log(job_id, 2, "info", f"Running approved step 2 with agent '{step2['agent']}'")
    try:
        output = runner.run(step2["agent"], step2["prompt"], previous_output)
        repo.update_step(job_id, 2, status="completed", output=output, finished_at=repo.now_iso())
        repo.update_job(job_id, status="completed", final_result=output, finished_at=repo.now_iso())
        repo.add_log(job_id, 2, "info", "Step 2 completed after approval")
        _write_step_result(job_id, 2, output)
        _write_final_result(job_id, output)
    except Exception as exc:
        repo.update_step(job_id, 2, status="failed", finished_at=repo.now_iso())
        repo.update_job(job_id, status="failed", error=str(exc), finished_at=repo.now_iso())
        repo.add_log(job_id, 2, "error", f"Step 2 failed: {exc}")


def _write_step_result(job_id: int, step_order: int, text: str) -> None:
    path = RESULTS_DIR / f"job-{job_id}-step-{step_order}.txt"
    path.write_text(text, encoding="utf-8")


def _write_final_result(job_id: int, text: str) -> None:
    path = RESULTS_DIR / f"job-{job_id}-final.txt"
    path.write_text(text, encoding="utf-8")

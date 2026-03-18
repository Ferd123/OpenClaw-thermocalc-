# Dashboard Orchestrator MVP

Local MVP for orchestrating **2-step sequential jobs** with selectable agents (`codex`, `gemini`), SQLite persistence, execution logs, stored results, and an optional approval gate before step 2.

## What it does

- Create a job with exactly 2 ordered steps
- Select `codex` or `gemini` per step
- Run step 1 → optionally wait for approval → run step 2
- Persist jobs, steps, status, logs, and final result in SQLite
- Store step/final outputs as text files under `results/`
- Serve a simple dashboard UI from FastAPI
- Use local CLI executables when available; otherwise fall back to deterministic mock output so the MVP is runnable everywhere

## Stack

- Backend: FastAPI
- Persistence: SQLite via `sqlite3`
- Frontend: static HTML/CSS/JS
- Background execution: Python threads

## Project structure

```text
.dashboard-orchestrator/
├─ app/
│  ├─ __init__.py
│  ├─ database.py
│  ├─ main.py
│  ├─ models.py
│  ├─ repository.py
│  └─ runner.py
├─ results/
├─ static/
│  ├─ app.js
│  ├─ index.html
│  └─ styles.css
├─ orchestrator.db        # created at runtime
├─ requirements.txt
└─ README.md
```

## Run

### 1. Create and activate a virtual environment

**PowerShell**

```powershell
cd dashboard-orchestrator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Start the server

```powershell
uvicorn app.main:app --reload --port 8000
```

### 3. Open the dashboard

- <http://127.0.0.1:8000>

## API endpoints

- `GET /health`
- `GET /api/jobs`
- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/run`
- `POST /api/jobs/{job_id}/approve`

## Example payload

```json
{
  "title": "Gemini plans, Codex implements",
  "description": "Demo workflow",
  "requires_approval": true,
  "steps": [
    {
      "name": "Plan",
      "agent": "gemini",
      "prompt": "Create an implementation plan for a hello-world feature."
    },
    {
      "name": "Implement",
      "agent": "codex",
      "prompt": "Implement the feature using the plan from the previous step."
    }
  ]
}
```

## Notes on agent execution

`runner.py` tries to find a local `codex` or `gemini` executable in `PATH`:

- If found, it invokes the CLI and captures stdout/stderr.
- If not found, it generates mock output with the prompt and prior-step context.

That means the MVP is usable immediately, and can be upgraded later to real CLI flags / auth / richer execution adapters.

## Suggested next steps

- Replace the mock/CLI adapter with robust wrappers for your local Codex and Gemini setup
- Add cancel/retry semantics and per-step timeouts
- Stream logs over WebSocket or Server-Sent Events
- Add prompt templates, artifacts, and file attachments
- Move background execution to a queue (RQ/Celery/Arq) if you need durability across restarts

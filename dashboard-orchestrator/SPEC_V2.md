# Dashboard AI Orchestrator — Technical Spec v2

## 1. Purpose

Build an operational control center on top of OpenClaw to route, execute, compare, and evaluate AI work across multiple providers/models.

Primary optimization targets:

- technical accuracy
- response time
- cost
- traceability
- reproducibility

The dashboard is not just a UI. It is a decision system composed of:

- routing
- execution
- structured persistence
- evaluation
- observability

---

## 2. Scope split

### 2.1 OpenClaw native responsibilities

OpenClaw remains the infrastructure layer for:

- Gateway
- provider connectivity
- model addressing via `provider/model`
- chat/channel interfaces
- baseline dashboard/control UI
- session runtime integration

### 2.2 Orchestrator layer responsibilities

This project adds:

- `session / task / run / artifact` domain model
- routing engine
- manual override + compare mode
- structured persistence in SQLite
- multi-run comparisons
- metrics aggregation
- exportable results

---

## 3. Domain model

## 3.1 Session

A continuous work container.

Examples:

- RTD analysis workflow
- coding/debugging workflow
- technical writing workflow

### Fields

- `id`
- `title`
- `work_mode`: `research | coding | chat | comparison | ops`
- `output_mode`: `chat | summary | report | code`
- `active_model`
- `status`: `active | archived`
- `context_refs` (JSON array)
- `created_at`
- `updated_at`

### Notes

- `work_mode` describes the nature of the work.
- `output_mode` describes the expected output shape.
- `active_model` is the current UI default, not necessarily the final routed model.

---

## 3.2 Task

A specific unit of work inside a session.

### Fields

- `id`
- `session_id`
- `title`
- `type`: `analysis | code | summary | comparison | general`
- `input`
- `tags` (JSON array)
- `status`: `pending | routed | waiting_approval | running | completed | failed | cancelled`
- `priority`: `low | normal | high`
- `routing_strategy`: `manual | automatic | compare`
- `requested_models` (JSON array)
- `selected_run_id` (nullable)
- `approval_required`
- `approval_status`: `not_required | pending | approved | rejected`
- `created_at`
- `updated_at`
- `completed_at`

### State machine

```text
pending -> routed -> running -> completed
pending -> routed -> running -> failed
pending -> routed -> waiting_approval -> running -> completed
pending -> routed -> waiting_approval -> running -> failed
pending -> cancelled
```

---

## 3.3 Run

A concrete execution of a model against a task.

A task may have one or many runs.

### Fields

- `id`
- `task_id`
- `provider`
- `model`
- `status`: `queued | running | success | error | cancelled`
- `prompt_snapshot`
- `output`
- `error_message`
- `latency_ms`
- `cost`
- `tokens_in`
- `tokens_out`
- `score` (nullable)
- `started_at`
- `finished_at`
- `created_at`

### Notes

- `selected_run_id` in the parent task defines the official winning run.
- run-level scoring may be manual or automatic.

---

## 3.4 Artifact

Structured evidence attached to a task.

### Fields

- `id`
- `task_id`
- `kind`: `pdf | csv | image | txt | json | code | diff`
- `role`: `input | output | evidence`
- `path`
- `label`
- `created_at`

### Notes

Artifacts allow the orchestrator to work with technical files, reports, datasets, and outputs.

---

## 3.5 Provider

Provider availability and auth state.

### Fields

- `name`
- `auth_type`: `api_key | oauth | local`
- `status`: `connected | degraded | disconnected`
- `available_models` (JSON array)
- `last_check_at`

---

## 3.6 Model catalog

Logical view of available models.

### Fields

- `id` (canonical `provider/model`)
- `provider`
- `label`
- `capabilities` (JSON array)
- `cost_level`: `low | medium | high`
- `latency_class`: `fast | medium | slow`
- `supports_multimodal`
- `enabled`

### Notes

Avoid hardcoding volatile provider model names in routing logic. Use aliases/profiles where possible.

---

## 4. Routing engine

## 4.1 Base routing

Default routing by task type:

- `code` -> coding profile
- `analysis` -> research profile
- `summary` -> summary profile
- `comparison` -> compare profile
- `general` -> active session default

## 4.2 Tag routing

- `#code` -> OpenAI coding model
- `#paper` -> Gemini research model
- `#compare` -> multi-run
- `#cheap` -> low-cost profile
- `#fast` -> low-latency profile

## 4.3 Advanced routing inputs

Optional routing signals:

- prompt length
- code detected in prompt
- file types present (`pdf`, `csv`, `image`)
- priority (`time` vs `quality`)
- manual override from UI

## 4.4 Routing profiles

Profiles decouple task logic from raw model names.

Example:

```yaml
profiles:
  coding-primary:
    primary: openai/gpt-4o
    fallback: openai/gpt-4o-mini
  research-primary:
    primary: gemini/gemini-2.5-pro
    fallback: gemini/gemini-2.5-flash
  compare-default:
    models:
      - openai/gpt-4o
      - gemini/gemini-2.5-pro
```

---

## 5. Work modes

- `research`: papers, synthesis, technical analysis, multimodal input
- `coding`: scripts, debugging, refactors, pipeline work
- `chat`: quick assistance, short responses, light drafting
- `comparison`: side-by-side multi-model execution
- `ops`: monitoring, audits, status and costs

---

## 6. Metrics

## 6.1 Run-level metrics

- `latency_ms`
- `cost`
- `tokens_in`
- `tokens_out`
- `status`
- `score`

## 6.2 Task-level metrics

- total elapsed time
- number of runs
- chosen run
- output divergence score
- evaluation method: `manual | embedding | llm_judge`

## 6.3 System-level metrics

- daily cost by provider
- usage by model
- average response time
- success rate
- error rate
- fallback rate
- compare usage rate

---

## 7. UI minimum viable product

## 7.1 Main panel

- prompt input
- task type selector
- work mode selector
- model override selector
- execute button
- compare button

## 7.2 Sidebar

- active sessions
- recent tasks
- model switcher
- provider health

## 7.3 Result panel

- primary output
- per-run tabs
- visible metrics per run
- selected winning run

## 7.4 Actions

- rerun with another model
- compare outputs
- promote selected run
- save result
- export `txt/json`

---

## 8. Persistence model (SQLite)

Required tables:

- `sessions_v2`
- `tasks_v2`
- `runs_v2`
- `artifacts_v2`
- `providers_v2`
- `models_v2`

Legacy MVP tables (`jobs`, `job_steps`, `job_logs`) remain during migration.

---

## 9. API v2 minimum

### Sessions

- `GET /api/v2/sessions`
- `POST /api/v2/sessions`
- `GET /api/v2/sessions/{id}`

### Tasks

- `GET /api/v2/tasks`
- `POST /api/v2/tasks`
- `GET /api/v2/tasks/{id}`

### Runs

- `GET /api/v2/tasks/{id}/runs`
- `POST /api/v2/tasks/{id}/runs`
- `POST /api/v2/tasks/{id}/select-run`

### Catalog

- `GET /api/v2/providers`
- `GET /api/v2/models`

### Metrics

- `GET /api/v2/metrics/summary`

---

## 10. Implementation plan

## Phase 1

- add v2 schema to SQLite
- add session/task/run models
- add provider/model catalog endpoints
- keep legacy MVP working

## Phase 2

- create tasks from UI
- create runs manually and in compare mode
- persist metrics and selected run

## Phase 3

- add routing engine
- add automatic profile-based model selection
- add provider/model health checks

## Phase 4

- add scoring/evaluation
- add artifact ingestion
- add exports and richer metrics dashboards

---

## 11. Design constraints

- preserve backward compatibility with current MVP routes
- do not couple routing logic to one fixed model name everywhere
- support manual override at any step
- store enough metadata for reproducibility
- keep MVP database and API understandable

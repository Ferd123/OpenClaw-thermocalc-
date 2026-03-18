from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["codex", "gemini"]
WorkMode = Literal["research", "coding", "chat", "comparison", "ops"]
OutputMode = Literal["chat", "summary", "report", "code"]
TaskType = Literal["analysis", "code", "summary", "comparison", "general"]
TaskStatus = Literal["pending", "routed", "waiting_approval", "running", "completed", "failed", "cancelled"]
TaskPriority = Literal["low", "normal", "high"]
RoutingStrategy = Literal["manual", "automatic", "compare"]
RunStatus = Literal["queued", "running", "success", "error", "cancelled"]


class StepCreate(BaseModel):
    name: str
    agent: AgentName
    prompt: str


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    requires_approval: bool = False
    steps: list[StepCreate] = Field(min_length=2, max_length=2)


class JobRunRequest(BaseModel):
    reset_failed_steps: bool = True


class ApprovalRequest(BaseModel):
    approved: bool


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    work_mode: WorkMode = "research"
    output_mode: OutputMode = "chat"
    active_model: str | None = None
    context_refs: list[str] = Field(default_factory=list)


class TaskCreate(BaseModel):
    session_id: int
    title: str = Field(min_length=1, max_length=200)
    type: TaskType = "general"
    input: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    priority: TaskPriority = "normal"
    routing_strategy: RoutingStrategy = "automatic"
    requested_models: list[str] = Field(default_factory=list)
    approval_required: bool = False


class RunCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    prompt_snapshot: str = ""
    output: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    cost: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    score: float | None = None
    status: RunStatus = "queued"


class SelectRunRequest(BaseModel):
    run_id: int

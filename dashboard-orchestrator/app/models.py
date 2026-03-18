from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["codex", "gemini"]


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

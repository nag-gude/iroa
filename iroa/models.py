"""Pydantic models for IROA API and agent I/O."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertPayload(BaseModel):
    trigger_time: datetime | None = None
    service: str | None = None
    component: str | None = None
    alert_type: str | None = None
    severity: str | None = None
    description: str | None = None
    time_range_minutes: int = 15


class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="Natural language question or alert description")
    time_range_minutes: int = Field(15, ge=1, le=10080, description="Lookback in minutes")
    alert: AlertPayload | None = Field(None, description="Optional structured alert payload")
    create_ticket: bool = Field(False, description="Whether to create a ticket if high severity")


class Citation(BaseModel):
    type: str = Field(..., description="'search' or 'esql'")
    index: str | None = None
    id: str | None = None
    snippet: str | None = None
    fields: dict[str, Any] | None = None


class ActionTaken(BaseModel):
    action: str = Field(..., description="e.g. 'create_ticket'")
    system: str | None = Field(None, description="e.g. 'Jira'")
    identifier: str | None = Field(None, description="e.g. 'PROJ-123'")
    link: str | None = None


class AnalyzeResponse(BaseModel):
    summary: str = Field(..., description="Concise summary of the incident or answer")
    root_cause: str = Field(..., description="Root-cause hypothesis or main finding")
    evidence: list[Citation] = Field(default_factory=list, description="Citations to ES docs/results")
    actions_taken: list[ActionTaken] = Field(default_factory=list)
    explanation: str | None = Field(None, description="What the agent did (FR-5.3)")
    confidence: str | None = Field(None, description="e.g. 'high', 'medium', 'low'")
    audit_trail: list[str] = Field(default_factory=list, description="Steps performed")

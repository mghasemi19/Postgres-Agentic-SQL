from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SQLProposal(BaseModel):
    sql: str = Field(description="A single PostgreSQL read query that answers the user's question.")
    explanation: str = Field(
        description="A short explanation of what the SQL does. Do not reveal hidden chain-of-thought."
    )


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    session_id: str | None = Field(default=None, max_length=200)


class QueryResponse(BaseModel):
    request_id: str
    status: Literal["ok", "rejected", "error"]
    answer: str
    sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int


class ExecutionResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    plan_cost: float | None = None


class SafetyResult(BaseModel):
    allowed: bool
    sql: str | None = None
    reason: str | None = None

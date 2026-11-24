from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SQLProposal(BaseModel):
    sql: str = Field(description="A single PostgreSQL read query that answers the user's question.")
    explanation: str = Field(
        description="A short explanation of what the SQL does. Do not reveal hidden chain-of-thought."
    )

'''
proposal = SQLProposal(
    sql="""
    SELECT
        p.name,
        SUM(oi.quantity * oi.unit_price) AS revenue
    FROM products p
    JOIN order_items oi
        ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.name
    ORDER BY revenue DESC
    LIMIT 5
    """,
    explanation="Calculates total revenue for each product."
)'''


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

'''
{
  "request_id": "83af1c...",
  "status": "ok",
  "answer": "The Mechanical Keyboard generated the most revenue.",
  "sql": "SELECT ...",
  "columns": [
    "name",
    "revenue"
  ],
  "rows": [
    {
      "name": "Mechanical Keyboard",
      "revenue": 12500.40
    }
  ],
  "latency_ms": 1473
}'''    


class ExecutionResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    plan_cost: float | None = None

'''ExecutionResult(
    columns=["name", "revenue"],
    rows=[
        {
            "name": "Keyboard",
            "revenue": 12000
        }
    ],
    row_count=1,
    plan_cost=38.25
)'''


class SafetyResult(BaseModel):
    allowed: bool
    sql: str | None = None
    reason: str | None = None

'''SafetyResult(
    allowed=True,
    sql="""
    SELECT *
    FROM products
    LIMIT 10
    """,
    reason=None
)'''


'''
                     USER
                      │
                      │ JSON
                      ▼
              ┌───────────────┐
              │ QueryRequest  │
              │               │
              │ question      │
              │ session_id    │
              └───────┬───────┘
                      │
                      ▼
                     LLM
                      │
                      ▼
              ┌───────────────┐
              │ SQLProposal   │
              │               │
              │ sql           │
              │ explanation   │
              └───────┬───────┘
                      │
                      ▼
                SQL validator
                      │
                      ▼
              ┌───────────────┐
              │ SafetyResult  │
              │               │
              │ allowed       │
              │ sql           │
              │ reason        │
              └───────┬───────┘
                      │
                 allowed=true
                      │
                      ▼
                  PostgreSQL
                      │
                      ▼
             ┌─────────────────┐
             │ ExecutionResult │
             │                 │
             │ columns         │
             │ rows            │
             │ row_count       │
             │ plan_cost       │
             └────────┬────────┘
                      │
                      ▼
              answer generation
                      │
                      ▼
              ┌───────────────┐
              │ QueryResponse │
              │               │
              │ request_id    │
              │ status        │
              │ answer        │
              │ sql           │
              │ columns       │
              │ rows          │
              │ latency_ms    │
              └───────┬───────┘
                      │
                      ▼
                    USER
'''

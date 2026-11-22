from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import Settings
from .models import ExecutionResult


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine: Engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            future=True,
        )

    def ping(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT 1")).scalar_one() == 1

    def execute_readonly(self, sql: str) -> ExecutionResult:
        timeout = max(1, int(self.settings.statement_timeout_ms))

        with self.engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql(f"SET LOCAL statement_timeout = '{timeout}ms'")

                plan_cost: float | None = None
                if self.settings.max_plan_cost > 0:
                    plan_result = conn.exec_driver_sql(f"EXPLAIN (FORMAT JSON) {sql}")
                    plan_payload = plan_result.scalar_one()
                    plan_cost = _extract_total_cost(plan_payload)
                    if plan_cost is not None and plan_cost > self.settings.max_plan_cost:
                        raise RuntimeError(
                            f"Query rejected: planner cost {plan_cost:.2f} exceeds "
                            f"MAX_PLAN_COST={self.settings.max_plan_cost:.2f}."
                        )

                result = conn.execute(text(sql))
                columns = list(result.keys())
                raw_rows = result.fetchmany(self.settings.max_rows + 1)
                raw_rows = raw_rows[: self.settings.max_rows]
                rows = [dict(row._mapping) for row in raw_rows]
                tx.rollback()
                return ExecutionResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    plan_cost=plan_cost,
                )
            except Exception:
                tx.rollback()
                raise


def _extract_total_cost(payload: Any) -> float | None:
    # psycopg typically returns the JSON value already decoded. Be conservative.
    try:
        if isinstance(payload, list) and payload:
            plan = payload[0].get("Plan", {})
            value = plan.get("Total Cost")
            return float(value) if value is not None else None
        if isinstance(payload, dict):
            plan = payload.get("Plan", {})
            value = plan.get("Total Cost")
            return float(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None
    return None

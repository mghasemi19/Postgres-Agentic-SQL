# file is responsible for connecting to PostgreSQL, 
# executing SQL queries safely, and returning structured results.

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import Settings
from .models import ExecutionResult


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Create a pooled engine and check stale connections before reusing them.
        self.engine: Engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,                     # Checks whether a pooled connection is still alive before reuse
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,  # Maximum additional temporary connections
            future=True,
        )

    # Check connectivity with a lightweight query.
    def ping(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT 1")).scalar_one() == 1

    # Execute a query within transaction-level safety and resource limits.
    def execute_readonly(self, sql: str) -> ExecutionResult:
        timeout = max(1, int(self.settings.statement_timeout_ms))

        with self.engine.connect() as conn:
            tx = conn.begin()
            try:
                # Ask PostgreSQL to reject writes in this transaction.
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql(f"SET LOCAL statement_timeout = '{timeout}ms'")

                # Optionally reject expensive queries based on PostgreSQL planner estimates.
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

                # Run the SQL after read-only mode and optional plan checks are active.
                result = conn.execute(text(sql))
                columns = list(result.keys())
                # Fetch only a bounded number of rows to limit memory and data exposure.
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


# Extract planner cost from the JSON shapes commonly returned by psycopg.
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

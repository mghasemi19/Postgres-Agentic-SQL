from __future__ import annotations

import time
import uuid

import structlog

from .config import Settings
from .db import Database
from .graph import DatabaseAgentGraph
from .models import QueryResponse

logger = structlog.get_logger(__name__)


class DatabaseAgentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings)
        self.agent = DatabaseAgentGraph(settings, self.database)

    def query(self, question: str) -> QueryResponse:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        state = self.agent.invoke(question=question, request_id=request_id)
        latency_ms = int((time.perf_counter() - started) * 1000)

        logger.info(
            "request_completed",
            request_id=request_id,
            status=state.get("status", "error"),
            latency_ms=latency_ms,
        )

        return QueryResponse(
            request_id=request_id,
            status=state.get("status", "error"),
            answer=state.get("answer", "No answer was produced."),
            sql=state.get("sql") if self.settings.return_sql else None,
            columns=state.get("columns", []) if self.settings.return_rows else [],
            rows=state.get("rows", []) if self.settings.return_rows else [],
            latency_ms=latency_ms,
        )

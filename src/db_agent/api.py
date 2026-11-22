from __future__ import annotations

import time
from functools import lru_cache

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .config import get_settings
from .logging import configure_logging
from .models import QueryRequest, QueryResponse
from .service import DatabaseAgentService

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)

REQUESTS = Counter(
    "db_agent_requests_total",
    "Number of database-agent requests",
    ["endpoint", "status"],
)
LATENCY = Histogram(
    "db_agent_request_latency_seconds",
    "Database-agent request latency",
    ["endpoint"],
)

app = FastAPI(
    title="PostgreSQL Database Agent",
    version="0.1.0",
    description="Natural-language analytics over PostgreSQL with deterministic SQL guardrails.",
)


@lru_cache(maxsize=1)
def get_service() -> DatabaseAgentService:
    return DatabaseAgentService(settings)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=int(elapsed * 1000),
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        if get_service().database.ping():
            return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    raise HTTPException(status_code=503, detail="Database is not ready")


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    endpoint = "/v1/query"
    started = time.perf_counter()
    try:
        response = get_service().query(payload.question)
        REQUESTS.labels(endpoint=endpoint, status=response.status).inc()
        return response
    except Exception as exc:
        REQUESTS.labels(endpoint=endpoint, status="error").inc()
        logger.exception("unhandled_query_error")
        raise HTTPException(status_code=500, detail="Database agent failed") from exc
    finally:
        LATENCY.labels(endpoint=endpoint).observe(time.perf_counter() - started)

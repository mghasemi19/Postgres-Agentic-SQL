# PostgreSQL Database Agent

A production-style natural-language-to-SQL agent for PostgreSQL.

The service accepts a user's question, inspects the relevant database schema, asks an LLM to generate PostgreSQL, validates the SQL with an AST parser, runs the query inside a read-only transaction with a statement timeout, and turns the returned rows into a concise answer.

This repository is intentionally **not** the usual demo where an LLM receives a database password and gets to improvise. The execution path is constrained by application guardrails **and** PostgreSQL permissions.

## What this project demonstrates

- Natural language -> PostgreSQL with an LLM
- LangGraph state-machine orchestration
- Schema discovery and table ranking for larger databases
- Structured LLM output with Pydantic
- SQL AST validation with SQLGlot
- Read-only PostgreSQL transactions
- Statement timeout, row limit, and optional query-plan cost guardrail
- FastAPI REST API
- CLI client
- Structured JSON logging
- Prometheus metrics endpoint
- Docker Compose demo environment
- Unit tests and an evaluation harness
- A safe design path for future write operations

## Architecture

```mermaid
flowchart LR
    U[User / App] --> API[FastAPI]
    API --> G[LangGraph workflow]
    G --> S[Schema catalog]
    S --> PG[(PostgreSQL)]
    G --> LLM[LLM API]
    LLM --> G
    G --> V[SQLGlot validator]
    V -->|approved SQL| X[Read-only executor]
    X -->|SET TRANSACTION READ ONLY| PG
    X --> G
    G --> LLM2[Answer summarizer]
    LLM2 --> API

    V -->|reject| E[Safe error response]
    X -->|DB error| R[Repair attempt]
    R --> LLM
```

The graph is deliberately explicit:

```text
inspect_schema
      |
      v
generate_sql <---------------------+
      |                             |
      v                             |
validate_sql                        |
      |                             |
      +-- rejected --> fail         |
      |                             |
      v                             |
execute_sql                         |
      |                             |
      +-- DB error + retries left --+
      |
      v
summarize
      |
      v
END
```

## Safety model

Security is layered. No single LLM prompt is trusted.

1. The LLM receives schema metadata, not database credentials.
2. Generated SQL must parse successfully as PostgreSQL.
3. Only one statement is allowed.
4. Only query statements are allowed.
5. DDL/DML and transaction-control nodes are rejected anywhere in the AST.
6. Dangerous PostgreSQL functions such as `pg_sleep`, file-reading helpers, `dblink`, and large-object import/export are blocked.
7. Queries are forced to a configured maximum `LIMIT`.
8. The executor starts a database transaction and executes `SET TRANSACTION READ ONLY`.
9. A server-side `statement_timeout` is applied.
10. The recommended PostgreSQL role has `default_transaction_read_only=on` and only `SELECT` privileges.
11. Optionally, `EXPLAIN (FORMAT JSON)` is checked before execution and very high planner-cost queries are rejected.

For a production deployment, use a dedicated read replica or analytics database whenever possible.

## Technology choices

| Layer | Technology |
|---|---|
| API | FastAPI |
| Agent orchestration | LangGraph |
| LLM integration | LangChain `ChatOpenAI` compatible client |
| Data validation | Pydantic |
| SQL parser / AST | SQLGlot |
| PostgreSQL access | SQLAlchemy + psycopg 3 |
| Logs | structlog |
| Metrics | Prometheus client |
| Tests | pytest |
| Local stack | Docker Compose |

`ChatOpenAI` is isolated behind `src/db_agent/llm.py`, so replacing it with Anthropic, Gemini, Azure OpenAI, or another provider is a small adapter change. Any provider with an OpenAI-compatible endpoint can usually be used by setting `LLM_BASE_URL`.

---

# 1. Quick start with Docker

## Prerequisites

- Docker + Docker Compose
- An LLM API key

Copy the environment file:

```bash
cp .env.example .env
```

Edit at least:

```dotenv
LLM_API_KEY=your-key
LLM_MODEL=your-model-name
```

Then start the demo stack:

```bash
docker compose up --build
```

The services are:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Prometheus metrics: `http://localhost:8000/metrics`
- PostgreSQL: `localhost:5432`

The demo PostgreSQL database contains a small e-commerce schema with customers, products, orders, and order items.

Check health:

```bash
curl http://localhost:8000/health
```

Ask a question:

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which 5 products generated the most revenue?"
  }'
```

Example response shape:

```json
{
  "request_id": "8ca0...",
  "status": "ok",
  "answer": "The highest-revenue product is ...",
  "sql": "SELECT ... LIMIT 100",
  "columns": ["product_name", "revenue"],
  "rows": [
    {"product_name": "...", "revenue": 1234.5}
  ],
  "latency_ms": 842
}
```

Whether SQL and raw rows are returned is configurable. In a sensitive production application, set `RETURN_SQL=false` and `RETURN_ROWS=false`.

---

# 2. Connect to your existing PostgreSQL server

You do **not** need to use the demo database. Set:

```dotenv
DATABASE_URL=postgresql+psycopg://db_agent:strong-password@your-host:5432/your_database
ALLOWED_SCHEMAS=public,analytics
```

For a real server, create a restricted role similar to:

```sql
CREATE ROLE db_agent LOGIN PASSWORD 'use-a-secret-manager';
GRANT CONNECT ON DATABASE your_database TO db_agent;
GRANT USAGE ON SCHEMA analytics TO db_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO db_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
    GRANT SELECT ON TABLES TO db_agent;
ALTER ROLE db_agent SET default_transaction_read_only = on;
ALTER ROLE db_agent SET statement_timeout = '5s';
```

Do not give the agent owner, superuser, `CREATE`, or broad write privileges. The database should be able to stop a bad query even if every application-level check fails.

---

# 3. Run locally without Docker

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -e ".[dev]"
cp .env.example .env
```

Start the API:

```bash
uvicorn db_agent.api:app --reload
```

Use the CLI:

```bash
db-agent ask "How many orders were placed in October?"
```

Or point the CLI at a remote API:

```bash
db-agent ask-api "Which customers spent the most?" --url http://localhost:8000
```

---

# 4. Configuration

Important environment variables:

| Variable | Meaning | Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL | `postgresql+psycopg://...` |
| `LLM_API_KEY` | API key | secret |
| `LLM_MODEL` | model name | provider dependent |
| `LLM_BASE_URL` | optional OpenAI-compatible endpoint | `https://.../v1` |
| `ALLOWED_SCHEMAS` | schemas exposed to the agent | `public,analytics` |
| `MAX_ROWS` | hard result-row cap | `100` |
| `STATEMENT_TIMEOUT_MS` | PostgreSQL timeout | `5000` |
| `MAX_SQL_RETRIES` | generation repair attempts | `2` |
| `SCHEMA_TOP_K` | max tables described to LLM | `12` |
| `MAX_PLAN_COST` | optional PostgreSQL planner-cost ceiling; 0 disables | `0` |
| `RETURN_SQL` | include generated SQL in API response | `true` |
| `RETURN_ROWS` | include raw rows in API response | `true` |

See `.env.example` for the complete list.

---

# 5. Example questions

The bundled e-commerce data supports questions such as:

```text
How many active customers do we have?
Which 5 products generated the most revenue?
What was monthly revenue in 2026?
Which customers have spent more than 500 euros?
What is the average order value by country?
Which category has the highest number of units sold?
Show the top 10 customers by lifetime spend.
```

The agent may generate joins, grouping, CTEs, aggregates, ordering, and window functions, but the final SQL must still pass the validator.

---

# 6. How the schema selection scales

Dumping an entire enterprise schema into every prompt is wasteful and eventually impossible.

`SchemaCatalog` therefore uses two levels:

1. **Catalog pass:** cache table names and column names.
2. **Ranking pass:** score tables against the user's question using token overlap.
3. **Detail pass:** build detailed schema text only for the top `SCHEMA_TOP_K` tables, including columns, primary keys, and foreign keys.

This is intentionally simple and dependency-light. For thousands of tables, replace the ranker with schema embeddings stored in pgvector or another retrieval index. The rest of the graph can remain unchanged.

---

# 7. Evaluation

The `evals/cases.jsonl` file contains example natural-language questions and expectations.

Run live evaluation against your configured database and LLM:

```bash
python evals/run_eval.py
```

The evaluator checks:

- whether the request succeeded
- whether SQL passed the same production safety layer
- whether required tokens/tables appear when specified
- end-to-end latency

A serious production evaluation set should include:

- normal analytical questions
- ambiguous questions
- impossible questions
- schema-edge cases
- prompt-injection attempts
- destructive requests
- expensive Cartesian joins
- attempts to access system catalogs
- queries requesting sensitive columns

The repository includes a starter set, not a claim that text-to-SQL evaluation has somehow become easy. Humanity has not received that patch yet.

---

# 8. Production deployment notes

For horizontal scaling:

- Run multiple stateless API replicas behind a load balancer.
- Use PostgreSQL connection pooling, or place PgBouncer in front of PostgreSQL.
- Keep schema cache TTL reasonably long.
- Put secrets in a managed secret store.
- Send logs to your centralized log platform.
- Scrape `/metrics` from Prometheus.
- Prefer a read replica for analytics traffic.
- Add per-user authentication and authorization before exposing real data.
- Add column-level policy and PII masking for sensitive datasets.
- Consider PostgreSQL Row-Level Security for multi-tenant databases.

Kubernetes manifests are included under `deploy/k8s/` as a starting point.

---

# 9. Why writes are disabled

This project executes only read queries by design.

A write-capable database agent is a different risk class. It should have:

- explicit intent classification
- a generated change plan
- an approval step
- parameterized mutations rather than free-form SQL when possible
- idempotency keys
- transaction boundaries
- audit logs
- before/after previews
- scoped write roles
- rollback/recovery procedures

See `docs/write-mode.md` for a production-safe extension design.

---

# 10. Repository layout

```text
postgres-database-agent/
├── README.md
├── pyproject.toml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── src/db_agent/
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── db.py
│   ├── graph.py
│   ├── llm.py
│   ├── logging.py
│   ├── models.py
│   ├── prompts.py
│   ├── safety.py
│   ├── schema.py
│   └── service.py
├── sql/init/
│   ├── 001_schema.sql
│   ├── 002_seed.sql
│   └── 003_readonly_role.sql
├── tests/
│   ├── test_safety.py
│   └── test_schema_ranking.py
├── evals/
│   ├── cases.jsonl
│   └── run_eval.py
├── docs/
│   ├── architecture.md
│   ├── security.md
│   ├── production.md
│   └── write-mode.md
└── deploy/k8s/
    ├── deployment.yaml
    └── service.yaml
```

---

# 11. Useful development commands

```bash
make install
make test
make lint
make run
make docker-up
make docker-down
```

---

# 12. Next engineering upgrades

For a larger production system, the next improvements I would prioritize are:

1. Authentication and authorization tied to database policy.
2. Column-level sensitivity metadata and masking.
3. Schema retrieval with embeddings for very large catalogs.
4. A semantic layer so business concepts such as “revenue” have canonical definitions.
5. Query result caching for repeated safe analytical questions.
6. Offline evaluation with hundreds of curated questions.
7. Human approval workflow for any future mutation tools.
8. Database observability for slow-query and load monitoring.

The important boundary is this: the LLM proposes a query; deterministic software and PostgreSQL decide whether it is allowed to run.

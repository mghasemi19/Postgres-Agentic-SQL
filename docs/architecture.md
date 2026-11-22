# Architecture

## Request lifecycle

A request passes through deterministic stages rather than giving an unconstrained ReAct loop direct database access.

1. **API validation** checks the request shape and question length.
2. **Schema retrieval** finds candidate tables and retrieves only their metadata.
3. **SQL generation** asks the LLM for a typed `SQLProposal`.
4. **AST validation** parses PostgreSQL and enforces policy.
5. **Execution** starts a read-only PostgreSQL transaction, sets a server-side timeout, optionally checks the query plan, and fetches a capped number of rows.
6. **Repair** is attempted only when PostgreSQL rejects an otherwise policy-approved query.
7. **Answer synthesis** receives only the user's question plus returned database rows.

## Why LangGraph

A database agent benefits from explicit control flow. LangGraph gives each stage a named node and lets the application decide exactly when retries or tool execution are allowed. The LLM does not choose arbitrary Python functions or get a generic shell-like tool surface.

## Component boundaries

```text
API
  -> DatabaseAgentService
       -> DatabaseAgentGraph
            -> SchemaCatalog
            -> LLM adapter
            -> SQLSafetyValidator
            -> Database executor
```

The boundaries make it straightforward to replace:

- the LLM provider
- the schema ranker
- the SQL policy
- PostgreSQL connection details
- observability infrastructure

without rewriting the full application.

## Scaling schema retrieval

For small and medium databases, lexical table ranking is enough to avoid sending every table to the LLM.

For very large catalogs, use:

1. one document per table containing name, description, columns, and relationships
2. embeddings for those documents
3. top-k retrieval by question
4. exact schema introspection only for retrieved tables

PostgreSQL + pgvector is a natural place to keep those schema embeddings if you want to avoid another infrastructure service.

## Scaling API traffic

The API is stateless. Multiple replicas can run behind a load balancer. The main shared resource is PostgreSQL, so use connection pooling and preferably a read replica for heavy analytics.

## Failure behavior

A failure must be boring:

- validation rejection -> no SQL executes
- timeout -> transaction rolls back
- planner-cost rejection -> transaction rolls back
- database syntax error -> bounded repair attempt
- exhausted retries -> user receives an error, not invented data

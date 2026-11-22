# Production deployment

## Recommended topology

```text
Client
  |
API Gateway / Auth
  |
Load Balancer
  |
+---------------------------+
| Database Agent API pods   |
|  replica 1                |
|  replica 2                |
|  replica N                |
+---------------------------+
  |             |
LLM API      PgBouncer
                |
          PostgreSQL read replica
```

## Authentication

The starter API intentionally does not invent an authentication system. Before exposing real company data, put the service behind your identity layer and pass a verified identity/role into the authorization policy.

## Connection pooling

SQLAlchemy's local pool is useful for one process. With many application replicas, add PgBouncer or a managed database proxy so total PostgreSQL connections stay bounded.

## Read replica

Analytical queries should normally run against a read replica. This reduces the chance that an expensive model-generated query affects transactional workloads.

## Observability

The service emits JSON logs and Prometheus metrics. In production, add:

- request counts by outcome
- LLM latency and token usage
- SQL execution latency
- database timeout count
- SQL rejection count by policy reason
- retry count
- top slow safe-query fingerprints
- read-replica CPU and I/O

Do not log full result rows if they may contain sensitive data.

## Rate limiting

Put rate limiting at the API gateway or ingress. Model calls and database scans both cost real money, a charming property shared by almost every useful cloud component.

## High availability

The API itself is stateless. Run multiple replicas and use readiness probes. Database and LLM provider availability remain external dependencies; configure sensible timeouts and retries rather than unbounded retries.

## Semantic layer

Real organizations have ambiguous terms:

- revenue
- active customer
- churn
- conversion
- gross margin

For high-stakes analytics, encode these definitions in governed views or a semantic layer. Do not expect an LLM to infer your CFO's private definition of “revenue” from column names.

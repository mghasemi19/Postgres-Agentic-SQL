from __future__ import annotations

import re

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from .models import SafetyResult


# AST node keys blocked anywhere in a statement. Using keys rather than importing every expression
# class keeps this resilient across SQLGlot versions.
BLOCKED_NODE_KEYS = {
    "alter",
    "analyze",
    "attach",
    "cache",
    "call",
    "command",
    "commit",
    "copy",
    "create",
    "delete",
    "detach",
    "drop",
    "execute",
    "grant",
    "insert",
    "load_data",
    "lock",
    "merge",
    "pragma",
    "revoke",
    "rollback",
    "set",
    "transaction",
    "truncate_table",
    "uncache",
    "update",
    "use",
}

BLOCKED_FUNCTIONS = {
    "dblink",
    "dblink_connect",
    "dblink_exec",
    "lo_export",
    "lo_import",
    "pg_ls_dir",
    "pg_read_binary_file",
    "pg_read_file",
    "pg_sleep",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "set_config",
}

SYSTEM_SCHEMAS = {"pg_catalog", "information_schema"}


class SQLSafetyValidator:
    def __init__(self, allowed_schemas: list[str], max_rows: int):
        self.allowed_schemas = {s.lower() for s in allowed_schemas}
        self.max_rows = max_rows

    def validate(self, sql: str) -> SafetyResult:
        sql = sql.strip().rstrip(";")
        if not sql:
            return SafetyResult(allowed=False, reason="The model returned empty SQL.")

        # A cheap first-pass rejection makes obvious prompt-injection output fail closed.
        if re.search(r"\b(copy|vacuum|reindex|cluster)\b", sql, flags=re.IGNORECASE):
            return SafetyResult(allowed=False, reason="Administrative SQL is not allowed.")

        try:
            statements = parse(sql, dialect="postgres")
        except ParseError as exc:
            return SafetyResult(allowed=False, reason=f"SQL could not be parsed: {exc}")

        if len(statements) != 1:
            return SafetyResult(allowed=False, reason="Only one SQL statement is allowed.")

        tree = statements[0]
        if tree is None:
            return SafetyResult(allowed=False, reason="SQL parsing returned no statement.")

        if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            return SafetyResult(allowed=False, reason="Only SELECT-style read queries are allowed.")

        for node in tree.walk():
            key = getattr(node, "key", "").lower()
            if key in BLOCKED_NODE_KEYS:
                return SafetyResult(allowed=False, reason=f"Blocked SQL operation: {key}.")

            if isinstance(node, exp.Table):
                schema = (node.db or "").lower()
                if schema in SYSTEM_SCHEMAS:
                    return SafetyResult(allowed=False, reason=f"System schema {schema} is blocked.")
                if schema and schema not in self.allowed_schemas:
                    return SafetyResult(
                        allowed=False,
                        reason=f"Schema {schema} is not in ALLOWED_SCHEMAS.",
                    )

            if isinstance(node, exp.Func):
                name = _function_name(node)
                if name in BLOCKED_FUNCTIONS:
                    return SafetyResult(allowed=False, reason=f"Function {name} is blocked.")

        # Force a row cap even when the LLM omits one. SQLGlot returns a copy from limit().
        limited = tree.limit(self.max_rows)
        safe_sql = limited.sql(dialect="postgres", pretty=False)
        return SafetyResult(allowed=True, sql=safe_sql)


def _function_name(node: exp.Func) -> str:
    try:
        if isinstance(node, exp.Anonymous):
            return (node.name or "").lower()
        return (node.sql_name() or "").lower()
    except Exception:
        return ""

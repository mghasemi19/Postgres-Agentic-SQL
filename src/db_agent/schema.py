'''
schema.py is the file that lets the agent inspect your PostgreSQL database structure 
and prepare a compact schema description for the LLM.

PostgreSQL
   ↓
inspect tables/columns/keys
   ↓
rank relevant tables
   ↓
build schema text
   ↓
send that context to the LLM
'''

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .config import Settings

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class TableSummary:
    schema: str
    table: str
    columns: tuple[str, ...]

    @property
    def fq_name(self) -> str:
        return f"{self.schema}.{self.table}"

'''
TableSummary(
    schema="public",
    table="orders",
    columns=("order_id", "customer_id", "status", "ordered_at", "currency")
)
'''    


class SchemaCatalog:
    def __init__(self, engine: Engine, settings: Settings):
        self.engine = engine
        self.settings = settings
        self._catalog: list[TableSummary] = []
        self._cached_at = 0.0



    # Reuse the discovered catalog until its configured cache lifetime expires.
    def _refresh_if_needed(self) -> None:
        now = time.monotonic()
        if self._catalog and now - self._cached_at < self.settings.schema_cache_ttl_seconds:
            return

        # SQLAlchemy inspection reads names and column metadata from PostgreSQL.
        inspector = inspect(self.engine)
        catalog: list[TableSummary] = []
        for schema in self.settings.allowed_schemas:
            table_names = inspector.get_table_names(schema=schema)
            view_names = inspector.get_view_names(schema=schema)
            for table in sorted(set(table_names + view_names)):
                columns = tuple(col["name"] for col in inspector.get_columns(table, schema=schema))
                catalog.append(TableSummary(schema=schema, table=table, columns=columns))

        self._catalog = catalog
        self._cached_at = now



    # Rank likely relevant tables so large schemas fit within the LLM context.
    def rank_tables(self, question: str) -> list[TableSummary]:
        self._refresh_if_needed()
        if len(self._catalog) <= self.settings.schema_top_k:
            return list(self._catalog)

        q_tokens = {token.lower() for token in _TOKEN_RE.findall(question)}

        def score(item: TableSummary) -> tuple[int, int, str]:
            table_tokens = {token.lower() for token in _TOKEN_RE.findall(item.table)}
            column_tokens = {
                token.lower()
                for column in item.columns
                for token in _TOKEN_RE.findall(column)
            }
            table_overlap = len(q_tokens & table_tokens)
            column_overlap = len(q_tokens & column_tokens)
            # Give table-name matches more weight than generic column matches like "id".
            return (table_overlap * 5 + column_overlap, table_overlap, item.fq_name)

        ranked = sorted(self._catalog, key=score, reverse=True)
        selected = ranked[: self.settings.schema_top_k]

        # If nothing matches, choose a stable alphabetic subset instead of arbitrary ordering.
        if score(selected[0])[0] == 0:
            return sorted(self._catalog, key=lambda x: x.fq_name)[: self.settings.schema_top_k]
        return selected

    '''
    100 database tables
        ↓
    rank_tables()
            ↓
    12 relevant tables
            ↓
            LLM
    '''



    # Format selected tables and their relationships as context for SQL generation.
    def context_for_question(self, question: str) -> str:
        self._refresh_if_needed()
        # SQLAlchemy inspection reads names and column metadata from PostgreSQL.
        inspector = inspect(self.engine)
        tables = self.rank_tables(question)
        chunks: list[str] = []

        for item in tables:
            # Include column types/nullability plus keys so the model can form valid joins.
            cols = inspector.get_columns(item.table, schema=item.schema)
            pk = inspector.get_pk_constraint(item.table, schema=item.schema) or {}
            fks = inspector.get_foreign_keys(item.table, schema=item.schema) or []

            chunks.append(f"TABLE {item.fq_name}")
            for col in cols:
                nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                chunks.append(f"  - {col['name']}: {col['type']} {nullable}")

            constrained = pk.get("constrained_columns") or []
            if constrained:
                chunks.append(f"  PRIMARY KEY ({', '.join(constrained)})")

            for fk in fks:
                local = ", ".join(fk.get("constrained_columns") or [])
                remote_schema = fk.get("referred_schema") or item.schema
                remote_table = fk.get("referred_table")
                remote_cols = ", ".join(fk.get("referred_columns") or [])
                if remote_table:
                    chunks.append(
                        f"  FOREIGN KEY ({local}) -> "
                        f"{remote_schema}.{remote_table}({remote_cols})"
                    )
            chunks.append("")

        # Return an explicit empty-catalog message rather than an empty prompt section.
        if not chunks:
            return "No accessible tables were discovered in the allowed schemas."
        return "\n".join(chunks).strip()

'''
TABLE public.orders
  - order_id: BIGINT NOT NULL
  - customer_id: BIGINT NOT NULL
  - status: TEXT NOT NULL
  - ordered_at: TIMESTAMP WITH TIME ZONE NOT NULL
  - currency: CHAR(3) NOT NULL

  PRIMARY KEY (order_id)

  FOREIGN KEY (customer_id)
    -> public.customers(customer_id)
and the samething for other tables, plus a final empty line.
'''    

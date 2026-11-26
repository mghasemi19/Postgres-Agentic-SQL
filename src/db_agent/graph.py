from __future__ import annotations

import json
from typing import Any, TypedDict

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from .config import Settings
from .db import Database
from .llm import build_llm
from .models import SQLProposal
from .prompts import ANSWER_SYSTEM_PROMPT, SQL_SYSTEM_PROMPT
from .safety import SQLSafetyValidator
from .schema import SchemaCatalog

logger = structlog.get_logger(__name__)


# Shared state passed between graph nodes; each node returns only the fields it updates.
class AgentState(TypedDict, total=False):   # means that not all fields must exist when the state is initialized.
    question: str
    request_id: str
    schema_context: str
    attempt: int
    sql: str
    sql_explanation: str
    validation_error: str
    execution_error: str
    columns: list[str]
    rows: list[dict[str, Any]]
    answer: str
    status: str


class DatabaseAgentGraph:


    # Assemble the schema catalog, SQL policy, model clients, and compiled workflow.
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.catalog = SchemaCatalog(database.engine, settings)
        self.validator = SQLSafetyValidator(settings.allowed_schemas, settings.max_rows)
        self.llm = build_llm(settings)
        self.sql_llm = self.llm.with_structured_output(SQLProposal)
        self.graph = self._build().compile()




    # Define the allowed order of work and the retry/rejection branches.
    def _build(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("inspect_schema", self.inspect_schema)
        graph.add_node("generate_sql", self.generate_sql)
        graph.add_node("validate_sql", self.validate_sql)
        graph.add_node("execute_sql", self.execute_sql)
        graph.add_node("summarize", self.summarize)
        graph.add_node("fail", self.fail)

        graph.add_edge(START, "inspect_schema")
        graph.add_edge("inspect_schema", "generate_sql")
        graph.add_edge("generate_sql", "validate_sql")
        graph.add_conditional_edges(
            "validate_sql",
            self.after_validation,
            {"execute": "execute_sql", "fail": "fail"},
        )
        graph.add_conditional_edges(
            "execute_sql",
            self.after_execution,
            {"retry": "generate_sql", "summarize": "summarize", "fail": "fail"},
        )
        graph.add_edge("summarize", END)
        graph.add_edge("fail", END)
        return graph




    # Select relevant database metadata before asking the model to write SQL.
    def inspect_schema(self, state: AgentState) -> AgentState:
        context = self.catalog.context_for_question(state["question"])
        return {"schema_context": context, "attempt": 0}




    # Ask for a typed SQL proposal, including any prior database error for repair.
    def generate_sql(self, state: AgentState) -> AgentState:
        attempt = int(state.get("attempt", 0)) + 1
        system = SQL_SYSTEM_PROMPT.format(
            schema_context=state["schema_context"],
            execution_error=state.get("execution_error", "None"),
        )
        proposal = self.sql_llm.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=state["question"]),
            ]
        )
        logger.info(
            "sql_generated",
            request_id=state.get("request_id"),
            attempt=attempt,
            sql=proposal.sql,
        )
        return {
            "attempt": attempt,
            "sql": proposal.sql,
            "sql_explanation": proposal.explanation,
            "validation_error": "",
        }




    # Apply deterministic SQL policy checks before any query reaches PostgreSQL.
    def validate_sql(self, state: AgentState) -> AgentState:
        result = self.validator.validate(state.get("sql", ""))
        if not result.allowed:
            logger.warning(
                "sql_rejected",
                request_id=state.get("request_id"),
                reason=result.reason,
            )
            return {
                "status": "rejected",
                "validation_error": result.reason or "SQL rejected.",
            }
        return {"sql": result.sql or "", "validation_error": ""}




    # Route rejected SQL to a safe failure response and approved SQL to execution.
    def after_validation(self, state: AgentState) -> str:
        return "fail" if state.get("validation_error") else "execute"




    # Run the validated query and store either its results or a sanitized error.
    def execute_sql(self, state: AgentState) -> AgentState:
        try:
            result = self.database.execute_readonly(state["sql"])
            logger.info(
                "sql_executed",
                request_id=state.get("request_id"),
                row_count=result.row_count,
                plan_cost=result.plan_cost,
            )
            return {
                "columns": result.columns,
                "rows": result.rows,
                "execution_error": "",
            }
        except Exception as exc:
            # Do not send full driver trace or credentials back to the LLM/user.
            error = _sanitize_db_error(str(exc))
            logger.warning(
                "sql_execution_failed",
                request_id=state.get("request_id"),
                attempt=state.get("attempt"),
                error=error,
            )
            return {"execution_error": error}




    # Retry database errors only while the configured attempt budget remains.
    def after_execution(self, state: AgentState) -> str:
        if not state.get("execution_error"):
            return "summarize"
        if int(state.get("attempt", 0)) <= self.settings.max_sql_retries:
            return "retry"
        return "fail"




    # Ask the model to explain the returned rows without adding unsupported facts.
    def summarize(self, state: AgentState) -> AgentState:
        compact_rows = state.get("rows", [])[: self.settings.max_rows]
        payload = json.dumps(
            {
                "columns": state.get("columns", []),
                "rows": compact_rows,
            },
            default=str,
            ensure_ascii=False,
        )
        response = self.llm.invoke(
            [
                SystemMessage(content=ANSWER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Question:\n{state['question']}\n\n"
                        f"Database result:\n{payload}"
                    )
                ),
            ]
        )
        answer = response.content if isinstance(response.content, str) else str(response.content)
        return {"answer": answer, "status": "ok"}




    # Turn validation and execution failures into clear user-facing responses.
    def fail(self, state: AgentState) -> AgentState:
        if state.get("validation_error"):
            return {
                "status": "rejected",
                "answer": f"The generated query was rejected by the safety policy: "
                f"{state['validation_error']}",
            }
        if state.get("execution_error"):
            return {
                "status": "error",
                "answer": "I could not execute a safe query for that request. "
                f"Database error: {state['execution_error']}",
            }
        return {"status": "error", "answer": "The database agent could not complete the request."}




    def invoke(self, *, question: str, request_id: str) -> AgentState:
        return self.graph.invoke({"question": question, "request_id": request_id})





def _sanitize_db_error(message: str) -> str:
    # Keep enough information for SQL repair while limiting accidental secret leakage.
    first_line = message.splitlines()[0].strip()
    return first_line[:600]

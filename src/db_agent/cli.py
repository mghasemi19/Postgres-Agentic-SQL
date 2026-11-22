from __future__ import annotations

import json

import httpx
import typer
from rich.console import Console
from rich.syntax import Syntax

from .config import get_settings
from .logging import configure_logging
from .service import DatabaseAgentService

app = typer.Typer(help="PostgreSQL database agent CLI")
console = Console()


@app.command()
def ask(question: str) -> None:
    """Run the agent directly in this process."""
    settings = get_settings()
    configure_logging(settings.log_level)
    result = DatabaseAgentService(settings).query(question)
    console.print(f"[bold]Status:[/bold] {result.status}")
    console.print(f"[bold]Answer:[/bold] {result.answer}")
    if result.sql:
        console.print("\n[bold]SQL[/bold]")
        console.print(Syntax(result.sql, "sql", word_wrap=True))
    if result.rows:
        console.print("\n[bold]Rows[/bold]")
        console.print_json(json.dumps(result.rows, default=str))


@app.command("ask-api")
def ask_api(
    question: str,
    url: str = typer.Option("http://localhost:8000", help="API base URL"),
) -> None:
    """Call a running database-agent API."""
    with httpx.Client(timeout=120) as client:
        response = client.post(f"{url.rstrip('/')}/v1/query", json={"question": question})
        response.raise_for_status()
        console.print_json(response.text)


if __name__ == "__main__":
    app()

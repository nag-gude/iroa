"""IROA CLI: in-process or --agent-url for microservices."""
from __future__ import annotations

import typer
import httpx
from elasticsearch import Elasticsearch

from iroa.env_loader import load_env
from iroa.config import get_settings

load_env()
from iroa.models import AnalyzeRequest, AnalyzeResponse
from iroa.agent.runner import run_agent
from iroa.tools.search import SearchTool
from iroa.tools.esql import ESQLTool

app = typer.Typer(help="IROA — Incident Response + Observability Agent. Search. Reason. Resolve.")


@app.command()
def version():
    """Show IROA version."""
    typer.echo("0.1.0")


def _make_es_client() -> Elasticsearch:
    s = get_settings()
    if s.elasticsearch_api_key:
        return Elasticsearch(s.elasticsearch_url, api_key=s.elasticsearch_api_key)
    if s.elasticsearch_user and s.elasticsearch_password:
        return Elasticsearch(s.elasticsearch_url, basic_auth=(s.elasticsearch_user, s.elasticsearch_password))
    return Elasticsearch(s.elasticsearch_url)


def _run_in_process(query: str, time_range: int, create_ticket: bool) -> AnalyzeResponse:
    es = _make_es_client()
    s = get_settings()
    search_tool = SearchTool(es, s.iroa_log_index_pattern, s.iroa_metrics_index_pattern)
    esql_tool = ESQLTool(es, s.iroa_log_index_pattern, s.iroa_metrics_index_pattern)
    ticketing = None
    if s.jira_base_url and s.jira_api_token and s.jira_email:
        from iroa.connectors.jira_connector import JiraConnector
        conn = JiraConnector(s.jira_base_url, s.jira_email, s.jira_api_token)
        ticketing = lambda **kw: conn.create_ticket(**kw)
    req = AnalyzeRequest(query=query, time_range_minutes=time_range, create_ticket=create_ticket)
    return run_agent(req, search_tool, esql_tool, ticketing)


@app.command()
def analyze(
    query: str = typer.Option(..., "--query", "-q", help="Natural language question or alert description"),
    time_range: int = typer.Option(15, "--time-range", "-t", help="Lookback minutes"),
    create_ticket: bool = typer.Option(False, "--create-ticket", help="Create ticket if configured"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
    agent_url: str | None = typer.Option(None, "--agent-url", help="Agent service URL for microservices mode"),
):
    if agent_url:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{agent_url.rstrip('/')}/analyze", json={"query": query, "time_range_minutes": time_range, "create_ticket": create_ticket})
            r.raise_for_status()
            result = AnalyzeResponse.model_validate(r.json())
    else:
        result = _run_in_process(query, time_range, create_ticket)

    if json_out:
        print(result.model_dump_json(indent=2))
    else:
        typer.echo("--- Summary ---")
        typer.echo(result.summary)
        typer.echo("\n--- Root cause ---")
        typer.echo(result.root_cause)
        if result.actions_taken:
            typer.echo("\n--- Actions ---")
            for a in result.actions_taken:
                typer.echo(f"  {a.action}: {a.identifier or a.system} {a.link or ''}")
        if result.audit_trail:
            typer.echo("\n--- Audit trail ---")
            for step in result.audit_trail:
                typer.echo(f"  {step}")


if __name__ == "__main__":
    import sys
    # Normalize argv so Typer sees "iroa analyze ..." (subcommand "analyze").
    # When run as "python -m iroa.cli analyze ...", argv can be [python, "-m", "iroa.cli", "analyze", ...]
    # or [path/to/cli.py, "analyze", ...]. Ensure prog name is "iroa" and first arg is "analyze".
    if len(sys.argv) >= 2 and sys.argv[1] == "-m" and len(sys.argv) >= 4 and sys.argv[2] in ("iroa.cli", "iroa"):
        sys.argv = ["iroa"] + sys.argv[3:]
    elif len(sys.argv) >= 2 and sys.argv[1] == "analyze":
        sys.argv = ["iroa", "analyze"] + sys.argv[2:]
    app(prog_name="iroa")

"""IROA monolith API (Elastic Agent Builder).

POST /analyze runs the Agent Builder agent (Search + ES|QL tools, reasoning, optional ticket).
Single process + demo UI at /. See docs/AGENT_BUILDER.md."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from elasticsearch import Elasticsearch

from iroa.env_loader import load_env
from iroa.config import get_settings

load_env()
from iroa.models import AnalyzeRequest, AnalyzeResponse
from iroa.agent.runner import run_agent
from iroa.tools.search import SearchTool
from iroa.tools.esql import ESQLTool
from iroa.connectors.jira_connector import JiraConnector


def make_es_client() -> Elasticsearch:
    """Connect to Elasticsearch (Elastic Cloud or self-managed). Uses ELASTICSEARCH_CLOUD_ID if set, else ELASTICSEARCH_URL."""
    s = get_settings()
    if s.elasticsearch_cloud_id:
        if s.elasticsearch_api_key:
            return Elasticsearch(cloud_id=s.elasticsearch_cloud_id, api_key=s.elasticsearch_api_key)
        if s.elasticsearch_user and s.elasticsearch_password:
            return Elasticsearch(cloud_id=s.elasticsearch_cloud_id, basic_auth=(s.elasticsearch_user, s.elasticsearch_password))
        return Elasticsearch(cloud_id=s.elasticsearch_cloud_id)
    if s.elasticsearch_api_key:
        return Elasticsearch(s.elasticsearch_url, api_key=s.elasticsearch_api_key)
    if s.elasticsearch_user and s.elasticsearch_password:
        return Elasticsearch(s.elasticsearch_url, basic_auth=(s.elasticsearch_user, s.elasticsearch_password))
    return Elasticsearch(s.elasticsearch_url)


def make_ticketing_callback():
    s = get_settings()
    if s.jira_base_url and s.jira_api_token and s.jira_email:
        conn = JiraConnector(s.jira_base_url, s.jira_email, s.jira_api_token)
        return lambda **kw: conn.create_ticket(**kw)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.es = make_es_client()
    s = get_settings()
    app.state.search_tool = SearchTool(app.state.es, s.iroa_log_index_pattern, s.iroa_metrics_index_pattern)
    app.state.esql_tool = ESQLTool(app.state.es, s.iroa_log_index_pattern, s.iroa_metrics_index_pattern)
    app.state.ticketing_callback = make_ticketing_callback()
    yield
    app.state.es.close()


app = FastAPI(title="IROA", description="Incident Response + Observability Agent. Search. Reason. Resolve.", version="0.1.0", lifespan=lifespan)

# Demo UI: static files live in project root / static (sibling of iroa/)
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_demo_ui():
    """Serve the demo frontend (HTML) at root."""
    index = _STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Demo UI not found (missing static/index.html)")
    return FileResponse(index, media_type="text/html")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    try:
        return run_agent(req, search_tool=app.state.search_tool, esql_tool=app.state.esql_tool, ticketing_callback=app.state.ticketing_callback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "IROA"}

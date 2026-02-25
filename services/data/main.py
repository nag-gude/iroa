"""Data service: Search + ES|QL over Elasticsearch. Port 8001.

Fetches logs (and metrics) from Elasticsearch—including Elastic Cloud when
ELASTICSEARCH_URL or ELASTICSEARCH_CLOUD_ID is set—and exposes them to the agent
for analysis (correlation, root-cause hypothesis). The agent service calls this
service to get data, then runs the full analysis loop."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError, NotFoundError, ConnectionError as ESConnectionError

from iroa.env_loader import load_env
from iroa.tools.search import SearchTool
from iroa.tools.esql import ESQLTool
from services.data.config import get_settings

load_env()


def _es_error_detail(e: Exception) -> str:
    """Build a clear error string for Elasticsearch/connection failures."""
    if isinstance(e, ApiError):
        body = getattr(e, "body", None) or {}
        if isinstance(body, dict):
            err = body.get("error", {})
            if isinstance(err, dict):
                return f"{err.get('type', 'api_error')}: {err.get('reason', str(e))}"
        return str(e)
    if isinstance(e, ESConnectionError):
        return f"Connection failed (check ELASTICSEARCH_URL and network): {e!s}"
    return str(e)


def _is_unknown_resource(e: Exception) -> bool:
    """True if Elasticsearch returned 404 'Unknown resource' (e.g. Serverless)."""
    msg = str(e).lower()
    if isinstance(e, NotFoundError):
        return True
    if isinstance(e, ApiError):
        code = getattr(e, "status_code", None)
        if code == 404:
            return True
    return "unknown resource" in msg


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


class SearchLogsRequest(BaseModel):
    query_text: str | None = None
    service: str | None = None
    log_level: str | None = None
    time_range_minutes: int = Field(15, ge=1, le=10080)
    size: int = Field(50, ge=1, le=500)


class SearchLogsResponse(BaseModel):
    hits: list[dict[str, Any]]
    total: int
    index_pattern: str
    es_error: str | None = None  # e.g. "unknown_resource" when ES returns 404 (Serverless)


class SearchMetricsRequest(BaseModel):
    time_range_minutes: int = Field(15, ge=1, le=10080)
    size: int = Field(100, ge=1, le=1000)


class SearchMetricsResponse(BaseModel):
    hits: list[dict[str, Any]]
    total: int
    index_pattern: str


class ESQLRunRequest(BaseModel):
    query: str = Field(..., min_length=1)


class ESQLErrorCountByHostRequest(BaseModel):
    time_range_minutes: int = Field(15, ge=1, le=10080)
    log_level: str = "error"


class ESQLResponse(BaseModel):
    columns: list[dict[str, str]]
    values: list[list[Any]]
    query: str
    es_error: str | None = None  # e.g. "unknown_resource" when ES returns 404 (Serverless)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.es = make_es_client()
    s = get_settings()
    app.state.search_tool = SearchTool(app.state.es, s.iroa_log_index_pattern, s.iroa_metrics_index_pattern)
    app.state.esql_tool = ESQLTool(app.state.es, s.iroa_log_index_pattern, s.iroa_metrics_index_pattern)
    yield
    app.state.es.close()


app = FastAPI(title="IROA Data Service", description="Search + ES|QL over Elasticsearch.", version="0.1.0", lifespan=lifespan)


@app.post("/search/logs", response_model=SearchLogsResponse)
async def search_logs(req: SearchLogsRequest):
    try:
        r = app.state.search_tool.search_logs(
            query_text=req.query_text, service=req.service, log_level=req.log_level,
            time_range_minutes=req.time_range_minutes, size=req.size,
        )
        hits = [{"_index": h.get("_index"), "_id": h.get("_id"), "_source": h.get("_source", {})} for h in r.hits]
        return SearchLogsResponse(hits=hits, total=r.total, index_pattern=r.index_pattern)
    except Exception as e:
        if _is_unknown_resource(e):
            return SearchLogsResponse(hits=[], total=0, index_pattern=app.state.search_tool.log_index_pattern, es_error="unknown_resource")
        raise HTTPException(status_code=500, detail=_es_error_detail(e))


@app.post("/search/metrics", response_model=SearchMetricsResponse)
async def search_metrics(req: SearchMetricsRequest):
    try:
        r = app.state.search_tool.search_metrics(time_range_minutes=req.time_range_minutes, size=req.size)
        hits = [{"_index": h.get("_index"), "_id": h.get("_id"), "_source": h.get("_source", {})} for h in r.hits]
        return SearchMetricsResponse(hits=hits, total=r.total, index_pattern=r.index_pattern)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_es_error_detail(e))


@app.post("/esql/run", response_model=ESQLResponse)
async def esql_run(req: ESQLRunRequest):
    try:
        r = app.state.esql_tool.run(req.query)
        return ESQLResponse(columns=r.columns, values=r.values, query=r.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_es_error_detail(e))


@app.post("/esql/error-count-by-host", response_model=ESQLResponse)
async def esql_error_count_by_host(req: ESQLErrorCountByHostRequest):
    try:
        r = app.state.esql_tool.error_count_by_host(time_range_minutes=req.time_range_minutes, log_level=req.log_level)
        return ESQLResponse(columns=r.columns, values=r.values, query=r.query)
    except Exception as e:
        if _is_unknown_resource(e):
            return ESQLResponse(columns=[], values=[], query="", es_error="unknown_resource")
        raise HTTPException(status_code=500, detail=_es_error_detail(e))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "iroa-data"}

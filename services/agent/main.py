"""Agent service: orchestrator. POST /analyze + demo UI at /. Port 8000."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from iroa.env_loader import load_env
from iroa.models import AnalyzeRequest, AnalyzeResponse
from services.agent.orchestrator import run_orchestrator
from services.agent.config import get_settings

load_env()

# Static UI: use STATIC_DIR if set (Docker: /app/static), else repo root / static
_STATIC_DIR = Path(os.environ.get("STATIC_DIR", "") or str(Path(__file__).resolve().parent.parent.parent / "static"))

app = FastAPI(title="IROA Agent Service", description="Orchestrator: Search. Reason. Resolve.", version="0.1.0")


@app.get("/", include_in_schema=False)
async def serve_demo_ui():
    """Serve the demo frontend at root (Docker Compose: open agent URL for the UI)."""
    index = _STATIC_DIR / "index.html"
    if not _STATIC_DIR.exists() or not index.exists():
        raise HTTPException(
            status_code=404,
            detail="Demo UI not found (missing static files). Ensure the agent image was built with COPY static/.",
        )
    return FileResponse(index, media_type="text/html")


if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    s = get_settings()
    try:
        return run_orchestrator(
            req,
            data_service_url=s.data_service_url,
            actions_service_url=s.actions_service_url,
            timeout=s.timeout_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "iroa-agent"}

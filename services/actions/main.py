"""Actions service: create tickets (Jira). Port 8002."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from iroa.env_loader import load_env
from iroa.connectors.jira_connector import JiraConnector
from services.actions.config import get_settings

load_env()


class CreateTicketRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field("")
    severity: str = Field("medium")
    system: str = Field("jira")


class CreateTicketResponse(BaseModel):
    action: str = "create_ticket"
    system: str | None = None
    identifier: str | None = None
    link: str | None = None


app = FastAPI(title="IROA Actions Service", description="Ticketing (Jira).", version="0.1.0")


def _get_jira_connector() -> JiraConnector | None:
    s = get_settings()
    if s.jira_base_url and s.jira_api_token and s.jira_email:
        return JiraConnector(s.jira_base_url, s.jira_email, s.jira_api_token, project_key=s.jira_project_key)
    return None


@app.post("/tickets", response_model=CreateTicketResponse)
async def create_ticket(req: CreateTicketRequest):
    if req.system.lower() != "jira":
        raise HTTPException(status_code=400, detail="Only 'jira' is supported")
    conn = _get_jira_connector()
    if not conn:
        raise HTTPException(status_code=503, detail="Ticketing not configured")
    try:
        result = conn.create_ticket(title=req.title, description=req.description, severity=req.severity)
        if not result:
            raise HTTPException(status_code=502, detail="Ticket creation returned no result (Jira API did not return 201)")
        return CreateTicketResponse(action=result.action, system=result.system, identifier=result.identifier, link=result.link)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "iroa-actions", "ticketing_configured": _get_jira_connector() is not None}

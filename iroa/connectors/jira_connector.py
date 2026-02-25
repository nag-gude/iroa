"""Jira connector: create issue via REST API (Jira Cloud v3 uses ADF for description)."""
from __future__ import annotations

import httpx

from iroa.connectors.base import BaseTicketingConnector
from iroa.models import ActionTaken


def _plain_text_to_adf(text: str) -> dict:
    """Convert plain text to Atlassian Document Format (ADF) for Jira Cloud API v3."""
    if not (text or "").strip():
        text = "(No description)"
    # One paragraph per line; escape for JSON text node
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        lines = [text.strip() or "(No description)"]
    content = []
    for line in lines:
        # ADF text nodes: newlines in text are not allowed, use separate paragraphs
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": line[:5000]}],
        })
    return {"type": "doc", "version": 1, "content": content}


class JiraConnector(BaseTicketingConnector):
    def __init__(self, base_url: str, email: str, api_token: str, project_key: str = "IROA"):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key

    def create_ticket(
        self,
        *,
        title: str,
        description: str,
        severity: str = "medium",
        **kwargs: str,
    ) -> ActionTaken | None:
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": title[:255],
                "description": _plain_text_to_adf(description or ""),
                "issuetype": {"name": kwargs.get("issue_type", "Task")},
            }
        }
        if severity and severity.lower() == "high":
            payload["fields"]["priority"] = {"name": "High"}
        with httpx.Client() as client:
            r = client.post(
                f"{self.base_url}/rest/api/3/issue",
                json=payload,
                auth=(self.email, self.api_token),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=15.0,
            )
        if r.status_code != 201:
            try:
                err_body = r.json()
                msg = err_body.get("errorMessages") or err_body.get("errors") or str(err_body)
                if isinstance(msg, list):
                    msg = "; ".join(str(m) for m in msg[:5])
                msg = str(msg)[:400]
            except Exception:
                msg = (r.text[:400] if r.text else r.reason_phrase) or "unknown"
            raise RuntimeError(f"Jira API returned {r.status_code}: {msg}")
        data = r.json()
        key = data.get("key")
        link = f"{self.base_url}/browse/{key}" if key else None
        return ActionTaken(action="create_ticket", system="Jira", identifier=key, link=link)

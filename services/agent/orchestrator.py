"""Orchestrator: call Data + Actions services over HTTP, then reason and respond."""
from __future__ import annotations

import httpx
from typing import Any

from iroa.models import AnalyzeRequest, AnalyzeResponse, Citation, ActionTaken


def _response_error_detail(response: httpx.Response) -> str:
    """Extract error detail from a failed HTTP response for the audit trail."""
    try:
        body = response.json()
        if isinstance(body, dict) and "detail" in body:
            return body["detail"]
    except Exception:
        pass
    return response.text[:500] if response.text else response.reason_phrase or "Unknown error"


def run_orchestrator(
    request: AnalyzeRequest,
    data_service_url: str,
    actions_service_url: str,
    timeout: float = 60.0,
) -> AnalyzeResponse:
    audit: list[str] = []
    citations: list[Citation] = []
    actions_taken: list[ActionTaken] = []
    time_range = request.time_range_minutes
    query_text = request.query
    service = request.alert.service if request.alert else None

    audit.append("Alert received: " + (query_text[:80] + "..." if len(query_text) > 80 else query_text))
    search_data: dict[str, Any] | None = None
    esql_data: dict[str, Any] | None = None

    with httpx.Client(timeout=timeout) as client:
        audit.append("Calling data service: ES|QL error count by host")
        try:
            r = client.post(
                f"{data_service_url.rstrip('/')}/esql/error-count-by-host",
                json={"time_range_minutes": time_range, "log_level": "error"},
            )
            r.raise_for_status()
            esql_data = r.json()
            audit.append(f"ES|QL returned {len(esql_data.get('values', []))} rows")
            for row in (esql_data.get("values") or [])[:10]:
                cols = [c["name"] for c in esql_data.get("columns", [])]
                citations.append(Citation(type="esql", snippet=str(dict(zip(cols, row))), fields=dict(zip(cols, row))))
        except httpx.HTTPStatusError as e:
            detail = _response_error_detail(e.response)
            audit.append(f"Data service ES|QL failed (non-fatal): {detail}")
        except Exception as e:
            audit.append(f"Data service ES|QL failed (non-fatal): {e}")

        audit.append("Calling data service: Search logs")
        try:
            r = client.post(
                f"{data_service_url.rstrip('/')}/search/logs",
                json={"query_text": query_text, "service": service, "time_range_minutes": time_range, "size": 20},
            )
            r.raise_for_status()
            search_data = r.json()
            total = search_data.get("total", 0)
            hits = search_data.get("hits", [])
            audit.append(f"Search returned {total} hits (showing {len(hits)})")
            for h in hits[:10]:
                src = h.get("_source", {}) or {}
                err = src.get("error")
                msg = src.get("message") or (err.get("message") if isinstance(err, dict) else None) or str(src)[:200]
                snippet = (msg[:500] if isinstance(msg, str) else str(msg)[:500]) if msg else None
                citations.append(
                    Citation(
                        type="search",
                        index=h.get("_index"),
                        id=h.get("_id"),
                        snippet=snippet,
                        fields={"@timestamp": src.get("@timestamp"), "log.level": src.get("log.level")},
                    )
                )
        except httpx.HTTPStatusError as e:
            detail = _response_error_detail(e.response)
            audit.append(f"Data service Search failed: {detail}")
        except Exception as e:
            audit.append(f"Data service Search failed: {e}")

        summary, root_cause, confidence = _reason_over_http_responses(query_text, search_data, esql_data, time_range, audit)

        if request.create_ticket:
            audit.append("Calling actions service: create ticket")
            try:
                r = client.post(
                    f"{actions_service_url.rstrip('/')}/tickets",
                    json={
                        "title": f"IROA: {summary[:60]}",
                        "description": root_cause,
                        "severity": request.alert.severity if request.alert else "medium",
                        "system": "jira",
                    },
                )
                r.raise_for_status()
                data = r.json()
                actions_taken.append(
                    ActionTaken(action=data.get("action", "create_ticket"), system=data.get("system"), identifier=data.get("identifier"), link=data.get("link"))
                )
                audit.append(f"Ticket created: {data.get('identifier') or data.get('system')}")
            except httpx.HTTPStatusError as e:
                detail = _response_error_detail(e.response)
                audit.append(f"Actions service ticket failed: {detail}")
            except Exception as e:
                audit.append(f"Actions service ticket failed: {e}")

    explanation = _build_explanation_http(time_range, search_data, esql_data, audit)
    return AnalyzeResponse(
        summary=summary,
        root_cause=root_cause,
        evidence=citations[:30],
        actions_taken=actions_taken,
        explanation=explanation,
        confidence=confidence,
        audit_trail=audit,
    )


def _is_unknown_resource_error(audit: list[str]) -> bool:
    """True if the audit shows Elasticsearch 404 'Unknown resource' (e.g. Serverless)."""
    combined = " ".join(audit).lower()
    return "unknown resource" in combined and ("404" in combined or "not found" in combined)


def _has_es_unknown_resource(search_data: dict[str, Any] | None, esql_data: dict[str, Any] | None) -> bool:
    """True if Data service returned 200 with es_error=unknown_resource (ES 404 / Serverless)."""
    if (search_data or {}).get("es_error") == "unknown_resource":
        return True
    if (esql_data or {}).get("es_error") == "unknown_resource":
        return True
    return False


def _both_search_and_esql_unknown_resource(search_data: dict[str, Any] | None, esql_data: dict[str, Any] | None) -> bool:
    """True only when both Search and ES|QL returned es_error=unknown_resource (e.g. full Serverless)."""
    return (search_data or {}).get("es_error") == "unknown_resource" and (esql_data or {}).get("es_error") == "unknown_resource"


def _reason_over_http_responses(
    query: str,
    search_data: dict[str, Any] | None,
    esql_data: dict[str, Any] | None,
    time_range_minutes: int,
    audit: list[str] | None = None,
) -> tuple[str, str, str]:
    no_search = not search_data or (search_data.get("total", 0) == 0 and not search_data.get("hits"))
    no_esql = not esql_data or (len(esql_data.get("values") or []) == 0)
    if no_search and no_esql:
        # Only show "Unknown resource. No data was retrieved" when BOTH Search and ES|QL returned 404 (e.g. Serverless).
        # If only ES|QL failed (404) but Search returned 200 with 0 hits, data may exist with different index or time range.
        if _both_search_and_esql_unknown_resource(search_data, esql_data):
            return (
                "Elasticsearch returned 404 (Unknown resource). No data was retrieved.",
                "Elasticsearch Serverless or this API may not support the operations IROA needs. Use a classic Elasticsearch deployment or local Docker (see deployment docs).",
                "low",
            )
        if _has_es_unknown_resource(search_data, esql_data) or (audit and _is_unknown_resource_error(audit)):
            return (
                "No data found for the given time range. ES|QL returned 404 (not available on this deployment).",
                "If you see data in Kibana, ensure IROA_LOG_INDEX_PATTERN (default logs-*) matches your indices and the time range includes your data. Use a classic Elasticsearch deployment (not Serverless) for full Search + ES|QL support.",
                "low",
            )
        return (
            "No data found in Elasticsearch for the given time range.",
            "Unable to determine root cause: no log or metric data matched the query. If you see data in Kibana, ensure IROA_LOG_INDEX_PATTERN (default logs-*) matches your indices and the time range includes your data.",
            "low",
        )
    parts = []
    hits = (search_data or {}).get("hits", [])
    total = (search_data or {}).get("total", 0)
    if hits:
        parts.append(f"Found {total} log events in the last {time_range_minutes} minutes.")
        first = hits[0].get("_source", {})
        level = first.get("log.level") or "unknown"
        svc = first.get("service", {}).get("name") if isinstance(first.get("service"), dict) else first.get("service.name")
        if level == "error":
            parts.append("Errors are present in the logs.")
        if svc:
            parts.append(f"Service '{svc}' appears in the result set.")
    else:
        parts.append("No matching log events in the given time range.")
    values = (esql_data or {}).get("values", [])
    columns = (esql_data or {}).get("columns", [])
    if values and columns:
        col_names = [c["name"] for c in columns]
        if "host.name" in col_names and "count" in col_names:
            hi, ci = col_names.index("host.name"), col_names.index("count")
            top = values[0]
            host, count = top[hi], top[ci]
            parts.append(f"ES|QL aggregation: highest error count by host is {count} on '{host}'.")
    summary = " ".join(parts)
    root_cause = "Based on Elasticsearch Search and ES|QL results: " + (summary if len(summary) < 300 else summary[:297] + "...")
    confidence = "medium" if (hits or values) else "low"
    return summary, root_cause, confidence


def _build_explanation_http(
    time_range: int,
    search_data: dict[str, Any] | None,
    esql_data: dict[str, Any] | None,
    audit: list[str] | None = None,
) -> str:
    parts = [f"IROA analyzed the query over the last {time_range} minutes.", "Called Data Service (Search + ES|QL) over Elasticsearch."]
    if search_data:
        parts.append(f"Search returned {search_data.get('total', 0)} documents; citations included.")
    if esql_data:
        parts.append(f"ES|QL returned {len(esql_data.get('values', []))} aggregated rows.")
    no_data = (not search_data or (search_data.get("total", 0) == 0)) and (not esql_data or len(esql_data.get("values") or []) == 0)
    if no_data and _both_search_and_esql_unknown_resource(search_data, esql_data):
        parts.append("Elasticsearch returned 404 (Unknown resource). Connect a classic Elasticsearch deployment or local Docker (see deployment docs).")
    elif no_data and (_has_es_unknown_resource(search_data, esql_data) or (audit and _is_unknown_resource_error(audit))):
        parts.append("No data in range; ES|QL may be unavailable (404). Ensure IROA_LOG_INDEX_PATTERN and time range match your data. Use classic Elasticsearch for full support.")
    else:
        parts.append("Correlation and root-cause hypothesis are based on these results.")
    return " ".join(parts)

"""Core Agent Loop: Alert -> ES|QL -> Search -> correlate -> hypothesis -> ticket -> audit -> explanation."""
from __future__ import annotations

from typing import Callable

from iroa.models import AnalyzeRequest, AnalyzeResponse, Citation, ActionTaken
from iroa.tools.search import SearchTool, SearchToolResult
from iroa.tools.esql import ESQLTool, ESQLToolResult


def run_agent(
    request: AnalyzeRequest,
    search_tool: SearchTool,
    esql_tool: ESQLTool,
    ticketing_callback: Callable[..., ActionTaken | None] | None = None,
) -> AnalyzeResponse:
    audit: list[str] = []
    citations: list[Citation] = []
    actions_taken: list[ActionTaken] = []
    time_range = request.time_range_minutes
    query_text = request.query
    service = request.alert.service if request.alert else None

    audit.append("Alert received: " + (query_text[:80] + "..." if len(query_text) > 80 else query_text))
    audit.append("Running ES|QL: error count by host")
    try:
        esql_result = esql_tool.error_count_by_host(time_range_minutes=time_range)
        audit.append(f"ES|QL returned {len(esql_result.values)} rows")
        for row in esql_result.values[:10]:
            citations.append(
                Citation(
                    type="esql",
                    index=esql_tool.log_index_pattern,
                    snippet=str(dict(zip([c["name"] for c in esql_result.columns], row))),
                    fields=dict(zip([c["name"] for c in esql_result.columns], row)),
                )
            )
    except Exception as e:
        audit.append(f"ES|QL step failed (non-fatal): {e}")
        esql_result = None

    audit.append("Running Search over log indices")
    try:
        search_result: SearchToolResult = search_tool.search_logs(
            query_text=query_text, service=service, time_range_minutes=time_range, size=20,
        )
        audit.append(f"Search returned {search_result.total} hits (showing {len(search_result.hits)})")
        for h in search_result.hits[:10]:
            src = h.get("_source", {})
            msg = src.get("message") or (src.get("error") or {}).get("message") if isinstance(src.get("error"), dict) else str(src)[:200]
            citations.append(
                Citation(
                    type="search",
                    index=h.get("_index"),
                    id=h.get("_id"),
                    snippet=msg[:500] if isinstance(msg, str) else str(msg)[:500],
                    fields={"@timestamp": src.get("@timestamp"), "log.level": src.get("log.level")},
                )
            )
    except Exception as e:
        audit.append(f"Search step failed: {e}")
        search_result = None

    audit.append("Correlating results and generating hypothesis")
    summary, root_cause, confidence = _reason_over_results(
        query_text, search_result, esql_result, time_range, audit,
    )

    if request.create_ticket and ticketing_callback:
        try:
            action = ticketing_callback(
                title=f"IROA: {summary[:60]}",
                description=root_cause,
                severity=request.alert.severity if request.alert else "medium",
            )
            if action:
                actions_taken.append(action)
                audit.append(f"Ticket created: {action.identifier or action.system}")
        except Exception as e:
            audit.append(f"Ticket creation failed: {e}")

    explanation = _build_explanation(query_text, search_result, esql_result, time_range, audit)
    return AnalyzeResponse(
        summary=summary,
        root_cause=root_cause,
        evidence=citations[:30],
        actions_taken=actions_taken,
        explanation=explanation,
        confidence=confidence,
        audit_trail=audit,
    )


def _is_unknown_resource_in_audit(audit: list[str]) -> bool:
    """True if the audit shows Elasticsearch 404 'Unknown resource' (e.g. Serverless)."""
    combined = " ".join(audit).lower()
    return "unknown resource" in combined


def _reason_over_results(
    query: str,
    search_result: SearchToolResult | None,
    esql_result: ESQLToolResult | None,
    time_range_minutes: int,
    audit: list[str] | None = None,
) -> tuple[str, str, str]:
    if not search_result and not esql_result:
        if audit and _is_unknown_resource_in_audit(audit):
            return (
                "Elasticsearch returned 404 (Unknown resource). No data was retrieved.",
                "Elasticsearch Serverless or this API may not support the operations IROA needs. Use a classic Elasticsearch deployment or local Docker (see deployment docs).",
                "low",
            )
        return (
            "No data found in Elasticsearch for the given time range.",
            "Unable to determine root cause: no log or metric data matched the query.",
            "low",
        )
    parts = []
    if search_result and search_result.hits:
        parts.append(f"Found {search_result.total} log events in the last {time_range_minutes} minutes.")
        first = search_result.hits[0].get("_source", {})
        level = first.get("log.level") or "unknown"
        svc = first.get("service", {}).get("name") or first.get("service.name")
        if level == "error":
            parts.append("Errors are present in the logs.")
        if svc:
            parts.append(f"Service '{svc}' appears in the result set.")
    else:
        parts.append("No matching log events in the given time range.")
    if esql_result and esql_result.values:
        col_names = [c["name"] for c in esql_result.columns]
        if "host.name" in col_names and "count" in col_names:
            hi, ci = col_names.index("host.name"), col_names.index("count")
            top = esql_result.values[0]
            host, count = top[hi], top[ci]
            parts.append(f"ES|QL aggregation: highest error count by host is {count} on '{host}'.")
    summary = " ".join(parts)
    root_cause = "Based on Elasticsearch Search and ES|QL results: " + (summary if len(summary) < 300 else summary[:297] + "...")
    confidence = "medium" if (search_result and search_result.hits) or (esql_result and esql_result.values) else "low"
    return summary, root_cause, confidence


def _build_explanation(
    query: str,
    search_result: SearchToolResult | None,
    esql_result: ESQLToolResult | None,
    time_range: int,
    audit: list[str] | None = None,
) -> str:
    parts = [
        f"IROA analyzed the query over the last {time_range} minutes.",
        "Searched Elasticsearch log indices (Search API) for relevant events.",
        "Ran ES|QL aggregations (error count by host) over the same indices.",
    ]
    if search_result:
        parts.append(f"Retrieved {search_result.total} documents; citations are included.")
    if esql_result:
        parts.append(f"ES|QL returned {len(esql_result.values)} aggregated rows.")
    if not search_result and not esql_result and audit and _is_unknown_resource_in_audit(audit):
        parts.append("Elasticsearch returned 404 (Unknown resource). Connect a classic Elasticsearch deployment or local Docker (see deployment docs).")
    else:
        parts.append("Correlation and root-cause hypothesis are based on these Elasticsearch results.")
    return " ".join(parts)

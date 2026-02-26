"""Elastic Agent Builder — ES|QL tool.

ES|QL queries for aggregations, filtering, time bucketing. Used by the Agent Builder
agent for analytics (e.g. error count by host). See docs/AGENT_BUILDER.md."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elasticsearch import Elasticsearch

# Time condition: use @timestamp only (works when event.created is not in the mapping)
def _time_filter_esql(time_range_minutes: int) -> str:
    return f"@timestamp >= NOW() - {time_range_minutes} minutes"


@dataclass
class ESQLToolResult:
    columns: list[dict[str, str]]
    values: list[list[Any]]
    query: str
    index_pattern: str


class ESQLTool:
    def __init__(
        self,
        client: Elasticsearch,
        log_index_pattern: str = "logs-*",
        metrics_index_pattern: str = "metrics-*",
    ):
        self.client = client
        self.log_index_pattern = log_index_pattern
        self.metrics_index_pattern = metrics_index_pattern

    def run(self, query: str) -> ESQLToolResult:
        if hasattr(self.client, "esql") and hasattr(self.client.esql, "query"):
            resp = self.client.esql.query(query=query)
        else:
            resp = self.client.transport.perform_request(method="POST", url="/_query", body={"query": query})
        cols = resp.get("columns", [])
        values = resp.get("values", [])
        return ESQLToolResult(columns=cols, values=values, query=query, index_pattern="")

    def error_count_by_host(self, *, time_range_minutes: int = 15, log_level: str = "error") -> ESQLToolResult:
        time_cond = _time_filter_esql(time_range_minutes)
        # When log.level exists: filter by it (case-insensitive). When it doesn't, count all docs by host.
        level_lower = log_level.lower().replace('"', '')
        level_filter = f'AND TO_LOWER(TO_STRING(log.level)) == "{level_lower}"'
        q = f'''FROM {self.log_index_pattern}
        | WHERE {time_cond} {level_filter}
        | STATS count = count() BY host.name
        | SORT count DESC
        | LIMIT 20'''
        try:
            return self.run(q.strip())
        except Exception:
            # Fallback when log.level is not in the mapping: count by host without level filter
            q_fallback = f'''FROM {self.log_index_pattern}
        | WHERE {time_cond}
        | STATS count = count() BY host.name
        | SORT count DESC
        | LIMIT 20'''
            return self.run(q_fallback.strip())

    def error_count_over_time(self, *, time_range_minutes: int = 15, bucket_span: str = "1 minute", log_level: str = "error") -> ESQLToolResult:
        time_cond = _time_filter_esql(time_range_minutes)
        level_lower = log_level.lower().replace('"', '')
        q = f'''FROM {self.log_index_pattern}
        | WHERE {time_cond} AND TO_LOWER(TO_STRING(log.level)) == "{level_lower}"
        | STATS count = count() BY BUCKET(@timestamp, {bucket_span})
        | SORT @timestamp'''
        return self.run(q.strip())

    def search_with_esql(
        self,
        *,
        filter_message_contains: str | None = None,
        service_name: str | None = None,
        time_range_minutes: int = 15,
        limit: int = 20,
    ) -> ESQLToolResult:
        where_parts = [_time_filter_esql(time_range_minutes)]
        if service_name:
            where_parts.append(f'string(service.name) == "{service_name}"')
        if filter_message_contains:
            where_parts.append(f'string(message) LIKE "*{filter_message_contains}*"')
        where_clause = " AND ".join(where_parts)
        q = f'''FROM {self.log_index_pattern}
        | WHERE {where_clause}
        | SORT @timestamp DESC NULLS LAST
        | LIMIT {limit}'''
        return self.run(q.strip())

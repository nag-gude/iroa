"""Elasticsearch Search tool — retrieve relevant logs/metrics by query and time range."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from elasticsearch import Elasticsearch

# Time field for range filter (use @timestamp only so it works when event.created is missing)
TIME_FIELD = "@timestamp"


@dataclass
class SearchToolResult:
    hits: list[dict[str, Any]]
    total: int
    index_pattern: str
    query: dict[str, Any]
    time_range: tuple[datetime, datetime]


class SearchTool:
    def __init__(
        self,
        client: Elasticsearch,
        log_index_pattern: str = "logs-*",
        metrics_index_pattern: str = "metrics-*",
    ):
        self.client = client
        self.log_index_pattern = log_index_pattern
        self.metrics_index_pattern = metrics_index_pattern

    def search_logs(
        self,
        *,
        query_text: str | None = None,
        service: str | None = None,
        log_level: str | None = None,
        time_range_minutes: int = 15,
        size: int = 50,
    ) -> SearchToolResult:
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=time_range_minutes)
        time_range = (start, now)
        range_interval = {"gte": start.isoformat(), "lte": now.isoformat()}
        must: list[dict[str, Any]] = [{"range": {TIME_FIELD: range_interval}}]
        should: list[dict[str, Any]] = []
        if query_text and query_text.strip():
            # Use should so we still get time-bounded hits when the question wording doesn't match logs; matching docs rank higher
            should.append({"multi_match": {"query": query_text, "fields": ["message", "error.message", "event.message"], "type": "best_fields"}})
        if service:
            must.append({"term": {"service.name": service}})
        if log_level:
            level_variants = {log_level, log_level.lower(), log_level.upper(), log_level.capitalize()}
            must.append({"terms": {"log.level": list(level_variants)}})
        bool_query: dict[str, Any] = {"must": must}
        if should:
            bool_query["should"] = should
        # Sort by score (matching query) then by time so we get citations even when query text doesn't match
        sort_spec = [{"_score": {"order": "desc"}}, {"@timestamp": {"order": "desc", "missing": "_last"}}]
        body: dict[str, Any] = {
            "query": {"bool": bool_query},
            "size": size,
            "sort": sort_spec,
            "_source": True,
        }
        resp = self.client.search(index=self.log_index_pattern, body=body)
        hits = [
            {"_index": h["_index"], "_id": h["_id"], "_source": h.get("_source", {}), "highlight": h.get("highlight")}
            for h in resp.get("hits", {}).get("hits", [])
        ]
        total = resp.get("hits", {}).get("total", {})
        if isinstance(total, dict):
            total = total.get("value", 0)
        return SearchToolResult(hits=hits, total=total, index_pattern=self.log_index_pattern, query=body, time_range=time_range)

    def search_metrics(self, *, time_range_minutes: int = 15, size: int = 100) -> SearchToolResult:
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=time_range_minutes)
        range_interval = {"gte": start.isoformat(), "lte": now.isoformat()}
        sort_spec = [{"@timestamp": {"order": "desc", "missing": "_last"}}]
        body: dict[str, Any] = {
            "query": {"range": {TIME_FIELD: range_interval}},
            "size": size,
            "sort": sort_spec,
            "_source": True,
        }
        resp = self.client.search(index=self.metrics_index_pattern, body=body)
        hits = [{"_index": h["_index"], "_id": h["_id"], "_source": h.get("_source", {})} for h in resp.get("hits", {}).get("hits", [])]
        total = resp.get("hits", {}).get("total", {})
        if isinstance(total, dict):
            total = total.get("value", 0)
        return SearchToolResult(hits=hits, total=total, index_pattern=self.metrics_index_pattern, query=body, time_range=(start, now))

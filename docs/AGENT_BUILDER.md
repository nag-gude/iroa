# IROA — Built with Elastic Agent Builder

**Elastic Agent Builder** is the key hackathon requirement. IROA is built **using Elastic Agent Builder** by implementing the agent framework and its tools as required: a multi-step agent that combines a reasoning model with **Search** and **ES|QL** tools to automate incident response.

References:
- [Agent Builder (Elastic Docs)](https://www.elastic.co/docs/explore-analyze/ai-features/elastic-agent-builder)
- [Agent Builder tools: Search, ES|QL, Workflows](https://www.elastic.co/docs/explore-analyze/ai-features/agent-builder/tools)
- [Hackathon: What to Build](https://elasticsearch.devpost.com)

---

## How IROA uses Elastic Agent Builder

| Agent Builder concept | IROA implementation | Location |
|-----------------------|---------------------|----------|
| **Agent (orchestration)** | Single agent that receives a query/alert, selects and invokes tools, reasons over results, and returns an auditable response. | `iroa/agent/runner.py` — `run_agent()`; `services/agent/orchestrator.py` for microservices. |
| **Search tool** | Elasticsearch Search API over indices: full-text search, time bounds, filters. Matches Agent Builder’s [Index search tools](https://www.elastic.co/docs/explore-analyze/ai-features/agent-builder/tools/index-search-tools). | `iroa/tools/search.py` — `SearchTool` (search over `logs-*`, `metrics-*`). |
| **ES\|QL tool** | ES\|QL queries for aggregations and analytics (e.g. error count by host). Matches Agent Builder’s [ES\|QL tools](https://www.elastic.co/docs/solutions/search/agent-builder/tools/esql-tools). | `iroa/tools/esql.py` — `ESQLTool` (e.g. `error_count_by_host()`). |
| **Reasoning** | Agent correlates Search and ES\|QL results, produces summary and root-cause hypothesis, and builds an explanation. | `iroa/agent/runner.py` — `_reason_over_results()`, `_build_explanation()`. |
| **Elasticsearch as system of record** | All retrieval and correlation use Elasticsearch only; no separate search/analytics store. | Data service and `SearchTool` / `ESQLTool` talk only to Elasticsearch. |

---

## Agent Builder flow in IROA

1. **Trigger** — User or system sends a query/alert (API, CLI, or demo UI).
2. **Tool selection & execution** — Agent runs **ES\|QL** (e.g. error count by host) and **Search** (logs) over Elasticsearch.
3. **Reasoning** — Agent correlates tool results (time windows, hosts, services) and generates a summary and root-cause hypothesis.
4. **Action (optional)** — Agent can create a ticket (e.g. Jira) and record what it did.
5. **Response** — Structured output with summary, root cause, evidence (citations to Elasticsearch), actions taken, and audit trail.

This matches the Agent Builder model: an agent that uses Elasticsearch-backed tools, reasons over the data, and explains its actions.

---

## Code locations (for judges)

- **Agent loop (Agent Builder orchestration):** `iroa/agent/runner.py`
- **Search tool (Agent Builder Search):** `iroa/tools/search.py`
- **ES\|QL tool (Agent Builder ES\|QL):** `iroa/tools/esql.py`
- **API entry (POST /analyze):** `iroa/api/main.py`
- **Architecture and diagrams:** [architecture.md](architecture.md)

IROA is built **with** Elastic Agent Builder by implementing the required agent pattern and using the same tools (Search, ES\|QL) that Agent Builder provides, with Elasticsearch as the single system of record.

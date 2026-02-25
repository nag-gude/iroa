# IROA Implementation Guide

This document describes how IROA is implemented and how it **uses Elasticsearch and the Elastic Agent Builder pattern**. The agent orchestrates **Elasticsearch Search** and **ES|QL** as tools (see [architecture.md](architecture.md) for diagrams and the 8-step agent loop). Elasticsearch is the only retrieval layer; the code is modular (tools, agent runner, connectors) and functional (API, CLI, UI, Docker, Vercel).

## Project layout

```
IROA/
  iroa/                    # Core library
    __init__.py
    config.py              # Settings (env)
    models.py              # AnalyzeRequest, AnalyzeResponse, Citation, ActionTaken
    cli.py                 # Typer CLI
    agent/
      runner.py            # Core Agent Loop (in-process)
    tools/
      search.py            # SearchTool (Elasticsearch Search)
      esql.py              # ESQLTool (ES|QL)
    connectors/
      base.py              # BaseTicketingConnector
      jira_connector.py    # JiraConnector
    api/
      main.py              # Monolith FastAPI app (POST /analyze, GET /health, GET / demo UI)

  static/                  # Demo UI (single-page HTML/JS served at GET /)
    index.html

  scripts/
    create_test_data.py    # Test data for full workflow (logs + metrics)

  services/                # Microservices
    data/
      config.py
      main.py              # Search + ES|QL API (:8001)
    actions/
      config.py
      main.py              # Create ticket API (:8002)
    agent/
      config.py
      orchestrator.py      # HTTP client to Data + Actions, reasoning
      main.py              # POST /analyze (:8000)

  docs/
    architecture.md       # Diagrams and flows
    setup.md
    implementation.md     # This file
    deployment.md
    SRS.md                 # Software requirements (reference)
```

## Key components

### Core Agent Loop (`iroa.agent.runner.run_agent`)

- **Input:** `AnalyzeRequest` (query, time_range_minutes, optional alert payload, create_ticket flag).
- **Steps:** Run ES|QL (error count by host) → Search logs → correlate → hypothesis → optional ticket via callback → audit → build `AnalyzeResponse`.
- **Used by:** Monolith API and CLI (in-process mode).

### Orchestrator (`services.agent.orchestrator.run_orchestrator`)

- **Input:** Same `AnalyzeRequest` plus `data_service_url` and `actions_service_url`.
- **Steps:** HTTP POST to Data (ES|QL, Search) and optionally Actions (tickets); same correlation and hypothesis logic; build `AnalyzeResponse`.
- **Used by:** Agent service (`services.agent.main`).

### Data service API

- `POST /search/logs` — Body: `query_text`, `service`, `log_level`, `time_range_minutes`, `size`. Returns hits and total.
- `POST /search/metrics` — Body: `time_range_minutes`, `size`.
- `POST /esql/run` — Body: `query` (raw ES|QL string).
- `POST /esql/error-count-by-host` — Body: `time_range_minutes`, `log_level`. Returns columns and values.

**Log level (`log.level`):** Search and ES|QL treat `log_level` as case-insensitive. Values like `info`, `INFO`, `trace`, `debug`, `error` all match regardless of casing (e.g. info 65%, trace 32%, debug 2%, INFO 0.3%). Use `log_level` in request bodies to filter or aggregate by level.

### Actions service API

- `POST /tickets` — Body: `title`, `description`, `severity`, `system` (e.g. `jira`). Returns `action`, `system`, `identifier`, `link`.

## Extending the implementation

### Add a new ticketing system

1. Implement a connector in `iroa/connectors/` extending `BaseTicketingConnector` (e.g. `service_now_connector.py`).
2. In `services/actions/main.py`, add a branch for the new `system` and call the new connector.
3. Configure credentials via env (e.g. `SERVICENOW_*`) and add to `services/actions/config.py`.

### Add a new ES|QL preset

1. In `iroa/tools/esql.py`, add a method (e.g. `latency_p99_by_service`) that builds an ES|QL string and calls `self.run()`.
2. In `services/data/main.py`, add a new endpoint (e.g. `POST /esql/latency-p99`) that calls the new method and returns `ESQLResponse`.
3. In `services/agent/orchestrator.py`, optionally call this endpoint in addition to or instead of error-count-by-host.

### Add an LLM for reasoning

1. In `iroa/config.py`, add `IROA_LLM_API_URL`, `IROA_LLM_API_KEY`, `IROA_LLM_MODEL`.
2. In `iroa/agent/runner.py` (and in `orchestrator.py` for microservices), replace or augment `_reason_over_results` / `_reason_over_http_responses` with a call to an LLM API, passing Search and ES|QL results as context and asking for summary and root cause.
3. Keep the existing logic as fallback when LLM is not configured or fails.

## Testing

- **Unit:** Mock Elasticsearch and HTTP in tests for `run_agent`, `run_orchestrator`, and connector methods.
- **Integration:** Use a real Elasticsearch instance (or testcontainers) and hit Data service endpoints; run Agent with real Data and Actions URLs.
- **E2E:** Start all three services (or monolith), send `POST /analyze`, assert response shape and audit trail.

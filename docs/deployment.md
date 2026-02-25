# IROA Deployment

## Docker Compose (local microservices)

From the **IROA** project root:

```bash
# Set Elasticsearch (and optional Jira) in .env
export ELASTICSEARCH_URL=https://your-deployment.es.cloud:9243
export ELASTICSEARCH_API_KEY=your_api_key

# --build ensures the agent image includes the static UI (COPY static/)
docker-compose up -d --build
```

Then open **http://localhost:8000** in your browser for the demo UI. If the UI does not load, rebuild the agent image: `docker-compose build agent && docker-compose up -d`.

Services:

- **Agent:** http://localhost:8000 — **demo web UI** at root (query, Analyze) and `POST /analyze`, `GET /health`. Depends on data and actions being healthy.
- **Data:** http://localhost:8001
- **Actions:** http://localhost:8002

Compose passes:

- To **data:** `ELASTICSEARCH_URL`, `ELASTICSEARCH_API_KEY`, `IROA_LOG_INDEX_PATTERN`, `IROA_METRICS_INDEX_PATTERN`
- To **actions:** `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_EMAIL`, `JIRA_PROJECT_KEY`
- To **agent:** `DATA_SERVICE_URL=http://data:8001`, `ACTIONS_SERVICE_URL=http://actions:8002`

### Building images

Images are built from the **IROA** directory; Dockerfiles are in **`docker/`**:

- `docker/Dockerfile.data`: copies `iroa/`, `services/data/`, `services/__init__.py`; runs `uvicorn services.data.main:app`.
- `docker/Dockerfile.actions`: copies `iroa/`, `services/actions/`, `services/__init__.py`; runs `uvicorn services.actions.main:app`.
- `docker/Dockerfile.agent`: copies `iroa/`, `services/agent/`, `services/__init__.py`, `static/` (demo UI); runs `uvicorn services.agent.main:app`. Agent serves the UI at `GET /`.

Build context for Compose is the IROA project root so that `iroa/` and `services/` are available.

## Environment variables (reference)

| Variable | Service | Purpose |
|----------|---------|---------|
| `ELASTICSEARCH_URL` | data, monolith | Elasticsearch endpoint |
| `ELASTICSEARCH_API_KEY` | data, monolith | API key for Elasticsearch |
| `IROA_LOG_INDEX_PATTERN` | data | Log index pattern (default `logs-*`) |
| `IROA_METRICS_INDEX_PATTERN` | data | Metrics index pattern (default `metrics-*`) |
| `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_EMAIL` | actions, monolith | Jira create-issue |
| `JIRA_PROJECT_KEY` | actions | Jira project key (default `IROA`) |
| `DATA_SERVICE_URL` | agent | Data service base URL (default `http://localhost:8001`) |
| `ACTIONS_SERVICE_URL` | agent | Actions service base URL (default `http://localhost:8002`) |

In Docker Compose, use service names for agent: `http://data:8001`, `http://actions:8002`.

## Ports

| Port | Service |
|------|---------|
| 8000 | Agent (orchestrator) / Monolith API |
| 8001 | Data (Search + ES|QL) |
| 8002 | Actions (ticketing) |

## Health checks

All services expose `GET /health`. Docker Compose healthchecks use `curl -f http://localhost:<port>/health`. Ensure curl is installed in the image (see Dockerfiles).

## Production considerations

- **TLS:** Put the stack behind a reverse proxy (e.g. Nginx, Traefik) and terminate TLS there.
- **Secrets:** Prefer a secrets manager or mounted secrets over plain env for API keys and Jira tokens.
- **Elasticsearch:** Use a dedicated cluster; ensure index patterns and retention match your observability data.
- **Scaling:** Scale Data and Agent horizontally; Actions can stay single instance unless you add more connectors and need redundancy.
- **Logging:** Send application logs to Elasticsearch or your logging pipeline for observability of IROA itself.

## Deployment options

IROA can run **locally** or on **Vercel**:

- **Local:** Run the monolith with `uvicorn iroa.api.main:app` (see [setup.md](setup.md)), or run all three services with **Docker Compose** (above).
- **[Vercel](deployment-vercel.md)** — Deploy the monolith as a serverless function (demo UI + `/analyze`, `/health`).

To **test** local deployments with curl and the CLI, see [Testing examples](testing-examples.md).

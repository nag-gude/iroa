# IROA Setup

## Prerequisites

- **Python 3.10+**
- **Elasticsearch 8.x** (Elastic Cloud or self-managed) with at least one index containing logs or metrics (e.g. `logs-*`, `metrics-*`).
- Optional: **Jira** (Cloud) for ticketing; credentials for create-issue API.

**Elasticsearch:** IROA uses an Elasticsearch deployment (Elastic Cloud or self-managed). Set `ELASTICSEARCH_URL` (or `ELASTICSEARCH_CLOUD_ID` for Elastic Cloud) and `ELASTICSEARCH_API_KEY` in `.env`. See the table below for where to get the URL and API key.

**Flow:** IROA fetches logs (and metrics) from Elasticsearch and runs the full analysis: Search + ES|QL → correlation → root-cause hypothesis → optional ticket.

## 1. Clone and enter project

If the repo is cloned and you are in the parent folder, enter IROA:

```bash
cd IROA
```

All commands below assume the current directory is the **IROA** project root (the folder containing `iroa/`, `services/`, `docs/`).

## 2. Create virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional, for editable install and CLI entry point:

```bash
pip install -e .
```

## 3. Configure environment

Copy the example env file and edit (place `.env` in the IROA project root):

```bash
cp .env.example .env
```

All services and the CLI read environment variables from this `.env` file in the **project root** (the directory containing `iroa/` and `pyproject.toml`), so the same file is used regardless of which directory you run commands from.

Set in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `ELASTICSEARCH_URL` | Yes* | Elasticsearch endpoint (e.g. `https://...es.us-central1.gcp.cloud.es.io:9243`). *Omit when using `ELASTICSEARCH_CLOUD_ID`. |
| `ELASTICSEARCH_CLOUD_ID` | No | Elastic Cloud only: Cloud ID from deployment (alternative to `ELASTICSEARCH_URL`). |
| `ELASTICSEARCH_API_KEY` | Yes | API key for Elasticsearch |

**Getting your Elasticsearch URL and API key:** For Elastic Cloud, copy the Elasticsearch endpoint from the deployment in the [Cloud console](https://cloud.elastic.co) and create an API key in Kibana (Management → API Keys, or Help → Connection details → API key) with read and ES|QL access on `logs-*` and `metrics-*`. For self-managed clusters, use your cluster URL and an API key.

| `IROA_LOG_INDEX_PATTERN` | No | Default `logs-*` |
| `IROA_METRICS_INDEX_PATTERN` | No | Default `metrics-*` |
| `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_EMAIL` | No | For Actions service / monolith ticketing |
| `DATA_SERVICE_URL` | No (agent) | Default `http://localhost:8001` when running Agent service |
| `ACTIONS_SERVICE_URL` | No (agent) | Default `http://localhost:8002` when running Agent service |

## 4. Run in one of two modes

### A. Monolith (single process)

One process runs API + Elasticsearch tools + optional Jira:

```bash
export PYTHONPATH=.
uvicorn iroa.api.main:app --reload --host 0.0.0.0 --port 8000
```

Then:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Why did checkout fail in the last 15 minutes?", "time_range_minutes": 15}'
```

### B. Microservices (three processes)

Terminal 1 — Data service:

```bash
export PYTHONPATH=.
uvicorn services.data.main:app --host 0.0.0.0 --port 8001
```

Terminal 2 — Actions service:

```bash
export PYTHONPATH=.
uvicorn services.actions.main:app --host 0.0.0.0 --port 8002
```

Terminal 3 — Agent service:

```bash
export PYTHONPATH=.
uvicorn services.agent.main:app --host 0.0.0.0 --port 8000
```

Then call the agent as above (`http://localhost:8000/analyze`).

### C. Demo UI (web)

The monolith serves a **demo frontend** at the root URL. After starting the monolith (step A), open **http://localhost:8000** in your browser. Enter a query, set the time range, and click **Analyze** to see summary, root cause, evidence, and audit trail.

## 5. CLI

From IROA project root:

**In-process (uses Elasticsearch and Jira from `.env`):**

```bash
PYTHONPATH=. python -m iroa.cli analyze -q "Why did checkout fail in the last 15 minutes?" --time-range 15
```

**Microservices (calls Agent service):**

```bash
PYTHONPATH=. python -m iroa.cli analyze -q "Why did checkout fail?" --time-range 15 --agent-url http://localhost:8000
```

With `pip install -e .` you can run:

```bash
iroa analyze -q "Your question here" --time-range 15
```

## 6. Test data (ingest into Elastic Cloud)

To have the agent **always pull data from Elastic Cloud**, ingest test data into your Elastic Cloud deployment:

1. **Set .env to Elastic Cloud:** `ELASTICSEARCH_URL` (e.g. `https://...es.us-central1.gcp.cloud.es.io:9243`) or `ELASTICSEARCH_CLOUD_ID`, and `ELASTICSEARCH_API_KEY` (or user/password). Use the same .env for the agent and for this script.
2. **Run the test data script** (requires a classic, non-Serverless Elastic Cloud deployment):

```bash
# From IROA project root
PYTHONPATH=. python scripts/create_test_data.py --minutes 60
```

This ingests sample logs and metrics into **Elastic Cloud** in indices `logs-iroa-test` and `metrics-iroa-test` (matching `logs-*` and `metrics-*`). The agent will then pull all data from Elastic Cloud when you run the monolith or Data service with the same .env.

Then run the agent with `time_range_minutes` ≤ 60, e.g.:

```bash
curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"query":"Why did checkout fail in the last 15 minutes?","time_range_minutes":15}' | jq .
```

Options:
- `--minutes 60` — Spread test data over the last N minutes (default 60).
- `--recreate` — Delete and recreate the test indices before indexing.

## 7. Health checks

- Monolith or Agent: `GET http://localhost:8000/health`
- Data: `GET http://localhost:8001/health`
- Actions: `GET http://localhost:8002/health`

For full **curl and CLI examples** (local monolith, microservices, Docker Compose), see [Testing examples](testing-examples.md).

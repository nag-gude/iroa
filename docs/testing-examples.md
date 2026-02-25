# Testing IROA: Local deployment

Examples to verify IROA using **local deployment** (monolith, microservices, Docker Compose). Replace placeholders with your actual URLs and API key. For **Vercel** deployment, use your Vercel project URL as the agent URL in the same curl/CLI examples.

**Quick demo:** Start the monolith (`uvicorn iroa.api.main:app --host 0.0.0.0 --port 8000`) or run **Docker Compose** (agent service)—then open the **agent URL** (e.g. **http://localhost:8000**) for the web UI: enter a query, click Analyze, and see summary, root cause, evidence, and audit trail.

**Test data:** Ingest test data into Elastic Cloud so the agent always pulls from Elastic Cloud: set .env to your Elastic Cloud URL (or Cloud ID) and API key, then run `PYTHONPATH=. python scripts/create_test_data.py --minutes 60`. Use `time_range_minutes` ≤ 60 in analyze requests. See [Setup § Test data](setup.md#6-test-data-ingest-into-elastic-cloud).

---

## Prerequisites

- **Elasticsearch** with data in `logs-*` and/or `metrics-*` (ingest data or use `scripts/create_test_data.py`; see [setup.md](setup.md)).
- IROA running locally (see [setup.md](setup.md)) or deployed on [Vercel](deployment-vercel.md); use the agent URL for `/analyze` and `/health`.

---

## 1. Local deployment

### 1.1 Monolith (single process)

Start the monolith:

```bash
cd IROA
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
export PYTHONPATH=.
uvicorn iroa.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Health check:**

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok","service":"IROA"}`

**Analyze (minimal):**

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Why did checkout fail in the last 15 minutes?", "time_range_minutes": 15}'
```

**Analyze (with optional fields):**

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What errors occurred in the payment service in the last hour?",
    "time_range_minutes": 10080,
    "create_ticket": false,
    "alert": {
      "service": "payment-service",
      "severity": "high",
      "time_range_minutes": 60
    }
  }'
```

---

### 1.2 Microservices (three processes)

Start each service in a separate terminal (from IROA root, with `.env` configured):

```bash
# Terminal 1 – Data
export PYTHONPATH=.
uvicorn services.data.main:app --host 0.0.0.0 --port 8001

# Terminal 2 – Actions
export PYTHONPATH=.
uvicorn services.actions.main:app --host 0.0.0.0 --port 8002

# Terminal 3 – Agent (entry point for /analyze)
export PYTHONPATH=.
uvicorn services.agent.main:app --host 0.0.0.0 --port 8000
```

**Health checks:**

```bash
curl -s http://localhost:8000/health   # Agent
curl -s http://localhost:8001/health   # Data
curl -s http://localhost:8002/health   # Actions
```

**Analyze (same as monolith; call the agent on 8000):**

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize errors in the last 30 minutes.", "time_range_minutes": 30}'
```

---

### 1.3 Docker Compose (local)

From IROA root, with `ELASTICSEARCH_URL` and `ELASTICSEARCH_API_KEY` in `.env`:

```bash
docker-compose up -d
```

Open **http://localhost:8000** in your browser for the **demo web UI**. The agent container serves the UI at `/` and the API at `POST /analyze`.

**Health checks:**

```bash
curl -s http://localhost:8000/health   # Agent
curl -s http://localhost:8001/health   # Data
curl -s http://localhost:8002/health   # Actions
```

**Analyze:**

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Why did checkout fail in the last 15 minutes?", "time_range_minutes": 15}'
```

---

## 2. Request and response reference

### Request body (`POST /analyze`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Natural language question or alert description. |
| `time_range_minutes` | integer | No | Lookback window in minutes (default `15`, range 1–10080). |
| `create_ticket` | boolean | No | If `true`, attempt to create a Jira ticket when appropriate (default `false`). |
| `alert` | object | No | Optional structured alert (e.g. `service`, `severity`, `time_range_minutes`). |

### Example response (200)

```json
{
  "summary": "Brief summary of the analysis.",
  "root_cause": "Root-cause hypothesis or main finding.",
  "evidence": [
    { "type": "search", "index": "logs-*", "id": "...", "snippet": "...", "fields": {} }
  ],
  "actions_taken": [],
  "audit_trail": ["Step 1...", "Step 2..."]
}
```

On error you get HTTP 500 with a `detail` message.

---

## 3. CLI (local or remote agent)

**In-process (uses `.env` Elasticsearch and Jira):**

```bash
cd IROA
PYTHONPATH=. python -m iroa analyze -q "Why did checkout fail in the last 15 minutes?" --time-range 15
```

**Against a running agent (local or Vercel):**

```bash
# Local agent (use either invocation)
PYTHONPATH=. python -m iroa analyze -q "Summarize errors in the last 30 minutes." --time-range 30 --agent-url http://localhost:8000
# or: PYTHONPATH=. python -m iroa.cli analyze -q "..." --time-range 30 --agent-url http://localhost:8000

# Vercel (replace with your Vercel project URL)
PYTHONPATH=. python -m iroa analyze -q "Summarize errors in the last 30 minutes." --time-range 30 --agent-url https://your-project.vercel.app
```

**In-process (no agent URL):** Uses your `.env` Elasticsearch and runs the agent locally:

```bash
PYTHONPATH=. python -m iroa analyze -q "Summarize errors in the last 30 minutes." --time-range 30
```

---

## 4. Quick copy-paste summary

| Scenario | Base URL | Health | Analyze |
|----------|----------|--------|---------|
| **Local monolith** | `http://localhost:8000` | `curl -s http://localhost:8000/health` | `curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"query":"Why did checkout fail in the last 15 minutes?","time_range_minutes":15}'` |
| **Local microservices** | `http://localhost:8000` (agent) | `curl -s http://localhost:8000/health` | Same as above (POST to agent) |
| **Local Docker Compose** | `http://localhost:8000` (agent) | Same | Same |
| **Vercel** | `https://<your-project>.vercel.app` | `curl -s https://<your-project>.vercel.app/health` | `curl -s -X POST https://<your-project>.vercel.app/analyze -H "Content-Type: application/json" -d '{"query":"...","time_range_minutes":15}'` |

Replace the `query` and `time_range_minutes` with your own values. Ensure Elasticsearch has data in `logs-*` and/or `metrics-*` for the chosen time range so the agent can return meaningful results.

---

## 5. Troubleshooting: Data service 500 and “No data found”

If you see **“No data found in Elasticsearch”** and the **audit_trail** shows **“Data service ES|QL failed”** or **“Data service Search failed”** with a 500 error, the Data service is failing to talk to Elasticsearch. The agent now includes the **error detail** from the Data service in the audit (e.g. `security_exception`, `index_not_found_exception`, or connection errors). Use that to fix the cause.

### Common causes

| Symptom in audit | Likely cause | What to do |
|------------------|--------------|------------|
| `Connection failed` / `Name or service not known` / `Failed to resolve` | Data service (or monolith) cannot resolve or reach the Elasticsearch host | **DNS:** Ensure the machine running the Data service can resolve the Elasticsearch hostname (e.g. `*.es.europe-west2.gcp.cloud.es.io`). Try `ping <host>` or `curl -v https://<your-es-host>:9243` from that machine. **Docker:** If Data runs in a container, give it external DNS (e.g. add `dns: 8.8.8.8` to the service in `docker-compose.yml` or run with `--network=host` for a quick test). **Firewall/VPN:** Allow outbound HTTPS to the Elastic Cloud host. |
| `Connection failed (check ELASTICSEARCH_URL and network)` | Wrong URL, or Data service cannot reach Elasticsearch | **Local/Docker:** Use the real Elasticsearch URL (e.g. Elastic Cloud endpoint), not `localhost`, in `.env`. **Docker:** the Data container must be able to reach the URL (use the cloud URL). |
| `security_exception` / 401 | Invalid or missing API key | Create an **Elasticsearch API key** in Kibana (not the Cloud management API key). Set `ELASTICSEARCH_API_KEY` in `.env` or in the Data service env. See [setup.md](setup.md). |
| `index_not_found_exception` / no indices | No indices match `logs-*` (or your `IROA_LOG_INDEX_PATTERN`) | Ingest data into Elasticsearch so that `logs-*` (and optionally `metrics-*`) exist, or run `scripts/create_test_data.py`. See [setup.md](setup.md). |
| **404 `Unknown resource`** / **No data was retrieved** | Both Search and ES\|QL returned 404 (e.g. Serverless), or index/time mismatch | Use a **classic** (non-Serverless) deployment. If you see data in Kibana but IROA shows no data: set **IROA_LOG_INDEX_PATTERN** to match your indices (default `logs-*`); increase **time range** in the UI; ensure ES 8.11+. |
| **No data found** but records in Kibana | Index pattern or time range doesn't match | Set **IROA_LOG_INDEX_PATTERN** to match your data (e.g. `logs-*`, `filebeat-*`). Increase **time range (minutes)** in the UI to cover your records. |
| ES\|QL-related error (e.g. parsing, endpoint) | ES\|QL not available or different API on your deployment | Ensure your Elasticsearch version supports ES\|QL and the correct endpoint. See Elastic’s ES\|QL documentation. |

### Actions service 502 (ticket failed)

If the audit shows **"Actions service ticket failed"** with **502 Bad Gateway**, the Actions service (or Jira) is failing. The audit now includes the **detail** from the Actions response (e.g. `Jira API returned 401: Unauthorized`). Check: (1) **Jira env** — `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_EMAIL`, and `JIRA_PROJECT_KEY` must be set in the **actions** service (e.g. in `docker-compose.yml` under `actions.environment`; use the same `.env`). (2) **API token** — use a [Jira API token](https://id.atlassian.com/manage-profile/security/api-tokens), not your password, with the email that owns the token. (3) **Project** — `JIRA_PROJECT_KEY` must be an existing project (e.g. `IROA`). (4) **Network** — the actions container must be able to reach `https://your-domain.atlassian.net`.

### See the exact error from the Data service

1. **Call the Data service directly** (replace with your Data URL and, for Docker, use the host port, e.g. `http://localhost:8001`):

   ```bash
   # Search logs
   curl -s -X POST http://localhost:8001/search/logs \
     -H "Content-Type: application/json" \
     -d '{"query_text": "error", "time_range_minutes": 180}' | jq .

   # ES|QL error count by host
   curl -s -X POST http://localhost:8001/esql/error-count-by-host \
     -H "Content-Type: application/json" \
     -d '{"time_range_minutes": 180}' | jq .
   ```

2. On 500, the response body contains a **`detail`** field with the Elasticsearch (or connection) error. Fix the config (URL, API key, indices) and retry.
3. After the fixes above, the **agent’s audit_trail** will also show this detail when a call fails, so you can debug from the analyze response alone.

### “Could not resolve host” (DNS)

If `curl -v https://<your-elastic-host>:9243` fails with **Could not resolve host**, your machine’s DNS is not resolving the Elastic Cloud hostname. Try:

1. **Test with a public DNS** (e.g. Google DNS) to see if the host is reachable:
   ```bash
   nslookup a9f48c222e074a66bfd4595237978ef5.es.europe-west2.gcp.cloud.es.io 8.8.8.8
   ```
   Replace the hostname with your `ELASTICSEARCH_URL` host. If this returns an IP, the host exists and the problem is your default DNS.

2. **Use Google or Cloudflare DNS on your Mac** (temporarily):
   - **System Settings** → **Network** → your connection (Wi‑Fi/Ethernet) → **Details** → **DNS** → add `8.8.8.8` and/or `1.1.1.1`, then **OK** / **Apply**.
   - Retry `curl -v https://<your-elastic-host>:9243`.

3. **Try another network** (e.g. phone hotspot or different Wi‑Fi) to rule out corporate or ISP DNS blocking.

4. **Confirm the deployment** in [Elastic Cloud](https://cloud.elastic.co): open the deployment and copy the Elasticsearch endpoint again. If the deployment was recreated, the hostname may have changed.

5. **If `nslookup <host> 8.8.8.8` returns NXDOMAIN** — The hostname does not exist in DNS. Your URL may be from an old or deleted deployment. In [Elastic Cloud](https://cloud.elastic.co), open your project → your deployment → copy the **current** Elasticsearch endpoint from the deployment overview and set it as `ELASTICSEARCH_URL` in `.env`. If you no longer have a deployment, create a new one and use its endpoint.

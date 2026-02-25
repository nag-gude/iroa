# IROA — Incident Response + Observability Agent

![IROA Logo](assets/Thumbnail.png)

**Tagline:** Search. Reason. Resolve.

**Subtitle:** Autonomous Observability Agent powered by Elasticsearch Search + ES|QL + Workflows.

IROA is a multi-step AI agent that uses **Elasticsearch as the system of record**: it runs ES|QL queries, performs search over logs and metrics, correlates anomalies, generates root-cause hypotheses, and optionally creates tickets via workflows or native connectors. It is not a chatbot over logs—it orchestrates a **full incident response loop in one call**.


## Why IROA stands out

- **Real-time response** — One query → Search + ES|QL + reasoning + optional ticket. Built for **speed to resolution**, not only after-the-fact reports.
- **Single orchestrated loop** — Alert → ES|QL → Search → correlate → hypothesis → ticket → audit → response. One agent, one API call, full trace.
- **Actionable outcomes** — Creates Jira tickets from the same run; every response includes evidence (citations) and an audit trail.
- **Elasticsearch-native** — Search API + ES|QL drive all retrieval and correlation; no replacement of Elastic as the system of record.
- **Production-ready** — Microservices, Docker Compose, Vercel. API + CLI + **web demo UI** (FastAPI-served) out of the box.

See **[architecture.md](docs/architecture.md)** for diagrams and how we use Elastic Agent Builder and Elasticsearch.


## Quick start

```bash
cd IROA
pip install -r requirements.txt
cp .env.example .env   # set ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY
export PYTHONPATH=.
uvicorn iroa.api.main:app --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser for the **demo UI** (query, time range, Analyze). Or call the API: `curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"query":"Why did checkout fail in the last 15 minutes?","time_range_minutes":15}'`

**Try with test data:** If you have no data in Elasticsearch yet, create sample logs and metrics: `PYTHONPATH=. python scripts/create_test_data.py --minutes 60`. Then run the agent with `time_range_minutes` ≤ 60 (see [Setup](docs/setup.md) § Test data).

## Documentation

| Document | Description |
|----------|-------------|
| [docs/SUBMISSION.md](docs/SUBMISSION.md) | **Hackathon submission:** Inspiration, What it does, How we built it, Challenges, Accomplishments, What we learned, What's next |
| [docs/setup.md](docs/setup.md) | Prerequisites, install, config, run (monolith and microservices) |
| [docs/implementation.md](docs/implementation.md) | Project layout, key components, how to extend |
| [docs/deployment.md](docs/deployment.md) | Docker Compose, env vars, ports, production notes |
| [docs/deployment-vercel.md](docs/deployment-vercel.md) | Deploy monolith on Vercel (serverless) |
| [docs/testing-examples.md](docs/testing-examples.md) | **Testing:** curl/CLI examples for local deployment |
| [docs/architecture.md](docs/architecture.md) | System architecture and agent flow diagrams |

## Project layout

```
IROA/
  iroa/              # Core library (models, tools, connectors, agent, API, CLI)
  services/          # Microservices: data (:8001), actions (:8002), agent (:8000)
  docker/            # Dockerfiles for data, actions, agent
  docs/              # Architecture, setup, implementation, deployment, SRS
```

## Microservices

| Service | Port | Role |
|---------|------|------|
| **Agent** | 8000 | Orchestrator: **demo UI** at `/`, POST /analyze, calls Data + Actions |
| **Data** | 8001 | Search + ES\|QL over Elasticsearch |
| **Actions** | 8002 | Ticketing (Jira) |

With **Docker Compose** or **Vercel**, open the agent URL (e.g. http://localhost:8000 or your Vercel URL) in a browser for the demo UI. See [docs/setup.md](docs/setup.md) and [docs/deployment.md](docs/deployment.md).

## How IROA differs

IROA is built for **real-time incident response**: one request runs the full loop (search, ES|QL, correlation, hypothesis, optional ticket) and returns an actionable result with evidence and audit trail. For **after-the-fact** post-mortem reports and integrity auditing, other tools focus on narrative and audit workflows; IROA focuses on **speed to resolution** and **actionable outcomes** with Elasticsearch at the center.

## License

MIT License.

# IROA — Incident Response + Observability Agent  
## Hackathon Submission

**Tagline:** Search. Reason. Resolve.

**Subtitle:** Autonomous Observability Agent powered by Elasticsearch Search + ES|QL + Workflows.


### 1. Brief description (~400 words)

**IROA (Incident Response + Observability Agent)** is an autonomous agent that runs the full incident loop in one call: it accepts an alert or a natural-language query, searches and analyzes data in Elasticsearch with **Elasticsearch Search** and **ES|QL**, correlates results, produces a root-cause hypothesis with evidence, and optionally creates a Jira ticket. **Tagline:** Search. Reason. Resolve.

**Problem solved (impact).** When an alert fires, engineers often switch between Kibana, terminals, and Jira—manually correlating errors across hosts, guessing at root cause, and creating tickets with incomplete context. IROA addresses this with **one request** (API, CLI, or web UI) that runs ES|QL (e.g. error count by host), Search over logs, correlation, hypothesis, optional ticket creation, and returns a structured response with summary, root_cause, evidence (citations), actions_taken, and an audit trail. **Elasticsearch** is the system of record; we use **Elastic Search** and **ES|QL** for all retrieval and correlation. For actions, we use a **native Jira connector** (create issue with Atlassian Document Format). The agent is exposed via **REST API** (`POST /analyze`), **CLI** (Typer), and a **web demo UI**. Deployment: monolith or microservices (Docker Compose) or monolith on Vercel.

**Technical execution — Agent Builder & Elasticsearch.** We leverage **Elasticsearch** and an **agent-orchestration pattern** consistent with **Elastic Agent Builder**: one agent that uses **Search** and **ES|QL** as tools, reasons over observability data in Elasticsearch, and returns an auditable response. Code: `iroa/tools/search.py`, `iroa/tools/esql.py`, `iroa/agent/runner.py`. **Documentation and diagrams:** We provide an **architecture document** with Mermaid diagrams (system architecture, 8-step agent loop, data flow) and an **implementation guide** (project layout, tools, how we use Agent Builder). See `docs/architecture.md` and `docs/implementation.md`.

**2–3 features we liked or challenges.** (1) **Using Search and ES|QL together** was powerful but required a clear contract: we standardized on `@timestamp`, aligned index patterns (`logs-*`, `metrics-*`), and kept time filters consistent so both return relevant, time-bounded results—getting that alignment right was a challenge we’re proud of. (2) **Jira’s requirement for Atlassian Document Format** for descriptions forced us to add a plain-text-to-ADF helper and normalize in one place; solving that improved our approach to vendor APIs. (3) **Designing a single orchestrated loop**—one `POST /analyze` that runs ES|QL, Search, correlation, hypothesis, optional ticket, and audit—was a feature we liked: judges and users see the full flow and audit trail in one call.


## Inspiration

Engineers and SREs spend too much time **switching between dashboards, logs, and ticketing systems** when an alert fires. They manually correlate errors across hosts, guess at root cause, and then open Jira or PagerDuty to create a ticket—often with incomplete context. We wanted an **agent that runs the full incident loop in one go**: take an alert or a natural-language question, search and analyze data in Elasticsearch, produce a root-cause hypothesis with evidence, and optionally create a ticket—all in a single API call. We chose **Elasticsearch as the system of record** so that Search and ES|QL drive retrieval and correlation, and we keep Elasticsearch as the single system of record (no separate monitoring integration). The inspiration is **speed to resolution** and **actionable outcomes**, not another chatbot over logs.


## What it does

IROA is a **multi-step AI agent** that:

1. **Accepts** a natural-language query or alert description (via API, CLI, or web UI).
2. **Runs ES|QL** over Elasticsearch (e.g. error count by host, time-bounded) and **Search** over log indices (full-text, filters, time range).
3. **Correlates** results (time windows, hosts, services) and **generates** a summary and root-cause hypothesis with confidence.
4. **Optionally creates a Jira ticket** with the summary and link, using the same run.
5. **Returns** a structured response: summary, root_cause, evidence (citations to ES docs), actions_taken, audit_trail, and explanation.

**Interfaces:** REST API (`POST /analyze`), Typer CLI (`iroa analyze "..."`), and a **web demo UI** (FastAPI-served at `GET /`) so you can type a query, set a time range, and click Analyze.

**Integrations:**

- **Jira:** Native connector creates issues with description in Atlassian Document Format (ADF); ticket key and link are returned in the response.

**Deployment:** Monolith (single process) or **microservices** (Agent :8000, Data :8001, Actions :8002) via Docker Compose; or monolith on **Vercel**. Elasticsearch can be Elastic Cloud or self-managed; we support both URL+API key and Cloud ID.


## How we built it

- **Stack:** Python 3.x, FastAPI, Elasticsearch Python client, Typer CLI, Pydantic. Frontend: vanilla HTML/JS for the demo UI.
- **Core library (`iroa/`):**  
  - **Tools:** `SearchTool` (Elasticsearch Search over `logs-*` with query in a should clause, time-bounded, sorted by score and `@timestamp`) and `ESQLTool` (ES|QL over logs/metrics; error-count-by-host preset; case-insensitive log level; single time field `@timestamp`).  
  - **Agent loop:** `run_agent()` in `iroa/agent/runner.py` — ES|QL → Search → correlate → hypothesis → optional ticket callback → audit → `AnalyzeResponse`.  
  - **Connectors:** `JiraConnector` with ADF for descriptions; base class for adding ServiceNow, etc.  
  - **Models:** `AnalyzeRequest`, `AnalyzeResponse`, `AlertPayload`, `Citation`, `ActionTaken`.
- **Services:**  
  - **Data (8001):** Search + ES|QL endpoints; talks only to Elasticsearch.  
  - **Actions (8002):** Create ticket (Jira); no Elasticsearch dependency.  
  - **Agent (8000):** Orchestrator that HTTP-calls Data and Actions, runs correlation and reasoning, serves demo UI and `POST /analyze`.
- **Config:** Single project-root `.env` via `iroa/env_loader.py`; all entrypoints (monolith, data, actions, agent, CLI, `create_test_data.py`) load it regardless of cwd.
- **Deploy:** Dockerfiles in `docker/`, `docker-compose.yml`, Vercel (see deployment-vercel.md).
- **Docs:** SRS, **architecture** (Mermaid diagrams: system, 8-step agent loop, data flow), **implementation** (layout, tools, Agent Builder alignment), setup, deployment (Docker, Vercel), testing examples.


## Challenges we ran into

- **Aligning Search and ES|QL with real data:** We had to standardize on a single time field (`@timestamp`) and avoid `event.created` and other fields that weren’t in our indices; we also made Search time-bounded and put the user query in a should clause so results were relevant and within the requested window.
- **Jira descriptions:** The Jira API required descriptions in **Atlassian Document Format (ADF)**. We added a `_plain_text_to_adf()` helper and send the ticket body as ADF to avoid 400 “Operation value must be an Atlassian Document” errors.
- **Elastic Cloud vs self-managed:** Supporting both URL+API key and Cloud ID, and making the test-data script and all services use the same client factory, required a clear config path and upfront auth validation with clear 401 guidance (e.g. API key roles: create_index, index, write).
- **Meaningful “no data” responses:** When Search or ES|QL returned no hits, we refined the logic so “Unknown resource” only appears when both return 404, and added friendlier messages and index/time-range hints in the UI and docs.


## Accomplishments that we're proud of

- **One orchestrated loop:** A single `POST /analyze` runs ES|QL, Search, correlation, hypothesis, optional ticket, and audit—no separate “narrator” and “auditor” pipelines. Judges and users see the full flow in one call.
- **Actionable outcomes:** Every response includes evidence (citations) and an audit trail; when `create_ticket` is true, the same run creates a Jira issue with ADF description and returns the link.
- **Elasticsearch-native:** Search API and ES|QL are the only retrieval layer; we don’t replace Elastic with another store. Log level handling is case-insensitive in both Search and ES|QL to match real-world data.
- **Production-ready shape:** Monolith for quick demos, microservices for scale; Docker Compose and Vercel; API + CLI + web UI; single `.env` at project root; health checks and clear error handling (e.g. Jira 502/400 with response body in audit).
- **Documentation:** SRS, architecture diagrams, setup, implementation, deployment, data collection, OpenTelemetry, monitoring integration, and testing examples so others can run, extend, and deploy IROA.


## What we learned

- **ES|QL and Search need a shared contract:** Agreeing on one time field and index patterns (`logs-*`, `metrics-*`) and keeping query and time filters consistent across both tools avoided “0 results” and confusing behavior.
- **Vendor APIs are strict:** Jira’s ADF requirement taught us to check API specs early and normalize payloads (e.g. plain text → ADF) in a single place so the rest of the pipeline stays simple.
- **Env and config matter:** Loading `.env` from project root once and reusing it in every service and script improved reliability and made local vs Cloud and monolith vs microservices easier to reason about.
- **User-facing copy matters:** Clear messages when no data is found (with index and time-range hints) and when ticket creation fails (with response detail in the audit) reduced support burden and made the agent feel more trustworthy.


## How this advanced our skills, workflow, and productivity

- **Skills:** We deepened hands-on use of **Elasticsearch Search and ES|QL** together—time-bounded queries, index patterns, and keeping both APIs aligned so the agent gets consistent, citable results. We also got practical experience with **Jira’s API** (ADF, error handling) and with **agent-style orchestration**: one request driving multiple tools (Search, ES|QL, ticketing) and producing a single auditable response.
- **Workflow:** Building IROA reinforced a **single-loop, API-first** workflow: one `POST /analyze` that does the full incident pass instead of ad‑hoc steps in Kibana, terminals, and Jira. That mindset—design for one call, full trace—carries over to how we think about other observability and automation projects.
- **Productivity:** We now have a reusable pattern for **query → search → correlate → ticket**: config-driven (`.env`, index patterns), deployable as monolith or microservices, and documented so we can spin up similar agents or extend this one without re-learning the stack.


## What's next for IROA — Incident Response + Observability Agent

- **LLM-backed reasoning:** Add an optional LLM step (e.g. via Agent Builder or an external API) to augment the current rule-based correlation and hypothesis; keep the existing logic as fallback when the LLM is unavailable or fails.
- **More ES|QL presets:** Latency percentiles by service, throughput over time, and other canned queries exposed as Data service endpoints and used by the orchestrator for richer correlation.
- **Additional ticketing systems:** ServiceNow, PagerDuty (create/acknowledge incident), or Zendesk connectors using the same base pattern as Jira.
- **Training / fine-tuning pipeline:** Per the SRS, support dataset preparation from Elasticsearch (historical incidents, labeled root causes), fine-tune a model for summarization or classification, and plug it into the agent with versioning and evaluation metrics.
- **Runbooks and suggested actions:** Surface runbook links or “suggested next steps” in the response based on root-cause category or service, and optionally trigger Elastic Workflows for automated remediation.
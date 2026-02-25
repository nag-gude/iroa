# Deploy IROA on Vercel

Deploy the **IROA monolith** (single FastAPI app) to **Vercel** as a serverless function. The monolith includes the agent, Search + ES|QL over Elasticsearch, and optional Jira ticketing in one deployment. The demo UI is served at `/` and the API at `/analyze` and `/health`.

## Prerequisites

- [Vercel account](https://vercel.com) and [Vercel CLI](https://vercel.com/docs/cli) (optional).
- **Elasticsearch** (Elastic Cloud or self-managed) with data in `logs-*` and `metrics-*`. See [setup.md](setup.md) for URL and API key.
- Optional: **Jira** credentials for ticketing.

## 1. Deploy from Git

1. Push the IROA repo to GitHub, GitLab, or Bitbucket.
2. In [Vercel](https://vercel.com/new), **Import** the repository.
3. Leave **Root Directory** as `.` and **Framework Preset** as None (or let Vercel auto-detect).
4. Add **Environment Variables** in the Vercel project (Settings → Environment Variables):

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `ELASTICSEARCH_URL` | Yes | Elasticsearch endpoint (e.g. `https://...es.us-central1.gcp.cloud.es.io:9243`) |
   | `ELASTICSEARCH_API_KEY` | Yes | API key for Elasticsearch |
   | `ELASTICSEARCH_CLOUD_ID` | No | Use instead of `ELASTICSEARCH_URL` for Elastic Cloud |
   | `IROA_LOG_INDEX_PATTERN` | No | Default `logs-*` |
   | `IROA_METRICS_INDEX_PATTERN` | No | Default `metrics-*` |
   | `JIRA_BASE_URL` | No | For ticketing (e.g. `https://your-domain.atlassian.net`) |
   | `JIRA_API_TOKEN` | No | Jira API token |
   | `JIRA_EMAIL` | No | Email for Jira API |
   | `JIRA_PROJECT_KEY` | No | Default `IROA` |

5. Click **Deploy**. Vercel will install dependencies from `requirements.txt`, detect the FastAPI app from `index.py` (or `pyproject.toml`), and deploy it as a serverless function.

## 2. Deploy with Vercel CLI

From the IROA project root:

```bash
pip install -r requirements.txt
vercel
```

Follow the prompts (link to an existing project or create a new one). Set environment variables in the [Vercel dashboard](https://vercel.com/dashboard) (Project → Settings → Environment Variables) or with `vercel env add ELASTICSEARCH_URL` etc.

## 3. Local preview

```bash
pip install -r requirements.txt
vercel dev
```

Open the URL shown (e.g. http://localhost:3000). Ensure `.env` is present for local env vars, or set them in the shell.

## 4. URLs after deployment

- **Demo UI:** `https://<your-project>.vercel.app/`
- **Analyze API:** `POST https://<your-project>.vercel.app/analyze`
- **Health:** `GET https://<your-project>.vercel.app/health`

## 5. Notes

- **Monolith only:** This deployment runs the **single-process monolith** (API + Search + ES|QL + optional Jira). The three **microservices** (Agent, Data, Actions) are not deployed separately on Vercel; use [Docker Compose](deployment.md) for that.
- **Cold starts:** Serverless functions may have a cold start on first request; subsequent requests reuse the same instance.
- **Size limit:** The deployment bundle must stay under the [Vercel Functions size limit](https://vercel.com/docs/functions/limitations). Use `.vercelignore` to exclude unneeded files (e.g. `docs/`, `deploy/`, `docker/`).
- **Secrets:** Do not commit `.env`. Use Vercel Environment Variables (or Vercel Secrets) for production.

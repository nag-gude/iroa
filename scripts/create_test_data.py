#!/usr/bin/env python3
"""
Create test data for the full IROA workflow and ingest into Elastic Cloud.

Indexes sample logs and metrics into the Elasticsearch deployment configured in .env.
Use Elastic Cloud in .env (ELASTICSEARCH_URL or ELASTICSEARCH_CLOUD_ID + ELASTICSEARCH_API_KEY)
so that test data is ingested into Elastic Cloud and the agent always pulls data from
Elastic Cloud when you run the monolith or Data service with the same .env.

Usage:
  # .env: ELASTICSEARCH_URL=https://...es.us-central1.gcp.cloud.es.io:9243 (or ELASTICSEARCH_CLOUD_ID)
  #       ELASTICSEARCH_API_KEY=...
  PYTHONPATH=. python scripts/create_test_data.py [--minutes 60] [--recreate]
  # Then run the agent; it will pull from Elastic Cloud:
  curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \\
    -d '{"query":"Why did checkout fail in the last 15 minutes?","time_range_minutes":15}'

Requires: .env with ELASTICSEARCH_URL or ELASTICSEARCH_CLOUD_ID, and ELASTICSEARCH_API_KEY
          (or ELASTICSEARCH_USER + ELASTICSEARCH_PASSWORD).
Indices: logs-iroa-test (matches logs-*), metrics-iroa-test (matches metrics-*).

Note: Elasticsearch Serverless does not support index creation or the bulk API used here.
Use a classic (non-Serverless) Elastic Cloud deployment.
"""
from __future__ import annotations

import argparse
import random
import sys
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Suppress deprecation for transport options in API methods (elasticsearch-py 8.x)
warnings.filterwarnings("ignore", message=".*Passing transport options in the API method is deprecated.*")

# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import AuthenticationException, NotFoundError
from elasticsearch.helpers import bulk

from iroa.env_loader import load_env
from iroa.config import get_settings, Settings

load_env()


LOG_INDEX = "logs-iroa-test"
METRICS_INDEX = "metrics-iroa-test"

SERVICES = ["payment-service", "checkout-service", "api-gateway", "inventory-service"]
HOSTS = ["host-payment-01", "host-checkout-01", "host-api-01", "host-inventory-01"]

ERROR_MESSAGES = [
    "Checkout failed: payment gateway timeout",
    "Payment declined: insufficient funds",
    "Checkout failed: inventory reservation failed for SKU",
    "Payment service error: connection refused to bank adapter",
    "Checkout failed: session expired",
    "Payment error: card declined",
    "Checkout timeout waiting for payment confirmation",
    "Payment service returned 503",
]

INFO_MESSAGES = [
    "Checkout started for user",
    "Payment request sent to gateway",
    "Inventory reserved successfully",
    "Order created successfully",
    "Checkout completed",
    "Payment confirmed",
]


def make_es_client() -> Elasticsearch:
    s = get_settings()
    if getattr(s, "elasticsearch_cloud_id", None):
        if s.elasticsearch_api_key:
            return Elasticsearch(cloud_id=s.elasticsearch_cloud_id, api_key=s.elasticsearch_api_key)
        if s.elasticsearch_user and s.elasticsearch_password:
            return Elasticsearch(cloud_id=s.elasticsearch_cloud_id, basic_auth=(s.elasticsearch_user, s.elasticsearch_password))
        return Elasticsearch(cloud_id=s.elasticsearch_cloud_id)
    if s.elasticsearch_api_key:
        return Elasticsearch(s.elasticsearch_url, api_key=s.elasticsearch_api_key)
    if s.elasticsearch_user and s.elasticsearch_password:
        return Elasticsearch(
            s.elasticsearch_url,
            basic_auth=(s.elasticsearch_user, s.elasticsearch_password),
        )
    return Elasticsearch(s.elasticsearch_url)


def _is_elastic_cloud(settings: Settings) -> bool:
    """True if .env is configured for Elastic Cloud (Cloud ID or cloud URL)."""
    if getattr(settings, "elasticsearch_cloud_id", None):
        return True
    url = (getattr(settings, "elasticsearch_url", None) or "").strip().lower()
    return "cloud.es.io" in url or "elastic-cloud.com" in url


def _auth_failure_help() -> str:
    return (
        "Elastic Cloud returned 401 (authentication failed). Fix credentials in .env:\n"
        "  1. Use an Elasticsearch API key created in Kibana (not the Elastic Cloud org API key).\n"
        "     In Kibana: Management → API Keys, or Help (?) → Connection details → API key.\n"
        "  2. The API key must have create_index, index, and write privileges on logs-* and metrics-*.\n"
        "  3. If both ELASTICSEARCH_API_KEY and ELASTICSEARCH_USER/PASSWORD are set, the script uses the API key.\n"
        "     Ensure the API key is valid and for this deployment; try user/password only if needed.\n"
        "  4. ELASTICSEARCH_URL (or ELASTICSEARCH_CLOUD_ID) must match the deployment where the key was created."
    )


def _verify_connection(client: Elasticsearch) -> None:
    """Verify we can authenticate; exit with clear guidance on 401."""
    try:
        client.info()
    except AuthenticationException:
        print(_auth_failure_help(), file=sys.stderr)
        sys.exit(1)


def generate_logs(minutes: int, num_errors: int = 12, num_info: int = 20) -> list[dict]:
    """Generate log documents with @timestamp in the last `minutes`."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    docs = []

    for i in range(num_errors):
        ts = start + (now - start) * (i / max(num_errors + num_info, 1)) + timedelta(seconds=random.randint(0, 60))
        service = random.choice(SERVICES)
        host = random.choice(HOSTS)
        msg = random.choice(ERROR_MESSAGES)
        docs.append({
            "@timestamp": ts.isoformat(),
            "message": msg,
            "log.level": "error",
            "host.name": host,
            "service.name": service,
            "error.message": msg,
            "event.message": msg,
        })

    for i in range(num_info):
        ts = start + (now - start) * ((num_errors + i) / max(num_errors + num_info, 1)) + timedelta(seconds=random.randint(0, 60))
        service = random.choice(SERVICES)
        host = random.choice(HOSTS)
        msg = random.choice(INFO_MESSAGES)
        docs.append({
            "@timestamp": ts.isoformat(),
            "message": msg,
            "log.level": "info",
            "host.name": host,
            "service.name": service,
            "event.message": msg,
        })

    return docs


def generate_metrics(minutes: int, count: int = 30) -> list[dict]:
    """Generate metric documents with @timestamp in the last `minutes`."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    docs = []
    for i in range(count):
        ts = start + (now - start) * (i / max(count, 1))
        docs.append({
            "@timestamp": ts.isoformat(),
            "metric.name": "system.cpu.usage",
            "service.name": random.choice(SERVICES),
            "host.name": random.choice(HOSTS),
            "metric.value": round(random.uniform(0.1, 0.9), 4),
        })
    return docs


def is_unknown_resource(e: Exception) -> bool:
    """True if Elasticsearch returned 404 'Unknown resource' (e.g. Serverless)."""
    msg = str(e).lower()
    return "unknown resource" in msg or ("404" in msg and "ok" in msg and "false" in msg)


def ensure_indices(client: Elasticsearch, recreate: bool) -> None:
    """Create test indices with minimal mapping so @timestamp range queries work."""
    mapping = {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "message": {"type": "text"},
                "log.level": {"type": "keyword"},
                "host.name": {"type": "keyword"},
                "service.name": {"type": "keyword"},
                "error.message": {"type": "text"},
                "event.message": {"type": "text"},
                "metric.name": {"type": "keyword"},
                "metric.value": {"type": "float"},
            }
        }
    }
    for idx in (LOG_INDEX, METRICS_INDEX):
        if recreate:
            try:
                client.indices.delete(index=idx, ignore_unavailable=True)
                print(f"Deleted index: {idx}")
            except Exception as e:
                if not is_unknown_resource(e):
                    print(f"Delete {idx}: {e}")
        try:
            # Try data stream first (Elastic Cloud / Fleet often use data streams for logs-* and metrics-*)
            created = False
            if hasattr(client.indices, "create_data_stream"):
                try:
                    client.indices.create_data_stream(name=idx)
                    print(f"Created data stream: {idx}")
                    created = True
                except Exception as ds_e:
                    if "resource_already_exists" in str(ds_e).lower() or "already_exists" in str(ds_e).lower():
                        created = True  # already exists
                    # else: fall through to regular index create
            if not created:
                client.indices.create(index=idx, body=mapping, ignore=400)  # 400 = already exists
        except Exception as e:
            if isinstance(e, AuthenticationException):
                raise
            # Some deployments (e.g. Serverless) may not allow create
            if is_unknown_resource(e):
                raise SystemExit(
                    "This Elasticsearch deployment does not support index creation or bulk indexing "
                    "(e.g. Elasticsearch Serverless). create_test_data.py requires a classic "
                    "Elasticsearch deployment where you can create indices and use the bulk API.\n"
                    "Options: (1) Use a non-Serverless Elastic Cloud deployment, or "
                    "(2) Use a classic self-managed Elasticsearch deployment."
                ) from e
            if "resource_already_exists" not in str(e).lower():
                print(f"Create {idx} (optional): {e}")


def run(minutes: int = 60, recreate: bool = False) -> None:
    s = get_settings()
    has_url = s.elasticsearch_url and not s.elasticsearch_url.startswith("https://<")
    has_cloud_id = getattr(s, "elasticsearch_cloud_id", None)
    has_auth = s.elasticsearch_api_key or (s.elasticsearch_user and s.elasticsearch_password)
    if (not has_url and not has_cloud_id) or not has_auth:
        print(
            "Set Elastic Cloud (or Elasticsearch) in .env: ELASTICSEARCH_URL or ELASTICSEARCH_CLOUD_ID, "
            "and ELASTICSEARCH_API_KEY. See .env.example.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = make_es_client()
    _verify_connection(client)

    if _is_elastic_cloud(s):
        print("Ingesting test data into Elastic Cloud. The agent will pull data from Elastic Cloud when using the same .env.\n")
    else:
        print(
            "Ingesting test data into Elasticsearch at %s.\n"
            "To have the agent always pull from Elastic Cloud, set ELASTICSEARCH_URL (or ELASTICSEARCH_CLOUD_ID) "
            "to your Elastic Cloud deployment in .env and re-run this script." % (s.elasticsearch_url or "(config)"),
            file=sys.stderr,
        )

    try:
        ensure_indices(client, recreate)
    except AuthenticationException:
        print(_auth_failure_help(), file=sys.stderr)
        sys.exit(1)


    logs = generate_logs(minutes)
    metrics = generate_metrics(minutes)

    # Use op_type "create" so indexing works with data streams (Elastic Cloud logs-* / metrics-*)
    log_actions = [{"_op_type": "create", "_index": LOG_INDEX, "_source": doc} for doc in logs]
    metric_actions = [{"_op_type": "create", "_index": METRICS_INDEX, "_source": doc} for doc in metrics]

    try:
        success, failed = bulk(client, log_actions, raise_on_error=False, request_timeout=30)
        if failed:
            print(f"Log bulk had failures: {failed[:3]}...", file=sys.stderr)
        print(f"Indexed {success} log documents into {LOG_INDEX}")

        success, failed = bulk(client, metric_actions, raise_on_error=False, request_timeout=30)
        if failed:
            print(f"Metrics bulk had failures: {failed[:3]}...", file=sys.stderr)
        print(f"Indexed {success} metric documents into {METRICS_INDEX}")
    except AuthenticationException:
        print(_auth_failure_help(), file=sys.stderr)
        sys.exit(1)
    except NotFoundError as e:
        if is_unknown_resource(e):
            raise SystemExit(
                "This Elasticsearch deployment does not support the bulk index API "
                "(e.g. Elasticsearch Serverless). create_test_data.py requires a classic "
                "Elasticsearch deployment.\n"
                "Options: (1) Use a non-Serverless Elastic Cloud deployment, or "
                "(2) Use a classic self-managed Elasticsearch deployment."
            ) from e
        raise

    client.close()
    print(f"\nDone. Data covers the last {minutes} minutes.")
    print("Run the agent with time_range_minutes <= %d. Use %d to match the test data window:" % (minutes, minutes))
    print('  curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \\')
    print('    -d \'{"query":"Why did checkout fail?","time_range_minutes":%d}\'' % minutes)
    print("\nIf you get 0 results: (1) Use time_range_minutes: %d to match this data. (2) Restart the server that handles /analyze (monolith or Data+Agent) so it loads the same .env and connects to Elastic Cloud." % minutes)


def main() -> None:
    p = argparse.ArgumentParser(description="Create IROA test data (logs + metrics) in Elasticsearch.")
    p.add_argument("--minutes", type=int, default=60, help="Spread test data over this many minutes (default 60)")
    p.add_argument("--recreate", action="store_true", help="Delete and recreate test indices before indexing")
    args = p.parse_args()
    run(minutes=args.minutes, recreate=args.recreate)


if __name__ == "__main__":
    main()

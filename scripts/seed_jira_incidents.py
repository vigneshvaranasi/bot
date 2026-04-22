"""Seed a Jira project with realistic support incidents for RAG testing.

Creates ~8 issues with multi-turn comment threads (diagnosis → resolution) and
transitions most of them to Done so the connector has a mix of open/closed.

Usage:
    uv run python scripts/seed_jira_incidents.py \\
        --url https://your-workspace.atlassian.net \\
        --email you@example.com \\
        --token <api_token> \\
        --project SUP

Or via env:
    JIRA_URL=... JIRA_EMAIL=... JIRA_API_TOKEN=... JIRA_PROJECT_KEY=SUP \\
        uv run python scripts/seed_jira_incidents.py
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

parser = argparse.ArgumentParser(description="Seed a Jira project with sample incidents")
parser.add_argument("--url", help="Jira base URL, e.g. https://acme.atlassian.net")
parser.add_argument("--email", help="Atlassian account email")
parser.add_argument("--token", help="Atlassian API token")
parser.add_argument("--project", help="Project key, e.g. SUP")
parser.add_argument(
    "--issue-type",
    default=None,
    help="Issue type name (default: 'Incident' if it exists, else 'Task')",
)
parser.add_argument(
    "--resolve-ratio",
    type=float,
    default=0.75,
    help="Fraction of created issues to transition to Done (default: 0.75)",
)
args = parser.parse_args()

JIRA_URL = (args.url or os.getenv("JIRA_URL") or "").rstrip("/")
JIRA_EMAIL = args.email or os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = args.token or os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = args.project or os.getenv("JIRA_PROJECT_KEY")
PREFERRED_TYPE = args.issue_type or os.getenv("JIRA_ISSUE_TYPE")
RESOLVE_RATIO = max(0.0, min(1.0, args.resolve_ratio))

missing = [
    name
    for name, value in [
        ("JIRA_URL", JIRA_URL),
        ("JIRA_EMAIL", JIRA_EMAIL),
        ("JIRA_API_TOKEN", JIRA_API_TOKEN),
        ("JIRA_PROJECT_KEY", JIRA_PROJECT_KEY),
    ]
    if not value
]
if missing:
    print(f"ERROR: missing required config: {', '.join(missing)}", file=sys.stderr)
    print("       supply via --flags or environment variables.", file=sys.stderr)
    sys.exit(1)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

print(f"Jira:     {JIRA_URL}")
print(f"Project:  {JIRA_PROJECT_KEY}")
print(f"As user:  {JIRA_EMAIL}")
print()
INCIDENTS: list[dict[str, Any]] = [
    {
        "summary": "Payment gateway returning HTTP 500 on EU traffic",
        "description": (
            "Users in the EU region are seeing 500 errors on checkout since 10:15 UTC.\n"
            "Affects Visa and Mastercard. Stripe webhooks are retrying.\n"
            "Error rate: ~12% on /checkout/confirm."
        ),
        "priority": "High",
        "labels": ["payments", "eu", "production"],
        "comments": [
            "Rolled back payments-service deploy #4821. Error rate back to baseline within 2 min.",
            "Root cause: new retry logic double-charged when Stripe returned 429. "
            "Patch in PR #1423, will re-deploy after review.",
            "Resolution: deployed fixed version v2.4.3. Monitoring for 24h before closing.",
        ],
        "resolve": True,
    },
    {
        "summary": "Postgres primary running out of connection slots",
        "description": (
            "Application pods starting to fail liveness checks around 03:10 UTC.\n"
            "pg_stat_activity shows 298/300 active connections on primary.\n"
            "Grafana dashboard: db-health-p99."
        ),
        "priority": "Highest",
        "labels": ["database", "postgres", "production"],
        "comments": [
            "Identified runaway analytics job holding 120+ idle-in-transaction connections.",
            "Killed the analytics job (pid 18342). Connections dropped to 40/300.",
            "Added connection lifetime cap of 10m in pgbouncer config to prevent recurrence. "
            "Rolled out to prod cluster.",
        ],
        "resolve": True,
    },
    {
        "summary": "SSO login loops back to sign-in page for Okta users",
        "description": (
            "Users authenticating via Okta are redirected back to the login page after SAML POST.\n"
            "Only affects users in the 'engineering' group. Microsoft and Google SSO still work."
        ),
        "priority": "High",
        "labels": ["auth", "sso", "okta"],
        "comments": [
            "SAML response includes NameID but no role attribute — group mapping skipped.",
            "Okta admin updated the SAML app attribute statements to include 'groups'. "
            "Tested with a sample user, redirect now works.",
            "Added regression check to our auth smoke tests.",
        ],
        "resolve": True,
    },
    {
        "summary": "Transactional emails delayed by 20+ minutes",
        "description": (
            "SendGrid dashboard shows a large backlog building up starting 09:00 UTC.\n"
            "Password reset and invitation emails affected. Marketing emails unaffected "
            "(they use a different subaccount)."
        ),
        "priority": "Medium",
        "labels": ["email", "sendgrid"],
        "comments": [
            "SendGrid returning 429s — we hit the per-subuser rate limit.",
            "Reached out to SendGrid support, got our transactional quota raised from 100/s "
            "to 500/s. Backlog drained in ~15 min.",
            "Long-term: add Redis-backed outbound rate limiter to avoid hitting provider caps.",
        ],
        "resolve": True,
    },
    {
        "summary": "Cache stampede on product catalog after deploy",
        "description": (
            "Post-deploy, product-catalog-service P99 latency jumped from 120ms to 4.2s.\n"
            "Redis hit rate dropped to 11%. Upstream DB load spiking."
        ),
        "priority": "High",
        "labels": ["performance", "cache", "redis"],
        "comments": [
            "New deploy cleared the cache namespace. All requests falling through to DB.",
            "Enabled single-flight coalescing via singleflight.Group for catalog lookups. "
            "Hit rate recovering as cache warms up.",
            "Will add cache pre-warming step to deploy pipeline to avoid this in future.",
        ],
        "resolve": True,
    },
    {
        "summary": "Background job worker OOM killed every ~2 hours",
        "description": (
            "Kubernetes is restarting the report-generator pods with OOMKilled.\n"
            "Memory usage climbs linearly from 300MB to 4GB (pod limit) before restart.\n"
            "Started after merging PR #1502 which added PDF export."
        ),
        "priority": "Medium",
        "labels": ["backend", "memory-leak", "workers"],
        "comments": [
            "Heap dump shows 2.3GB retained by WeasyPrint font cache — never evicted.",
            "Switched to ReportLab for PDF generation (no global font cache). "
            "Memory stable at ~500MB over 24h. Marking resolved.",
        ],
        "resolve": True,
    },
    {
        "summary": "Intermittent 502s from CDN on image assets",
        "description": (
            "Customer reports broken product images ~5% of the time.\n"
            "Cloudflare analytics shows 502 spikes correlated with origin timeouts."
        ),
        "priority": "Medium",
        "labels": ["cdn", "cloudflare", "images"],
        "comments": [
            "Origin timeout is 15s but image-resize-service sometimes takes 30s for large uploads.",
            "Ongoing — added retries at the CDN layer as a stopgap, investigating why "
            "image-resize-service is slow. Will post a proper fix once identified.",
        ],
        "resolve": False,
    },
    {
        "summary": "New user signups failing with 'invalid invitation token'",
        "description": (
            "Users clicking email invitations are shown 'invalid invitation token' error.\n"
            "Started about 30 minutes ago. Existing users unaffected."
        ),
        "priority": "High",
        "labels": ["signup", "invitations"],
        "comments": [
            "Investigating — invitation links work in staging but not prod.",
            "Suspect token signing key rotation. Checking vault.",
        ],
        "resolve": False,
    },
]

def _request(method: str, path: str, **kw) -> requests.Response:
    url = f"{JIRA_URL}{path}"
    resp = requests.request(method, url, auth=AUTH, headers=HEADERS, timeout=30, **kw)
    return resp


def _adf_paragraph(text: str) -> dict:
    """Wrap a plain string in minimal Atlassian Document Format."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


def resolve_issue_type() -> str:
    """Pick a valid issue type for the project: preferred → Incident → Task → first available."""
    resp = _request("GET", f"/rest/api/3/project/{JIRA_PROJECT_KEY}")
    if resp.status_code != 200:
        raise SystemExit(
            f"Cannot read project {JIRA_PROJECT_KEY}: {resp.status_code} {resp.text[:300]}"
        )
    types = [t["name"] for t in resp.json().get("issueTypes", [])]
    if not types:
        raise SystemExit(f"Project {JIRA_PROJECT_KEY} has no issue types configured.")

    for candidate in [PREFERRED_TYPE, "Incident", "Task", "Bug"]:
        if candidate and candidate in types:
            return candidate
    return types[0]


def create_issue(issue_type: str, tmpl: dict) -> str | None:
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": issue_type},
            "summary": tmpl["summary"],
            "description": _adf_paragraph(tmpl["description"]),
            "labels": tmpl.get("labels", []),
        }
    }
    priority = tmpl.get("priority")
    if priority:
        payload["fields"]["priority"] = {"name": priority}

    resp = _request("POST", "/rest/api/3/issue", json=payload)
    if resp.status_code not in (200, 201):
        if priority and resp.status_code == 400 and "priority" in resp.text.lower():
            payload["fields"].pop("priority", None)
            resp = _request("POST", "/rest/api/3/issue", json=payload)

    if resp.status_code not in (200, 201):
        print(f"  ✖ create failed: {resp.status_code} {resp.text[:300]}")
        return None

    return resp.json().get("key")


def add_comment(issue_key: str, body: str) -> bool:
    resp = _request(
        "POST",
        f"/rest/api/3/issue/{issue_key}/comment",
        json={"body": _adf_paragraph(body)},
    )
    if resp.status_code not in (200, 201):
        print(f"    ✖ comment failed: {resp.status_code} {resp.text[:200]}")
        return False
    return True


def transition_to_done(issue_key: str) -> bool:
    """Find a transition that moves the issue into the Done status category."""
    resp = _request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
    if resp.status_code != 200:
        print(f"    ✖ list transitions failed: {resp.status_code} {resp.text[:200]}")
        return False

    candidates = resp.json().get("transitions", [])
    target = None
    for t in candidates:
        to = t.get("to") or {}
        category = (to.get("statusCategory") or {}).get("key")
        if category == "done":
            target = t
            break
    if target is None:
        for t in candidates:
            if t.get("name", "").lower() in {"done", "resolve issue", "close issue", "resolved", "closed"}:
                target = t
                break

    if target is None:
        print(f"    ! no Done transition available; skipped")
        return False

    resp = _request(
        "POST",
        f"/rest/api/3/issue/{issue_key}/transitions",
        json={"transition": {"id": target["id"]}},
    )
    if resp.status_code not in (200, 204):
        print(f"    ✖ transition failed: {resp.status_code} {resp.text[:200]}")
        return False
    return True

def main() -> int:
    issue_type = resolve_issue_type()
    print(f"Using issue type: {issue_type}")
    print(f"Seeding {len(INCIDENTS)} incident(s)...\n")

    created: list[tuple[str, dict]] = []
    for tmpl in INCIDENTS:
        key = create_issue(issue_type, tmpl)
        if not key:
            continue
        print(f"✓ {key}  {tmpl['summary']}")
        for body in tmpl.get("comments", []):
            if add_comment(key, body):
                print(f"    + comment: {body[:70]}{'...' if len(body) > 70 else ''}")
        created.append((key, tmpl))

    to_resolve_n = int(round(len(created) * RESOLVE_RATIO))
    resolvable = [item for item in created if item[1].get("resolve")]
    to_resolve = resolvable[:to_resolve_n] if to_resolve_n else []

    if to_resolve:
        print(f"\nTransitioning {len(to_resolve)} issue(s) to Done...")
        for key, _ in to_resolve:
            if transition_to_done(key):
                print(f"  ✓ {key} → Done")

    print(f"\nDone. Created {len(created)}/{len(INCIDENTS)} issue(s) in {JIRA_PROJECT_KEY}.")
    print("Now hit 'Sync Now' on the Jira integration in the app to pull them into the KB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
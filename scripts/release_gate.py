"""Require the latest exact-main CI run, not an arbitrary successful status."""

import json
import os
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOSITORY = "Flippylolz/fillable"
WORKFLOW_ID = 351418605
WORKFLOW_PATH = ".github/workflows/ci.yml"
REQUIRED_JOBS = {"checks", "upgrade-checks", "ci-required"}


def validate_source(source, context, branch):
    if (
        not isinstance(source, str)
        or not re.fullmatch(r"[0-9a-f]{40}", source)
        or context.get("repository") != REPOSITORY
        or context.get("ref") != "refs/heads/main"
        or context.get("event") != "workflow_dispatch"
        or context.get("sha") != source
        or branch.get("object", {}).get("sha") != source
    ):
        raise ValueError("Release must be the dispatched current main revision")


def validate_ci(source, workflow, run, jobs):
    if (
        workflow.get("id") != WORKFLOW_ID
        or workflow.get("path") != WORKFLOW_PATH
        or workflow.get("state") != "active"
        or run.get("workflow_id") != WORKFLOW_ID
        or run.get("path") != WORKFLOW_PATH
        or run.get("event") != "push"
        or run.get("head_branch") != "main"
        or run.get("head_sha") != source
        or run.get("repository", {}).get("full_name") != REPOSITORY
        or run.get("head_repository", {}).get("full_name") != REPOSITORY
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or type(run.get("id")) is not int
        or run["id"] <= 0
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"] <= 0
    ):
        raise ValueError("Latest exact-source CI run has not succeeded")
    rows = jobs.get("jobs", [])
    if (
        type(jobs.get("total_count")) is not int
        or jobs.get("total_count") != len(REQUIRED_JOBS)
        or len(rows) != len(REQUIRED_JOBS)
        or {row.get("name") for row in rows} != REQUIRED_JOBS
        or any(
            row.get("status") != "completed"
            or row.get("conclusion") != "success"
            or row.get("head_sha") != source
            or type(row.get("run_attempt")) is not int
            or row.get("run_attempt") != run["run_attempt"]
            for row in rows
        )
    ):
        raise ValueError("Every required CI job must succeed for this attempt")


def request(path):
    token = os.environ["GH_TOKEN"]
    if not token:
        raise ValueError("Missing GitHub token")
    query = Request(
        f"https://api.github.com/repos/{REPOSITORY}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(query, timeout=20) as response:
        return json.load(response)


def verify(source):
    context = {
        key: os.environ.get(name)
        for key, name in (
            ("repository", "GITHUB_REPOSITORY"),
            ("ref", "GITHUB_REF"),
            ("event", "GITHUB_EVENT_NAME"),
            ("sha", "GITHUB_SHA"),
        )
    }
    validate_source(source, context, request("git/ref/heads/main"))
    workflow = request("actions/workflows/ci.yml")
    query = urlencode(
        {"head_sha": source, "event": "push", "branch": "main", "per_page": 1}
    )
    # No success filter: a newer failure must not fall back to an older green run.
    runs = request(f"actions/workflows/{WORKFLOW_ID}/runs?{query}")["workflow_runs"]
    if len(runs) != 1 or type(runs[0].get("id")) is not int:
        raise ValueError("Missing latest CI run")
    run = runs[0]
    jobs = request(f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100")
    validate_ci(source, workflow, run, jobs)
    # Re-read after the job lookup, including rerun status/attempt and moving main.
    current = request(f"actions/runs/{run['id']}")
    validate_ci(source, workflow, current, jobs)
    latest = request(f"actions/workflows/{WORKFLOW_ID}/runs?{query}")["workflow_runs"]
    if len(latest) != 1 or latest[0].get("id") != run["id"]:
        raise ValueError("A newer CI run superseded the proof")
    validate_ci(source, workflow, latest[0], jobs)
    validate_source(source, context, request("git/ref/heads/main"))
    return {"source_sha": source, "ci_run_id": run["id"]}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(sys.argv[1]), sort_keys=True))
    except Exception:
        # Never echo HTTP headers, tokens or configuration in workflow logs.
        print("release_gate_failed", file=sys.stderr)
        raise SystemExit(1) from None

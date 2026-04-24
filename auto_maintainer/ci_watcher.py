from __future__ import annotations

import re
import time
from typing import Any

from auto_maintainer.github import run_gh_json, run_gh_text


FAILED_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required"}
PENDING_STATES = {"PENDING", "QUEUED", "IN_PROGRESS", "pending", "queued", "in_progress"}

PATTERNS: list[tuple[str, list[str]]] = [
    ("merge_conflict", [r"merge conflict", r"CONFLICT \(", r"Automatic merge failed"]),
    ("dependency_install_failure", [r"npm ERR!", r"pip install", r"No matching distribution found", r"ResolutionImpossible"]),
    ("security_guard_failure", [r"CodeQL", r"Dependabot", r"npm audit", r"gitleaks", r"secret scanning", r"CVE-"]),
    ("contract_type_drift", [r"generated type drift", r"OpenAPI", r"schema drift", r"TS23\d+", r"Type .* is not assignable"]),
    ("schemathesis_failure", [r"schemathesis", r"Falsifying example", r"Response violates schema", r"5xx status code"]),
    ("frontend_build_failure", [r"next build", r"Failed to compile", r"webpack", r"vite build", r"Module not found"]),
    ("lint_failure", [r"eslint", r"ruff", r"flake8", r"pylint", r"black --check", r"Lint failed"]),
    ("unit_test_failure", [r"FAILED tests/", r"AssertionError", r"pytest", r"jest", r"vitest", r"test failed"]),
    ("flaky_infra", [r"timed out", r"ECONNRESET", r"503 Service Unavailable", r"rate limit exceeded", r"hosted runner"]),
]


def watch_and_classify(repo: str, pr: str, *, timeout_seconds: int = 1800, poll_seconds: int = 20) -> dict[str, Any]:
    wait_result = wait_for_pr_checks(repo, pr, timeout_seconds=timeout_seconds, poll_seconds=poll_seconds)
    checks = collect_check_runs(repo, pr)
    logs = collect_failing_logs(repo, pr)
    classification = classify_failure(checks, logs)
    return {
        "status": wait_result["status"],
        "classification": classification,
        "failed_checks": extract_failed_checks(checks),
        "evidence": logs[:5],
    }


def wait_for_pr_checks(repo: str, pr: str, *, timeout_seconds: int = 1800, poll_seconds: int = 20) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_checks: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        checks = collect_check_runs(repo, pr)
        last_checks = checks
        if checks:
            failed = extract_failed_checks(checks)
            pending = [check for check in checks if check.get("state") in PENDING_STATES or check.get("bucket") == "pending"]
            if failed:
                return {"status": "failed", "checks": checks}
            if not pending:
                return {"status": "passed", "checks": checks}
        time.sleep(poll_seconds)
    return {"status": "timeout", "checks": last_checks}


def collect_check_runs(repo: str, pr: str) -> list[dict[str, Any]]:
    return run_gh_json(
        [
            "pr",
            "checks",
            pr,
            "--repo",
            repo,
            "--json",
            "name,state,conclusion,workflowName,detailsUrl,bucket,startedAt,completedAt",
        ],
        allow_failure=True,
    ) or []


def collect_failing_logs(repo: str, pr: str) -> list[dict[str, str]]:
    pr_data = run_gh_json(["pr", "view", pr, "--repo", repo, "--json", "headRefName,headRefOid,mergeStateStatus"], allow_failure=True) or {}
    if pr_data.get("mergeStateStatus") == "DIRTY":
        return [{"category": "merge_conflict", "excerpt": "PR mergeStateStatus is DIRTY."}]
    runs = run_gh_json(
        ["run", "list", "--repo", repo, "--branch", pr_data.get("headRefName", ""), "--limit", "50", "--json", "databaseId,name,status,conclusion,headSha,workflowName,url"],
        allow_failure=True,
    ) or []
    evidence: list[dict[str, str]] = []
    for run in runs:
        if run.get("headSha") != pr_data.get("headRefOid"):
            continue
        if run.get("conclusion") not in FAILED_CONCLUSIONS:
            continue
        log = run_gh_text(["run", "view", str(run["databaseId"]), "--repo", repo, "--log-failed"], allow_failure=True, timeout=180)
        if not log:
            continue
        category, excerpt = classify_text(log)
        evidence.append({"check_name": run.get("name", ""), "category": category, "excerpt": excerpt})
    return evidence


def classify_failure(checks: list[dict[str, Any]], logs: list[dict[str, str]]) -> str:
    check_text = "\n".join(" ".join(str(check.get(key, "")) for key in ("name", "workflowName", "conclusion")) for check in checks)
    category, _ = classify_text(check_text)
    if category != "unknown":
        return category
    for item in logs:
        if item.get("category") and item["category"] != "unknown":
            return item["category"]
    return "unknown"


def classify_text(text: str) -> tuple[str, str]:
    sample = text[:200_000]
    for category, patterns in PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, sample, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                start = max(0, match.start() - 180)
                end = min(len(sample), match.end() + 180)
                return category, sample[start:end].replace("\r", "")
    return "unknown", sample[:500].replace("\r", "")


def extract_failed_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check for check in checks if check.get("conclusion") in FAILED_CONCLUSIONS]

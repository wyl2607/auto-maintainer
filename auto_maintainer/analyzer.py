from __future__ import annotations

from pathlib import Path
from typing import Any

from auto_maintainer.github import run_gh_json
from auto_maintainer.models import Candidate, CandidateSource, Config, RepoRef, RepoState


BACKLOG_MARKERS = ("TODO:", "FIXME:", "Backlog:", "Follow-up:", "Action:", "- [ ]", "CR-")
FAILING_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required"}


def analyze_repo(config: Config) -> tuple[RepoState, list[Candidate]]:
    state = collect_repo_state(config.repo)
    candidates: list[Candidate] = []
    candidates.extend(candidate_from_pr(pr) for pr in state.open_prs)
    candidates.extend(candidate_from_issue(issue) for issue in state.open_issues)
    candidates.extend(candidate for check in state.latest_checks if (candidate := candidate_from_check(check, config.repo)))
    candidates.extend(candidate_from_alert(alert) for alert in state.security_alerts)
    candidates.extend(collect_documented_backlog(config.repo))
    return state, candidates


def collect_repo_state(repo: RepoRef) -> RepoState:
    return RepoState(
        open_prs=collect_open_prs(repo),
        open_issues=collect_open_issues(repo),
        latest_checks=collect_latest_main_checks(repo),
        security_alerts=collect_security_alerts(repo),
    )


def collect_open_prs(repo: RepoRef) -> list[dict[str, Any]]:
    return run_gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo.slug,
            "--state",
            "open",
            "--json",
            "number,title,url,author,labels,isDraft,reviewDecision,mergeable,updatedAt,headRefName,baseRefName",
        ]
    ) or []


def collect_open_issues(repo: RepoRef) -> list[dict[str, Any]]:
    return run_gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo.slug,
            "--state",
            "open",
            "--json",
            "number,title,url,author,labels,assignees,updatedAt,comments",
        ]
    ) or []


def collect_latest_main_checks(repo: RepoRef) -> list[dict[str, Any]]:
    return run_gh_json(
        [
            "run",
            "list",
            "--repo",
            repo.slug,
            "--branch",
            repo.default_branch,
            "--limit",
            "10",
            "--json",
            "databaseId,name,displayTitle,headBranch,headSha,status,conclusion,event,createdAt,updatedAt,url",
        ],
        allow_failure=True,
    ) or []


def collect_security_alerts(repo: RepoRef) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for endpoint in ("dependabot/alerts", "code-scanning/alerts", "secret-scanning/alerts"):
        result = run_gh_json(["api", f"repos/{repo.slug}/{endpoint}"], allow_failure=True) or []
        if isinstance(result, list):
            alerts.extend(item for item in result if item.get("state", "open") == "open")
    return alerts


def collect_documented_backlog(repo: RepoRef) -> list[Candidate]:
    if repo.local_path is None:
        return []
    candidates: list[Candidate] = []
    for path in backlog_paths(repo.local_path):
        candidates.extend(parse_backlog_file(path, repo.local_path))
    return candidates


def backlog_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    consistency = root / "docs" / "policies" / "project-consistency-rules.md"
    if consistency.exists():
        paths.append(consistency)
    runbooks = root / "docs" / "runbooks"
    if runbooks.exists():
        paths.extend(sorted(runbooks.glob("*.md")))
    return paths


def parse_backlog_file(path: Path, root: Path) -> list[Candidate]:
    relative = path.relative_to(root)
    candidates: list[Candidate] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or not _looks_like_backlog_item(stripped):
            continue
        title = stripped.removeprefix("- [ ]").strip(" -")
        candidates.append(
            Candidate(
                id=f"backlog:{relative.as_posix()}:{line_no}",
                title=title[:160],
                source=CandidateSource.DOCUMENTED_BACKLOG,
                value=3,
                risk=1,
                complexity=2,
                confidence=2,
                reason=f"Documented backlog item in {relative}:{line_no}",
                files=[relative.as_posix()],
            )
        )
    return candidates


def _looks_like_backlog_item(line: str) -> bool:
    if any(line.startswith(marker) or marker in line for marker in BACKLOG_MARKERS[:-1]):
        return True
    return bool(line.startswith("-") and "CR-" in line)


def candidate_from_pr(pr: dict[str, Any]) -> Candidate:
    return Candidate(
        id=f"pr:{pr['number']}",
        title=pr["title"],
        source=CandidateSource.OPEN_PR,
        value=3,
        risk=2 if pr.get("isDraft") else 1,
        complexity=2,
        confidence=2,
        reason=f"Open PR #{pr['number']} may need review, CI fix, or merge decision.",
    )


def candidate_from_issue(issue: dict[str, Any]) -> Candidate:
    return Candidate(
        id=f"issue:{issue['number']}",
        title=issue["title"],
        source=CandidateSource.OPEN_ISSUE,
        value=3,
        risk=1,
        complexity=2,
        confidence=2,
        reason=f"Open issue #{issue['number']} may be actionable.",
    )


def candidate_from_check(check: dict[str, Any], repo: RepoRef) -> Candidate | None:
    conclusion = check.get("conclusion")
    status = check.get("status")
    if conclusion not in FAILING_CONCLUSIONS and status == "completed":
        return None
    if conclusion is None and status == "completed":
        return None
    value = 4 if conclusion in FAILING_CONCLUSIONS else 3
    title = check.get("displayTitle") or check.get("name") or "GitHub Actions check"
    return Candidate(
        id=f"check:{check.get('databaseId') or check.get('url')}",
        title=f"Fix or inspect check: {title}",
        source=CandidateSource.FAILING_CI,
        value=value,
        risk=2,
        complexity=2,
        confidence=3,
        reason=f"Latest {repo.default_branch} workflow status is {status}/{conclusion}.",
    )


def candidate_from_alert(alert: dict[str, Any]) -> Candidate:
    package = alert.get("dependency", {}).get("package", {}).get("name")
    title = package or alert.get("rule", {}).get("description") or alert.get("secret_type") or "Security alert"
    return Candidate(
        id=f"security:{alert.get('number') or alert.get('html_url') or title}",
        title=str(title),
        source=CandidateSource.SECURITY,
        value=5,
        risk=3,
        complexity=2,
        confidence=3,
        reason="GitHub security alert is open; human confirmation is required before applying changes.",
        touches=["secrets"] if alert.get("secret_type") else [],
    )

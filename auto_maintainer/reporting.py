from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_maintainer.models import Candidate, Config, ExecutionPlan, RepoState
from auto_maintainer.scoring import select_candidate


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_run_report(config: Config, state: RepoState, candidates: list[Candidate], run_id: str | None = None) -> Path:
    run_id = run_id or new_run_id()
    report_dir = config.report_dir / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    selected = select_candidate(candidates)

    (report_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "repo": config.repo.slug,
                "selected": _jsonable(selected),
                "state": _jsonable(state),
                "candidates": [_jsonable(candidate) for candidate in candidates],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    path = report_dir / "final-report.md"
    path.write_text(render_markdown(config, state, candidates, run_id), encoding="utf-8")
    return path


def write_plan_report(config: Config, state: RepoState, candidates: list[Candidate], plan: ExecutionPlan, run_id: str | None = None) -> Path:
    run_id = run_id or new_run_id()
    report_dir = config.report_dir / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "plan.json").write_text(json.dumps(_jsonable(plan), indent=2, ensure_ascii=False), encoding="utf-8")
    (report_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "repo": config.repo.slug,
                "plan": _jsonable(plan),
                "state": _jsonable(state),
                "candidates": [_jsonable(candidate) for candidate in candidates],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    path = report_dir / "execution-plan.md"
    path.write_text(render_plan_markdown(config, state, candidates, plan, run_id), encoding="utf-8")
    return path


def latest_report(report_dir: Path) -> Path | None:
    if not report_dir.exists():
        return None
    run_dirs = sorted((path for path in report_dir.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    for run_dir in run_dirs:
        for name in ("execution-plan.md", "ci-report.md", "final-report.md"):
            path = run_dir / name
            if path.exists():
                return path
    return None


def write_ci_report(config: Config, pr: str, result: dict[str, Any], run_id: str | None = None) -> Path:
    run_id = run_id or new_run_id()
    report_dir = config.report_dir / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "ci-result.json").write_text(json.dumps(_jsonable(result), indent=2, ensure_ascii=False), encoding="utf-8")
    path = report_dir / "ci-report.md"
    path.write_text(render_ci_markdown(config, pr, result, run_id), encoding="utf-8")
    return path


def write_handoff(plan: ExecutionPlan, local_path: Path) -> Path:
    auto_dir = local_path / ".auto-maintainer"
    auto_dir.mkdir(parents=True, exist_ok=True)
    path = auto_dir / "handoff.md"
    path.write_text(render_handoff_markdown(plan, local_path), encoding="utf-8")
    return path


def render_markdown(config: Config, state: RepoState, candidates: list[Candidate], run_id: str) -> str:
    selected = select_candidate(candidates)
    lines = [
        "# Auto Maintainer Report",
        "",
        "## Summary",
        f"- Run ID: `{run_id}`",
        f"- Repo: `{config.repo.slug}`",
        f"- Open PRs: {len(state.open_prs)}",
        f"- Open issues: {len(state.open_issues)}",
        f"- Security alerts visible to gh: {len(state.security_alerts)}",
        f"- Candidates: {len(candidates)}",
        f"- Selected: `{selected.id}` {selected.title}" if selected else "- Selected: none",
        "",
        "## Candidates",
        "| ID | Source | Value | Risk | Complexity | Confidence | Score | Decision |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for candidate in candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    candidate.id,
                    candidate.source.value,
                    str(candidate.value),
                    str(candidate.risk),
                    str(candidate.complexity),
                    str(candidate.confidence),
                    str(candidate.score),
                    candidate.decision.value if candidate.decision else "unset",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Decision Notes"])
    if not candidates:
        lines.append("- No actionable candidates were found. Current recommendation: stop.")
    for candidate in candidates:
        lines.append(f"- `{candidate.id}`: {candidate.decision_reason or candidate.reason}")
    lines.extend(["", "## Next Action"])
    if selected:
        lines.append("- A candidate passed gates. Assign it to a worker before implementation.")
    else:
        lines.append("- No candidate passed automatic execution gates. Stop or request human confirmation.")
    lines.append("")
    return "\n".join(lines)


def render_plan_markdown(config: Config, state: RepoState, candidates: list[Candidate], plan: ExecutionPlan, run_id: str) -> str:
    lines = [
        "# Auto Maintainer Execution Plan",
        "",
        "## Summary",
        f"- Run ID: `{run_id}`",
        f"- Repo: `{config.repo.slug}`",
        f"- Dry run: `{plan.dry_run}`",
        f"- Candidate: `{plan.candidate.id}` {plan.candidate.title}",
        f"- Decision: `{plan.candidate.decision.value if plan.candidate.decision else 'unset'}`",
        f"- Planned branch: `{plan.branch_name}`",
        "",
        "## Assignment",
        f"- Controller: `{plan.controller}`",
        f"- Worker: `{plan.worker}`",
        f"- Reviewer: `{plan.reviewer}`",
        "",
        "## Verification",
    ]
    lines.extend(f"- `{command}`" for command in plan.verification_commands)
    lines.extend(["", "## Stop Conditions"])
    lines.extend(f"- {condition}" for condition in plan.stop_conditions)
    lines.extend(["", "## Next Steps"])
    lines.extend(f"- {step}" for step in plan.next_steps)
    lines.extend(["", "## Candidate Table", "| ID | Source | Score | Decision |", "| --- | --- | ---: | --- |"])
    for candidate in candidates:
        lines.append(
            f"| {candidate.id} | {candidate.source.value} | {candidate.score} | {candidate.decision.value if candidate.decision else 'unset'} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_ci_markdown(config: Config, pr: str, result: dict[str, Any], run_id: str) -> str:
    lines = [
        "# Auto Maintainer CI Report",
        "",
        "## Summary",
        f"- Run ID: `{run_id}`",
        f"- Repo: `{config.repo.slug}`",
        f"- PR: `{pr}`",
        f"- Status: `{result.get('status')}`",
        f"- Classification: `{result.get('classification')}`",
        "",
        "## Failed Checks",
    ]
    failed = result.get("failed_checks") or []
    if not failed:
        lines.append("- None")
    for check in failed:
        lines.append(f"- `{check.get('workflowName') or check.get('name')}` {check.get('detailsUrl') or ''}".rstrip())
    lines.extend(["", "## Evidence"])
    evidence = result.get("evidence") or []
    if not evidence:
        lines.append("- None")
    for item in evidence[:5]:
        excerpt = str(item.get("excerpt", "")).strip().replace("\n", " ")[:500]
        lines.append(f"- `{item.get('category', 'unknown')}`: {excerpt}")
    lines.append("")
    return "\n".join(lines)


def render_handoff_markdown(plan: ExecutionPlan, local_path: Path) -> str:
    lines = [
        "# Auto Maintainer Worker Handoff",
        "",
        "## Assignment",
        f"- Controller: `{plan.controller}`",
        f"- Worker: `{plan.worker}`",
        f"- Reviewer: `{plan.reviewer}`",
        f"- Local path: `{local_path}`",
        f"- Branch: `{plan.branch_name}`",
        "",
        "## Candidate",
        f"- ID: `{plan.candidate.id}`",
        f"- Title: {plan.candidate.title}",
        f"- Reason: {plan.candidate.reason}",
        "",
        "## Requirements",
        "- Make the smallest scoped change that addresses only this candidate.",
        "- Do not change auth, permissions, deployment, secrets, schema, public API deletion, major upgrades, or large refactors without confirmation.",
        "- Stop if the worktree has unrelated changes or the fix expands beyond this task.",
        "",
        "## Verification",
    ]
    lines.extend(f"- `{command}`" for command in plan.verification_commands)
    lines.append("")
    return "\n".join(lines)


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_maintainer.models import Candidate, Config, RepoState
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

from __future__ import annotations

import re

from auto_maintainer.models import Candidate, Config, ExecutionPlan


def build_execution_plan(candidate: Candidate, config: Config, *, dry_run: bool = True) -> ExecutionPlan:
    return ExecutionPlan(
        candidate=candidate,
        controller=config.agents.controller,
        worker=config.agents.worker,
        reviewer=config.agents.reviewer,
        dry_run=dry_run,
        branch_name=f"auto/{slugify(candidate.id)}",
        verification_commands=suggest_verification_commands(candidate),
        stop_conditions=default_stop_conditions(config),
        next_steps=next_steps(dry_run),
    )


def suggest_verification_commands(candidate: Candidate) -> list[str]:
    files = "\n".join(candidate.files).lower()
    title = candidate.title.lower()
    if "frontend" in files or "i18n" in title:
        return ["npm run lint", "npm run build"]
    if "openapi" in title or "contract" in title or "types" in title:
        return ["npm run gen:types", "contracts CI must pass"]
    if "docs/" in files or candidate.source.value == "documented_backlog":
        return ["git diff --check"]
    return ["python -m pytest -q"]


def default_stop_conditions(config: Config) -> list[str]:
    return [
        "No candidate passes automatic execution gates.",
        f"The same PR fails CI {config.execution.max_ci_fix_attempts} times.",
        "A fix touches auth, permissions, deployment, secrets, schema, public API deletion, major upgrades, or large refactors.",
        "The worker detects unrelated local changes or merge conflicts.",
        "The required change expands beyond the selected candidate scope.",
    ]


def next_steps(dry_run: bool) -> list[str]:
    if dry_run:
        return [
            "Review this execution plan.",
            "Assign the selected candidate to the configured worker.",
            "Run implementation in a separate branch only after confirmation.",
        ]
    return [
        "Create the planned branch.",
        "Implement the smallest scoped change.",
        "Run verification commands.",
        "Open a PR and watch CI.",
    ]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.").lower()
    return slug[:80] or "task"

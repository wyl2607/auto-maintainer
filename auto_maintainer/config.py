from __future__ import annotations

import json
from pathlib import Path

from auto_maintainer.models import AgentConfig, Config, ExecutionLimits, Gates, RepoRef


def load_config(path: Path | None, *, repo_slug: str | None = None, local_path: Path | None = None) -> Config:
    data = _load_json(path) if path else {}
    repo_data = data.get("repo", {})

    owner, name = _split_repo(repo_slug or repo_data.get("slug") or _repo_from_parts(repo_data))
    repo_path = local_path or _optional_path(repo_data.get("local_path"))

    gates_data = data.get("gates", {})
    execution_data = data.get("execution", {})
    agents_data = data.get("agents", {})
    reporting_data = data.get("reporting", {})
    merge_data = data.get("merge", {})

    return Config(
        repo=RepoRef(
            owner=owner,
            name=name,
            local_path=repo_path,
            default_branch=repo_data.get("default_branch", "main"),
        ),
        gates=Gates(**{k: v for k, v in gates_data.items() if hasattr(Gates, k)}),
        execution=ExecutionLimits(**{k: v for k, v in execution_data.items() if hasattr(ExecutionLimits, k)}),
        agents=AgentConfig(**{k: v for k, v in agents_data.items() if hasattr(AgentConfig, k)}),
        report_dir=Path(reporting_data.get("output_dir", "state/runs")),
        merge_mode=merge_data.get("mode", "ask_before_merge"),
        require_confirmation_touches=tuple(
            data.get(
                "requires_confirmation_touches",
                Config(repo=RepoRef(owner, name)).require_confirmation_touches,
            )
        ),
    )


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _repo_from_parts(data: dict) -> str:
    owner = data.get("owner")
    name = data.get("name")
    if owner and name:
        return f"{owner}/{name}"
    raise ValueError("Repo must be provided as --repo OWNER/NAME or config repo.slug")


def _split_repo(slug: str) -> tuple[str, str]:
    if "/" not in slug:
        raise ValueError("Repo must use OWNER/NAME format")
    owner, name = slug.split("/", 1)
    return owner, name


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def default_config_json(repo_slug: str, local_path: Path | None = None) -> str:
    data = {
        "repo": {
            "slug": repo_slug,
            "local_path": str(local_path) if local_path else "../target-repo",
            "default_branch": "main",
        },
        "gates": {
            "value_min": 3,
            "risk_max": 2,
            "complexity_max": 2,
            "confidence_min": 2,
        },
        "execution": {
            "max_tasks_per_run": 1,
            "max_ci_fix_attempts": 3,
            "max_total_runtime_minutes": 90,
            "require_clean_worktree": True,
        },
        "agents": {
            "controller": "macbook-air",
            "worker": "opencode",
            "reviewer": "coco",
        },
        "merge": {
            "mode": "ask_before_merge",
        },
        "reporting": {
            "output_dir": "state/runs",
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

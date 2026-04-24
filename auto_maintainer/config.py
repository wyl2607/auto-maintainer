from __future__ import annotations

import json
from pathlib import Path

from auto_maintainer.models import Config, ExecutionLimits, Gates, RepoRef


def load_config(path: Path | None, *, repo_slug: str | None = None, local_path: Path | None = None) -> Config:
    data = _load_json(path) if path else {}
    repo_data = data.get("repo", {})

    owner, name = _split_repo(repo_slug or repo_data.get("slug") or _repo_from_parts(repo_data))
    repo_path = local_path or _optional_path(repo_data.get("local_path"))

    gates_data = data.get("gates", {})
    execution_data = data.get("execution", {})
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

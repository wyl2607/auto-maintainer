from __future__ import annotations

import json
import subprocess
from typing import Any


class GitHubCliError(RuntimeError):
    pass


def run_gh_json(args: list[str], *, allow_failure: bool = False, timeout: int = 120) -> Any:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    if result.returncode != 0:
        if allow_failure:
            return None
        message = stderr.strip() or stdout.strip() or "gh command failed"
        raise GitHubCliError(message)
    if not stdout.strip():
        return None
    return json.loads(stdout)


def run_gh_text(args: list[str], *, allow_failure: bool = False, timeout: int = 120) -> str | None:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    if result.returncode != 0:
        if allow_failure:
            return None
        message = stderr.strip() or stdout.strip() or "gh command failed"
        raise GitHubCliError(message)
    return stdout


def create_draft_pr(repo: str, base: str, head: str, title: str, body: str) -> dict[str, Any]:
    url = run_gh_text(
        [
            "pr",
            "create",
            "--repo",
            repo,
            "--base",
            base,
            "--head",
            head,
            "--title",
            title,
            "--body",
            body,
            "--draft",
        ]
    )
    pr_url = (url or "").strip().splitlines()[-1]
    return {"url": pr_url, "base": base, "head": head, "title": title, "draft": True}

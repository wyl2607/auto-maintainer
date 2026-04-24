from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from auto_maintainer.git_ops import GitError, sync_status
from auto_maintainer.github import run_gh_json, run_gh_text


def run_doctor(repo: str | None = None, local_path: Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(check_python())
    checks.append(check_executable("git"))
    checks.append(check_executable("gh"))
    checks.append(check_import())
    checks.append(check_gh_auth())
    if repo:
        checks.append(check_repo_access(repo))
    if local_path:
        checks.append(check_local_repo(local_path))
    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def check_python() -> dict[str, Any]:
    ok = sys.version_info >= (3, 11)
    return {"name": "python", "ok": ok, "detail": sys.version.split()[0]}


def check_executable(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    return {"name": name, "ok": path is not None, "detail": path or "not found"}


def check_import() -> dict[str, Any]:
    spec = importlib.util.find_spec("auto_maintainer")
    return {"name": "auto_maintainer import", "ok": spec is not None, "detail": "importable" if spec else "not importable"}


def check_gh_auth() -> dict[str, Any]:
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, check=False)
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    return {"name": "gh auth", "ok": result.returncode == 0, "detail": (stdout or stderr).strip().splitlines()[0] if (stdout or stderr).strip() else "no output"}


def check_repo_access(repo: str) -> dict[str, Any]:
    data = run_gh_json(["repo", "view", repo, "--json", "nameWithOwner,url"], allow_failure=True)
    return {"name": "repo access", "ok": data is not None, "detail": data.get("url") if data else f"cannot access {repo}"}


def check_local_repo(path: Path) -> dict[str, Any]:
    if not (path / ".git").exists():
        return {"name": "local repo", "ok": False, "detail": f"{path} is not a git repository"}
    try:
        status = sync_status(path)
    except GitError as exc:
        return {"name": "local repo", "ok": False, "detail": str(exc)}
    return {"name": "local repo", "ok": not status["dirty"], "detail": status}


def get_last_ci_status(repo: str, branch: str = "main") -> dict[str, Any]:
    runs = run_gh_json(["run", "list", "--repo", repo, "--branch", branch, "--limit", "1", "--json", "databaseId,name,status,conclusion,url"], allow_failure=True) or []
    return runs[0] if runs else {"status": "unknown", "conclusion": "unknown"}

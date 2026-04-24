from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def ensure_clean_worktree(path: Path) -> None:
    status = run_git(["status", "--short"], path)
    if status.strip():
        raise GitError("Target worktree is not clean; refusing to create an execution branch.")


def create_branch(path: Path, branch_name: str) -> None:
    run_git(["switch", "-c", branch_name], path)


def current_branch(path: Path) -> str:
    return run_git(["branch", "--show-current"], path).strip()


def push_branch(path: Path, remote: str, branch_name: str) -> None:
    run_git(["push", "-u", remote, branch_name], path)


def run_git(args: list[str], path: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=path,
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    if result.returncode != 0:
        raise GitError(stderr.strip() or stdout.strip() or "git command failed")
    return stdout

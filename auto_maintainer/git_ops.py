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


def sync_status(path: Path, remote: str = "origin", branch: str = "main") -> dict[str, str | bool | int]:
    run_git(["fetch", remote], path)
    current = current_branch(path)
    local = run_git(["rev-parse", "HEAD"], path).strip()
    remote_ref = f"{remote}/{branch}"
    remote_sha = run_git(["rev-parse", remote_ref], path).strip()
    counts = run_git(["rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"], path).strip().split()
    ahead, behind = int(counts[0]), int(counts[1])
    dirty = bool(run_git(["status", "--short"], path).strip())
    return {
        "current_branch": current,
        "local_sha": local,
        "remote_sha": remote_sha,
        "ahead": ahead,
        "behind": behind,
        "dirty": dirty,
        "up_to_date": ahead == 0 and behind == 0 and not dirty,
    }


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

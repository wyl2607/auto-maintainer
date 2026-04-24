#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${AUTO_MAINTAINER_TARGET_DIR:-$HOME/Developer/auto-maintainer}"

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "Repository not found at $TARGET_DIR. Run scripts/macbook-bootstrap.sh first." >&2
  exit 1
fi

cd "$TARGET_DIR"

if [[ -n "$(git status --short)" ]]; then
  echo "Worktree is dirty; refusing to overwrite local changes." >&2
  git status --short >&2
  exit 1
fi

git fetch origin
git switch main
git pull --ff-only origin main

if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m pip install -e ".[dev]"
  .venv/bin/python -m pytest -q
else
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev]"
  python -m pytest -q
fi

echo "Synced auto-maintainer at $TARGET_DIR"

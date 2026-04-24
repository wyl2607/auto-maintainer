#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${AUTO_MAINTAINER_REPO_URL:-https://github.com/wyl2607/auto-maintainer.git}"
DEV_ROOT="${AUTO_MAINTAINER_DEV_ROOT:-$HOME/Developer}"
TARGET_DIR="${AUTO_MAINTAINER_TARGET_DIR:-$DEV_ROOT/auto-maintainer}"

mkdir -p "$DEV_ROOT"

if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "Updating $TARGET_DIR"
  git -C "$TARGET_DIR" fetch origin
  git -C "$TARGET_DIR" switch main
  git -C "$TARGET_DIR" pull --ff-only origin main
else
  echo "Cloning $REPO_URL to $TARGET_DIR"
  git clone "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q

echo "auto-maintainer is ready at $TARGET_DIR"
echo "Activate with: source $TARGET_DIR/.venv/bin/activate"

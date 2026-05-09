# controller workstation Sync

Use the controller workstation as the controller workspace for `auto-maintainer`. The GitHub repository is the source of truth; every update from Windows/OpenCode must be committed and pushed to `main`, then pulled on the controller workstation.

## First Setup

```bash
mkdir -p ~/Developer
curl -fsSL https://raw.githubusercontent.com/wyl2607/auto-maintainer/main/scripts/controller-bootstrap.sh | bash
```

Or clone manually:

```bash
cd ~/Developer
git clone https://github.com/wyl2607/auto-maintainer.git
cd auto-maintainer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Pull Updates

```bash
cd ~/Developer/auto-maintainer
./scripts/controller-sync.sh
```

The sync script refuses to continue if the controller workstation worktree has local uncommitted changes.

## Normal Update Flow

1. Develop and test on Windows/OpenCode.
2. Commit and push to `wyl2607/auto-maintainer`.
3. Confirm GitHub Actions are green.
4. On the controller workstation, run `./scripts/controller-sync.sh`.
5. Use the controller workstation copy as the controller for repo analysis and run reports.

## Controller Commands

```bash
source ~/Developer/auto-maintainer/.venv/bin/activate
auto-maintainer analyze --repo wyl2607/esg-research-toolkit --local-path ~/Developer/esg-research-toolkit --json
auto-maintainer run --repo wyl2607/esg-research-toolkit --local-path ~/Developer/esg-research-toolkit --json
auto-maintainer report --latest
```

## Safety

- Do not edit generated run reports into git; `state/runs/` is ignored.
- Do not force-pull over local changes; commit or discard them explicitly first.
- Treat GitHub `main` as the sync source of truth.

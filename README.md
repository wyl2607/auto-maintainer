# auto-maintainer

A cautious GitHub maintenance loop controller for small repositories.

`auto-maintainer` helps decide whether a repo should be changed at all before any code is written. It follows this workflow:

```text
Analyze -> Score -> Gate -> Assign -> Execute -> Verify -> PR -> CI Watch -> Fix Loop -> Merge Gate -> Report -> Reassess
```

The current version implements the controller foundation: repo analysis, candidate scoring, safety gates, report generation, and CI failure classification. It does not mutate repositories or merge PRs yet.

## Goals

- Avoid "change for change's sake" automation.
- Prefer high-value, low-risk maintenance tasks.
- Stop when risk or ambiguity is too high.
- Produce useful reports for humans and agents.
- Watch GitHub CI and classify failures into actionable buckets.

## Install

```bash
python -m pip install -e ".[dev]"
```

Requires Python 3.11+ and the GitHub CLI:

```bash
gh auth login
```

## MacBook Air Sync

Use the MacBook Air as a controller workspace by bootstrapping from GitHub:

```bash
mkdir -p ~/Developer
curl -fsSL https://raw.githubusercontent.com/wyl2607/auto-maintainer/main/scripts/macbook-bootstrap.sh | bash
```

After each Windows/OpenCode update is committed and pushed, sync on the MacBook Air:

```bash
cd ~/Developer/auto-maintainer
./scripts/macbook-sync.sh
```

Details are in `docs/macbook-air-sync.md`.

Check a machine after setup:

```bash
auto-maintainer doctor --repo wyl2607/auto-maintainer --local-path .
```

Check whether a checkout is synced with GitHub:

```bash
auto-maintainer sync-status --repo wyl2607/auto-maintainer --local-path .
```

## Analyze A Repo

```bash
auto-maintainer analyze --repo wyl2607/esg-research-toolkit --local-path ../esg-research-toolkit --json
```

The command gathers:

- open PRs
- open issues
- recent default-branch workflow runs
- visible security alerts, when the token has permission
- documented backlog items from `docs/policies/project-consistency-rules.md` and `docs/runbooks/*.md`

It writes a report under `state/runs/<run-id>/final-report.md`.

## Watch CI

```bash
auto-maintainer watch-ci --repo wyl2607/esg-research-toolkit --pr 123 --json
```

## Plan A Dry Run

```bash
auto-maintainer run --repo wyl2607/esg-research-toolkit --local-path ../esg-research-toolkit --json
```

`run` currently creates an execution plan only. It selects the top candidate that passes gates, assigns controller/worker/reviewer roles, suggests a branch name, lists verification commands, and records stop conditions. It does not create branches, edit code, push, open PRs, or merge.

To create only the planned branch and write a worker handoff file:

```bash
auto-maintainer run --repo wyl2607/esg-research-toolkit --local-path ../esg-research-toolkit --execute-plan --json
```

`--execute-plan` still does not edit files, commit, push, open PRs, or merge. It requires a clean target worktree by default and writes `.auto-maintainer/handoff.md` in the target repo.

The handoff file is now written to the controller run directory as `state/runs/<run-id>/handoff.md`, so it does not dirty the target repository.

Create a draft PR from the current target branch:

```bash
auto-maintainer run --repo wyl2607/esg-research-toolkit --local-path ../esg-research-toolkit --create-draft-pr --json
```

`--create-draft-pr` pushes the current target branch and opens a draft PR with the execution plan in the body. It refuses to create a PR from the default branch and still never merges.

If an open PR already exists for the branch, the tool reuses that PR instead of failing or creating a duplicate.

Reuse a previously saved plan:

```bash
auto-maintainer run --repo wyl2607/esg-research-toolkit --local-path ../esg-research-toolkit --run-id 20260424T200731Z --create-draft-pr --json
```

## Reports

Show the latest generated report:

```bash
auto-maintainer report --latest
```

Bundle the latest run artifacts:

```bash
auto-maintainer report --bundle
```

Write a CI classification report:

```bash
auto-maintainer watch-ci --repo wyl2607/esg-research-toolkit --pr 123 --write-report --json
```

Track bounded CI attempts for a run:

```bash
auto-maintainer watch-ci --repo wyl2607/esg-research-toolkit --pr 123 --write-report --run-id 20260424T200731Z --json
```

When `--run-id` is provided, the CI report and `state.json` are written to the same run directory.

## Merge Gate

Check whether a PR is ready to merge without merging it:

```bash
auto-maintainer merge-gate --repo wyl2607/esg-research-toolkit --pr 123 --json
```

The gate blocks on draft PRs, closed PRs, merge conflicts, failed checks, pending checks, and blocking review decisions.

Failure categories:

- `dependency_install_failure`
- `lint_failure`
- `unit_test_failure`
- `contract_type_drift`
- `schemathesis_failure`
- `frontend_build_failure`
- `security_guard_failure`
- `flaky_infra`
- `merge_conflict`
- `unknown`

## Safety Gates

Candidates are scored with:

```text
score = value - risk - complexity + confidence
```

Automatic execution eligibility defaults:

- `value >= 3`
- `risk <= 2`
- `complexity <= 2`
- `confidence >= 2`

Human confirmation is required for tasks touching:

- auth
- permissions
- deployment
- secrets
- database schema
- public API deletion
- major dependency upgrades
- large refactors

## Example Config

Use JSON for the first version:

```json
{
  "repo": {
    "slug": "wyl2607/esg-research-toolkit",
    "local_path": "../esg-research-toolkit",
    "default_branch": "main"
  },
  "gates": {
    "value_min": 3,
    "risk_max": 2,
    "complexity_max": 2,
    "confidence_min": 2
  },
  "execution": {
    "max_tasks_per_run": 1,
    "max_ci_fix_attempts": 3,
    "max_total_runtime_minutes": 90,
    "require_clean_worktree": true
  },
  "agents": {
    "controller": "macbook-air",
    "worker": "opencode",
    "reviewer": "coco"
  },
  "merge": {
    "mode": "ask_before_merge"
  },
  "reporting": {
    "output_dir": "state/runs"
  }
}
```

## Current Limitations

- Read-only analysis, dry-run planning, safe branch handoff, draft PR creation, artifact bundling, and CI classification only.
- No automatic code edits or merge in v0.1.
- Security alert visibility depends on GitHub token scopes and repo settings.
- Backlog parsing is intentionally simple and line-based.
- CI classification uses heuristics; unknown failures are expected.

## Roadmap

- Add `run --dry-run` execution planning.
- Add worker assignment metadata.
- Add bounded fix-loop state tracking.
- Add PR creation with generated reports.
- Add optional merge gate after explicit human authorization.

## License

MIT

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

- Read-only analysis, dry-run planning, and CI classification only.
- No automatic branch creation, code edits, PR creation, or merge in v0.1.
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

from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_maintainer.analyzer import analyze_repo
from auto_maintainer.ci_watcher import evaluate_merge_gate, watch_and_classify
from auto_maintainer.config import default_config_json, load_config
from auto_maintainer.doctor import get_last_ci_status, run_doctor
from auto_maintainer.git_ops import GitError, create_branch, current_branch, ensure_clean_worktree, push_branch, sync_status
from auto_maintainer.github import create_draft_pr
from auto_maintainer.planner import build_execution_plan
from auto_maintainer.reporting import (
    build_pr_body,
    bundle_reports,
    latest_report,
    load_plan,
    write_ci_report,
    write_handoff,
    write_merge_gate_report,
    write_plan_report,
    write_worker_prompt,
    write_pr_report,
    write_run_report,
)
from auto_maintainer.scoring import apply_gates, select_candidate
from auto_maintainer.state import record_ci_attempt


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "analyze":
        return analyze_command(args)
    if args.command == "watch-ci":
        return watch_ci_command(args)
    if args.command == "run":
        return run_command(args)
    if args.command == "report":
        return report_command(args)
    if args.command == "merge-gate":
        return merge_gate_command(args)
    if args.command == "doctor":
        return doctor_command(args)
    if args.command == "sync-status":
        return sync_status_command(args)
    if args.command == "handoff":
        return handoff_command(args)
    if args.command == "init-config":
        return init_config_command(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-maintainer")
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Analyze, score, gate, and report candidates.")
    analyze.add_argument("--repo", required=True, help="GitHub repo in OWNER/NAME format.")
    analyze.add_argument("--local-path", type=Path, help="Optional local checkout for docs backlog scanning.")
    analyze.add_argument("--config", type=Path, help="Optional JSON config file.")
    analyze.add_argument("--json", action="store_true", help="Print machine-readable summary.")

    run = subparsers.add_parser("run", help="Create a gated execution plan. Defaults to dry-run.")
    run.add_argument("--repo", required=True, help="GitHub repo in OWNER/NAME format.")
    run.add_argument("--local-path", type=Path, help="Optional local checkout for docs backlog scanning.")
    run.add_argument("--config", type=Path, help="Optional JSON config file.")
    run.add_argument("--dry-run", action="store_true", default=True, help="Plan only; do not mutate repos. Enabled by default.")
    run.add_argument("--execute-plan", action="store_true", help="Create the planned branch and write a worker handoff file.")
    run.add_argument("--create-draft-pr", action="store_true", help="Push current target branch and create a draft PR.")
    run.add_argument("--base", default=None, help="Base branch for draft PR creation. Defaults to config default branch.")
    run.add_argument("--remote", default="origin", help="Git remote to push when creating a draft PR.")
    run.add_argument("--run-id", help="Run ID whose saved plan should be reused.")
    run.add_argument("--json", action="store_true", help="Print machine-readable plan summary.")

    watch = subparsers.add_parser("watch-ci", help="Watch a PR and classify failures.")
    watch.add_argument("--repo", required=True, help="GitHub repo in OWNER/NAME format.")
    watch.add_argument("--pr", required=True, help="PR number or URL.")
    watch.add_argument("--timeout", type=int, default=1800)
    watch.add_argument("--poll", type=int, default=20)
    watch.add_argument("--config", type=Path, help="Optional JSON config file for report output settings.")
    watch.add_argument("--write-report", action="store_true", help="Write a CI classification report.")
    watch.add_argument("--run-id", help="Run ID to update with CI attempt state.")
    watch.add_argument("--json", action="store_true")

    report = subparsers.add_parser("report", help="Show the latest generated report.")
    report.add_argument("--config", type=Path, help="Optional JSON config file.")
    report.add_argument("--repo", help="GitHub repo in OWNER/NAME format, used only with config overrides.")
    report.add_argument("--latest", action="store_true", help="Print the latest report path and contents.")
    report.add_argument("--bundle", action="store_true", help="Create bundle.zip for the latest run or --run-id.")
    report.add_argument("--run-id", help="Specific run ID for bundle creation.")
    report.add_argument("--json", action="store_true")

    merge_gate = subparsers.add_parser("merge-gate", help="Check whether a PR satisfies read-only merge gates.")
    merge_gate.add_argument("--repo", required=True, help="GitHub repo in OWNER/NAME format.")
    merge_gate.add_argument("--pr", required=True, help="PR number or URL.")
    merge_gate.add_argument("--config", type=Path, help="Optional JSON config file for report output settings.")
    merge_gate.add_argument("--run-id", help="Run ID to write merge-gate report into.")
    merge_gate.add_argument("--write-report", action="store_true", help="Write merge-gate report artifacts.")
    merge_gate.add_argument("--json", action="store_true")

    doctor = subparsers.add_parser("doctor", help="Check local environment readiness.")
    doctor.add_argument("--repo", help="Optional GitHub repo in OWNER/NAME format to check access.")
    doctor.add_argument("--local-path", type=Path, help="Optional local checkout to inspect.")
    doctor.add_argument("--json", action="store_true")

    sync = subparsers.add_parser("sync-status", help="Check whether a local checkout is synced with origin/main.")
    sync.add_argument("--repo", help="Optional GitHub repo in OWNER/NAME format for latest CI lookup.")
    sync.add_argument("--local-path", type=Path, default=Path("."), help="Local checkout path.")
    sync.add_argument("--remote", default="origin")
    sync.add_argument("--branch", default="main")
    sync.add_argument("--json", action="store_true")

    handoff = subparsers.add_parser("handoff", help="Render a saved handoff or worker prompt.")
    handoff.add_argument("--config", type=Path, help="Optional JSON config file.")
    handoff.add_argument("--repo", help="GitHub repo in OWNER/NAME format, used only with config overrides.")
    handoff.add_argument("--local-path", type=Path, help="Local checkout path for prompt context.")
    handoff.add_argument("--run-id", help="Run ID whose plan should be rendered. Defaults to latest plan.")
    handoff.add_argument("--format", choices=["handoff", "prompt"], default="prompt")
    handoff.add_argument("--write", action="store_true", help="Write the rendered handoff/prompt into the run directory.")
    handoff.add_argument("--json", action="store_true")

    init = subparsers.add_parser("init-config", help="Write a starter auto-maintainer config JSON file.")
    init.add_argument("--repo", required=True, help="GitHub repo in OWNER/NAME format.")
    init.add_argument("--local-path", type=Path, help="Target repo local path to include in the config.")
    init.add_argument("--output", type=Path, default=Path("auto-maintainer.config.json"))
    init.add_argument("--force", action="store_true", help="Overwrite existing config file.")
    init.add_argument("--json", action="store_true")
    return parser


def analyze_command(args: argparse.Namespace) -> int:
    config = load_config(args.config, repo_slug=args.repo, local_path=args.local_path)
    state, candidates = analyze_repo(config)
    candidates = apply_gates(candidates, config)
    report_path = write_run_report(config, state, candidates)
    selected = select_candidate(candidates)
    if args.json:
        print(
            json.dumps(
                {
                    "repo": config.repo.slug,
                    "report": str(report_path),
                    "candidate_count": len(candidates),
                    "selected": selected.id if selected else None,
                    "outcome": "candidate_selected" if selected else "stopped_no_candidate",
                },
                indent=2,
            )
        )
    else:
        print(f"Report: {report_path}")
        if selected:
            print(f"Selected: {selected.id} - {selected.title}")
        else:
            print("No candidate passed automatic execution gates.")
    return 0


def watch_ci_command(args: argparse.Namespace) -> int:
    result = watch_and_classify(args.repo, args.pr, timeout_seconds=args.timeout, poll_seconds=args.poll)
    report_path = None
    if args.write_report:
        config = load_config(args.config, repo_slug=args.repo)
        report_path = write_ci_report(config, args.pr, result, run_id=args.run_id)
        if args.run_id:
            state = record_ci_attempt(config.report_dir, args.run_id, result, config.execution.max_ci_fix_attempts)
            result["run_state"] = state
    if args.json:
        output = dict(result)
        if report_path:
            output["report"] = str(report_path)
        print(json.dumps(output, indent=2))
    else:
        print(f"Status: {result['status']}")
        print(f"Classification: {result['classification']}")
        if report_path:
            print(f"Report: {report_path}")
        for check in result["failed_checks"]:
            print(f"Failed: {check.get('workflowName') or check.get('name')} {check.get('detailsUrl') or ''}")
    return 0 if result["status"] == "passed" else 1


def run_command(args: argparse.Namespace) -> int:
    config = load_config(args.config, repo_slug=args.repo, local_path=args.local_path)
    state, candidates = analyze_repo(config)
    candidates = apply_gates(candidates, config)
    saved_plan = load_plan(config.report_dir, args.run_id) if args.run_id else None
    selected = select_candidate(candidates)
    if selected is None and saved_plan is None:
        report_path = write_run_report(config, state, candidates)
        if args.json:
            print(
                json.dumps(
                    {
                        "repo": config.repo.slug,
                        "outcome": "stopped_no_candidate",
                        "report": str(report_path),
                        "candidate_count": len(candidates),
                    },
                    indent=2,
                )
            )
        else:
            print(f"No candidate passed gates. Report: {report_path}")
        return 0

    execute_plan = bool(args.execute_plan)
    plan = saved_plan or build_execution_plan(selected, config, dry_run=not execute_plan)
    plan_path = (
        config.report_dir / args.run_id / "execution-plan.md"
        if saved_plan is not None and args.run_id
        else write_plan_report(config, state, candidates, plan, run_id=args.run_id)
    )
    handoff_path = None
    pr = None
    if execute_plan:
        if config.repo.local_path is None:
            raise SystemExit("--execute-plan requires --local-path or config repo.local_path")
        try:
            if config.execution.require_clean_worktree:
                ensure_clean_worktree(config.repo.local_path)
            create_branch(config.repo.local_path, plan.branch_name)
            handoff_path = write_handoff(config, plan, config.repo.local_path, run_id=args.run_id)
        except GitError as exc:
            raise SystemExit(str(exc)) from exc
    if args.create_draft_pr:
        if config.repo.local_path is None:
            raise SystemExit("--create-draft-pr requires --local-path or config repo.local_path")
        try:
            if config.execution.require_clean_worktree:
                ensure_clean_worktree(config.repo.local_path)
            branch = current_branch(config.repo.local_path)
            if branch == config.repo.default_branch:
                raise SystemExit("Refusing to create a PR from the default branch.")
            push_branch(config.repo.local_path, args.remote, branch)
            title = f"Auto-maintainer: {plan.candidate.title[:80]}"
            pr = create_draft_pr(config.repo.slug, args.base or config.repo.default_branch, branch, title, build_pr_body(plan))
            write_pr_report(config, pr, plan, run_id=args.run_id)
        except GitError as exc:
            raise SystemExit(str(exc)) from exc
    if args.json:
        print(
            json.dumps(
                {
                    "repo": config.repo.slug,
                    "outcome": "draft_pr_created" if pr else "branch_created" if execute_plan else "planned",
                    "plan": str(plan_path),
                    "handoff": str(handoff_path) if handoff_path else None,
                    "pr": pr,
                    "selected": plan.candidate.id,
                    "worker": plan.worker,
                    "reviewer": plan.reviewer,
                    "dry_run": plan.dry_run,
                },
                indent=2,
            )
        )
    else:
        print(f"Plan: {plan_path}")
        print(f"Selected: {selected.id} - {selected.title}")
        print(f"Worker: {plan.worker}; Reviewer: {plan.reviewer}")
        if handoff_path:
            print(f"Handoff: {handoff_path}")
        if pr:
            print(f"Draft PR: {pr.get('url')}")
    return 0


def merge_gate_command(args: argparse.Namespace) -> int:
    result = evaluate_merge_gate(args.repo, args.pr)
    report_path = None
    if args.write_report:
        config = load_config(args.config, repo_slug=args.repo)
        report_path = write_merge_gate_report(config, args.pr, result, run_id=args.run_id)
    if args.json:
        if report_path:
            result = dict(result)
            result["report"] = str(report_path)
        print(json.dumps(result, indent=2))
    else:
        print(f"Ready: {result['ready']}")
        if report_path:
            print(f"Report: {report_path}")
        for blocker in result["blockers"]:
            print(f"Blocker: {blocker}")
    return 0 if result["ready"] else 1


def report_command(args: argparse.Namespace) -> int:
    repo_slug = args.repo or "local/report-only"
    config = load_config(args.config, repo_slug=repo_slug)
    if args.bundle:
        bundle = bundle_reports(config.report_dir, args.run_id)
        if bundle is None:
            if args.json:
                print(json.dumps({"bundle": None, "outcome": "not_found"}, indent=2))
            else:
                print("No run found to bundle.")
            return 1
        if args.json:
            print(json.dumps({"bundle": str(bundle), "outcome": "created"}, indent=2))
        else:
            print(bundle)
        return 0
    path = latest_report(config.report_dir)
    if path is None:
        if args.json:
            print(json.dumps({"report": None, "outcome": "not_found"}, indent=2))
        else:
            print("No reports found.")
        return 1
    if args.json:
        print(json.dumps({"report": str(path), "outcome": "found"}, indent=2))
    else:
        print(path)
        if args.latest:
            print(path.read_text(encoding="utf-8"))
    return 0


def doctor_command(args: argparse.Namespace) -> int:
    result = run_doctor(repo=args.repo, local_path=args.local_path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"OK: {result['ok']}")
        for check in result["checks"]:
            print(f"{'PASS' if check['ok'] else 'FAIL'} {check['name']}: {check['detail']}")
    return 0 if result["ok"] else 1


def sync_status_command(args: argparse.Namespace) -> int:
    try:
        status = sync_status(args.local_path, remote=args.remote, branch=args.branch)
    except GitError as exc:
        raise SystemExit(str(exc)) from exc
    result = {"sync": status}
    if args.repo:
        result["last_ci"] = get_last_ci_status(args.repo, args.branch)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Branch: {status['current_branch']}")
        print(f"Ahead: {status['ahead']}; Behind: {status['behind']}; Dirty: {status['dirty']}")
        print(f"Up to date: {status['up_to_date']}")
        if args.repo:
            ci = result["last_ci"]
            print(f"Last CI: {ci.get('status')}/{ci.get('conclusion')} {ci.get('url', '')}".rstrip())
    return 0 if status["up_to_date"] else 1


def handoff_command(args: argparse.Namespace) -> int:
    repo_slug = args.repo or "local/handoff"
    config = load_config(args.config, repo_slug=repo_slug, local_path=args.local_path)
    plan = load_plan(config.report_dir, args.run_id)
    if plan is None:
        raise SystemExit("No saved plan found. Run `auto-maintainer run ... --json` first.")
    local_path = config.repo.local_path or args.local_path or Path(".")
    if args.write:
        path = write_worker_prompt(config, plan, local_path, args.run_id) if args.format == "prompt" else write_handoff(config, plan, local_path, args.run_id)
        if args.json:
            print(json.dumps({"path": str(path), "format": args.format}, indent=2))
        else:
            print(path)
        return 0
    if args.format == "prompt":
        from auto_maintainer.reporting import render_worker_prompt

        output = render_worker_prompt(plan, local_path)
    else:
        from auto_maintainer.reporting import render_handoff_markdown

        output = render_handoff_markdown(plan, local_path)
    if args.json:
        print(json.dumps({"format": args.format, "content": output}, indent=2))
    else:
        print(output)
    return 0


def init_config_command(args: argparse.Namespace) -> int:
    if args.output.exists() and not args.force:
        raise SystemExit(f"Config already exists: {args.output}. Use --force to overwrite.")
    args.output.write_text(default_config_json(args.repo, args.local_path), encoding="utf-8")
    if args.json:
        print(json.dumps({"config": str(args.output), "outcome": "created"}, indent=2))
    else:
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

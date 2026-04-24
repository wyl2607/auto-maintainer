from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_maintainer.analyzer import analyze_repo
from auto_maintainer.ci_watcher import watch_and_classify
from auto_maintainer.config import load_config
from auto_maintainer.reporting import write_run_report
from auto_maintainer.scoring import apply_gates, select_candidate


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "analyze":
        return analyze_command(args)
    if args.command == "watch-ci":
        return watch_ci_command(args)
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

    watch = subparsers.add_parser("watch-ci", help="Watch a PR and classify failures.")
    watch.add_argument("--repo", required=True, help="GitHub repo in OWNER/NAME format.")
    watch.add_argument("--pr", required=True, help="PR number or URL.")
    watch.add_argument("--timeout", type=int, default=1800)
    watch.add_argument("--poll", type=int, default=20)
    watch.add_argument("--json", action="store_true")
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
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Status: {result['status']}")
        print(f"Classification: {result['classification']}")
        for check in result["failed_checks"]:
            print(f"Failed: {check.get('workflowName') or check.get('name')} {check.get('detailsUrl') or ''}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

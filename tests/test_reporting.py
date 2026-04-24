from pathlib import Path

from auto_maintainer.models import Candidate, CandidateSource, Config, ExecutionPlan, RepoRef
from auto_maintainer.reporting import latest_report, render_handoff_markdown, write_ci_report


def make_plan() -> ExecutionPlan:
    candidate = Candidate(
        id="task:1",
        title="Small task",
        source=CandidateSource.TODO,
        value=3,
        risk=1,
        complexity=1,
        confidence=2,
        reason="test reason",
    )
    return ExecutionPlan(
        candidate=candidate,
        controller="macbook-air",
        worker="opencode",
        reviewer="coco",
        dry_run=False,
        branch_name="auto/task-1",
        verification_commands=["python -m pytest -q"],
        stop_conditions=["stop here"],
        next_steps=["continue"],
    )


def test_render_handoff_markdown_includes_assignment(tmp_path: Path):
    markdown = render_handoff_markdown(make_plan(), tmp_path)

    assert "Worker: `opencode`" in markdown
    assert "Branch: `auto/task-1`" in markdown
    assert "python -m pytest -q" in markdown


def test_write_ci_report_and_find_latest(tmp_path: Path):
    config = Config(repo=RepoRef("owner", "repo"), report_dir=tmp_path)
    path = write_ci_report(config, "12", {"status": "failed", "classification": "lint_failure", "failed_checks": [], "evidence": []}, "run1")

    assert path.exists()
    assert latest_report(tmp_path) == path

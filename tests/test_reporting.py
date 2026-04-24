from pathlib import Path

from auto_maintainer.models import Candidate, CandidateSource, Config, ExecutionPlan, RepoRef, RepoState
from auto_maintainer.reporting import build_pr_body, bundle_reports, latest_report, load_plan, render_handoff_markdown, write_ci_report, write_handoff, write_plan_report


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


def test_bundle_reports_creates_zip(tmp_path: Path):
    config = Config(repo=RepoRef("owner", "repo"), report_dir=tmp_path)
    write_ci_report(config, "12", {"status": "passed", "classification": "unknown"}, "run1")

    bundle = bundle_reports(tmp_path, "run1")

    assert bundle is not None
    assert bundle.exists()
    assert bundle.name == "bundle.zip"


def test_build_pr_body_includes_stop_conditions():
    body = build_pr_body(make_plan())

    assert "## Stop Conditions" in body
    assert "Draft PR" in body


def test_write_handoff_uses_report_directory(tmp_path: Path):
    config = Config(repo=RepoRef("owner", "repo"), report_dir=tmp_path / "runs")
    handoff = write_handoff(config, make_plan(), tmp_path / "target", "run1")

    assert handoff == tmp_path / "runs" / "run1" / "handoff.md"
    assert handoff.exists()
    assert not (tmp_path / "target" / ".auto-maintainer").exists()


def test_load_plan_round_trips_plan(tmp_path: Path):
    config = Config(repo=RepoRef("owner", "repo"), report_dir=tmp_path)
    plan = make_plan()
    write_plan_report(config, state=RepoState(open_prs=[], open_issues=[], latest_checks=[], security_alerts=[]), candidates=[plan.candidate], plan=plan, run_id="run1")

    loaded = load_plan(tmp_path, "run1")

    assert loaded is not None
    assert loaded.candidate.id == plan.candidate.id
    assert loaded.branch_name == plan.branch_name

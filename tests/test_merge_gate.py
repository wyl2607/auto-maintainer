from auto_maintainer.ci_watcher import evaluate_merge_gate
from auto_maintainer.models import Config, RepoRef
from auto_maintainer.reporting import write_merge_gate_report


def test_evaluate_merge_gate_blocks_draft(monkeypatch):
    def fake_json(args, allow_failure=False, timeout=120):
        if args[:2] == ["pr", "view"]:
            return {
                "number": 1,
                "state": "OPEN",
                "isDraft": True,
                "mergeStateStatus": "CLEAN",
                "reviewDecision": None,
                "baseRefName": "main",
                "headRefName": "feature",
                "url": "https://example.test/pr/1",
            }
        if args[:2] == ["pr", "checks"]:
            return []
        raise AssertionError(args)

    monkeypatch.setattr("auto_maintainer.ci_watcher.run_gh_json", fake_json)

    result = evaluate_merge_gate("owner/repo", "1")

    assert result["ready"] is False
    assert "PR is still draft." in result["blockers"]


def test_write_merge_gate_report(tmp_path):
    config = Config(repo=RepoRef("owner", "repo"), report_dir=tmp_path)

    path = write_merge_gate_report(config, "1", {"ready": False, "blockers": ["blocked"]}, "run1")

    assert path.exists()
    assert (tmp_path / "run1" / "merge-gate.json").exists()


def _gate(monkeypatch, pr_overrides, checks):
    def fake_json(args, allow_failure=False, timeout=120):
        if args[:2] == ["pr", "view"]:
            data = {"number": 1, "state": "OPEN", "isDraft": False, "mergeStateStatus": "CLEAN", "reviewDecision": "APPROVED"}
            data.update(pr_overrides)
            return data
        return checks

    monkeypatch.setattr("auto_maintainer.ci_watcher.run_gh_json", fake_json)
    return evaluate_merge_gate("owner/repo", "1")


def test_merge_gate_ready_when_clean(monkeypatch):
    result = _gate(monkeypatch, {}, [{"name": "t", "state": "SUCCESS", "bucket": "pass"}])

    assert result["ready"] is True
    assert result["blockers"] == []


def test_merge_gate_blocks_failed_and_pending_checks(monkeypatch):
    checks = [
        {"name": "a", "state": "FAILURE", "bucket": "fail"},
        {"name": "b", "state": "PENDING", "bucket": "pending"},
    ]
    result = _gate(monkeypatch, {}, checks)

    assert result["ready"] is False
    assert "PR has failed checks." in result["blockers"]
    assert "PR has pending checks." in result["blockers"]


def test_merge_gate_blocks_conflict_closed_and_review(monkeypatch):
    result = _gate(monkeypatch, {"state": "CLOSED", "mergeStateStatus": "DIRTY", "reviewDecision": "CHANGES_REQUESTED"}, [])

    assert "PR is not open." in result["blockers"]
    assert "PR has merge conflicts." in result["blockers"]
    assert "Review decision is CHANGES_REQUESTED." in result["blockers"]

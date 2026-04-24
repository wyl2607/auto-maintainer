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

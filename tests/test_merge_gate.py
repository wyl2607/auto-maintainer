from auto_maintainer.ci_watcher import evaluate_merge_gate


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

from auto_maintainer.github import create_draft_pr


def test_create_draft_pr_reuses_existing_open_pr(monkeypatch):
    def fake_json(args, allow_failure=False, timeout=120):
        assert args[:2] == ["pr", "list"]
        return [
            {
                "number": 12,
                "url": "https://example.test/pr/12",
                "title": "Existing",
                "isDraft": True,
                "baseRefName": "main",
                "headRefName": "feature",
            }
        ]

    def fail_text(*args, **kwargs):
        raise AssertionError("should not create a new PR")

    monkeypatch.setattr("auto_maintainer.github.run_gh_json", fake_json)
    monkeypatch.setattr("auto_maintainer.github.run_gh_text", fail_text)

    result = create_draft_pr("owner/repo", "main", "feature", "Title", "Body")

    assert result["existing"] is True
    assert result["number"] == 12
    assert result["url"] == "https://example.test/pr/12"

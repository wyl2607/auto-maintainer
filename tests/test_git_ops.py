from auto_maintainer.git_ops import sync_status


def test_sync_status_reports_expected_shape(monkeypatch, tmp_path):
    calls = []

    def fake_run_git(args, path):
        calls.append(args)
        if args == ["branch", "--show-current"]:
            return "main\n"
        if args == ["rev-parse", "HEAD"]:
            return "local\n"
        if args == ["rev-parse", "origin/main"]:
            return "remote\n"
        if args == ["rev-list", "--left-right", "--count", "HEAD...origin/main"]:
            return "0\t0\n"
        if args == ["status", "--short"]:
            return ""
        if args == ["fetch", "origin"]:
            return ""
        raise AssertionError(args)

    monkeypatch.setattr("auto_maintainer.git_ops.run_git", fake_run_git)

    result = sync_status(tmp_path)

    assert result["up_to_date"] is True
    assert result["dirty"] is False
    assert ["fetch", "origin"] in calls

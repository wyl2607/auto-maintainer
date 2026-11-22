from auto_maintainer.ci_watcher import classify_text


def test_classifies_generated_type_drift():
    category, excerpt = classify_text("Fail on generated type drift (PR gate)")

    assert category == "contract_type_drift"
    assert "generated type drift" in excerpt


def test_classifies_pytest_failure():
    category, _ = classify_text("FAILED tests/test_api.py::test_case - AssertionError")

    assert category == "unit_test_failure"


def test_classifies_unknown_text():
    category, _ = classify_text("everything fine here")

    assert category == "unknown"


def test_classify_failure_prefers_check_names_then_logs():
    from auto_maintainer.ci_watcher import classify_failure

    assert classify_failure([{"name": "ruff", "conclusion": "failure"}], []) == "lint_failure"
    assert classify_failure([{"name": "build"}], [{"category": "flaky_infra"}]) == "flaky_infra"
    assert classify_failure([], [{"category": "unknown"}]) == "unknown"


def test_normalize_check_maps_gh_fields():
    from auto_maintainer.ci_watcher import extract_failed_checks, normalize_check

    failed = normalize_check({"name": "t", "state": "FAILURE", "bucket": "fail", "workflow": "Tests", "link": "http://x"})
    passed = normalize_check({"name": "u", "state": "SUCCESS", "bucket": "pass", "workflow": "Tests", "link": "http://y"})

    assert failed["workflowName"] == "Tests"
    assert failed["detailsUrl"] == "http://x"
    assert extract_failed_checks([failed, passed]) == [failed]


def test_collect_check_runs_requests_only_valid_gh_fields(monkeypatch):
    from auto_maintainer.ci_watcher import collect_check_runs

    seen = {}

    def fake_json(args, allow_failure=False, timeout=120):
        seen["fields"] = args[args.index("--json") + 1].split(",")
        return []

    monkeypatch.setattr("auto_maintainer.ci_watcher.run_gh_json", fake_json)
    collect_check_runs("o/r", "1")

    # Fields listed by `gh pr checks --help`; anything else makes gh fail.
    valid = {"bucket", "completedAt", "description", "event", "link", "name", "startedAt", "state", "workflow"}
    assert set(seen["fields"]) <= valid

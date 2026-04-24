from auto_maintainer.state import load_run_state, record_ci_attempt


def test_record_ci_attempt_stops_at_budget(tmp_path):
    result = {"status": "failed", "classification": "lint_failure", "failed_checks": [{"name": "lint"}]}

    state = record_ci_attempt(tmp_path, "run1", result, 1)

    assert state["attempts"] == 1
    assert state["status"] == "stopped"
    assert "max attempts" in state["stop_reason"]
    assert load_run_state(tmp_path, "run1")["last_ci_classification"] == "lint_failure"

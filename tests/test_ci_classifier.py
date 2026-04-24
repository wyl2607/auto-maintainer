from auto_maintainer.ci_watcher import classify_text


def test_classifies_generated_type_drift():
    category, excerpt = classify_text("Fail on generated type drift (PR gate)")

    assert category == "contract_type_drift"
    assert "generated type drift" in excerpt


def test_classifies_pytest_failure():
    category, _ = classify_text("FAILED tests/test_api.py::test_case - AssertionError")

    assert category == "unit_test_failure"

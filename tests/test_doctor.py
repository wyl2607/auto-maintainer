from auto_maintainer.doctor import check_python, run_doctor


def test_check_python_passes_supported_runtime():
    result = check_python()

    assert result["name"] == "python"
    assert result["ok"] is True


def test_run_doctor_without_optional_inputs():
    result = run_doctor()

    assert "ok" in result
    assert result["checks"]

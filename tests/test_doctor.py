import subprocess

from auto_maintainer.doctor import check_gh_auth, check_python, run_doctor


def test_check_python_passes_supported_runtime():
    result = check_python()

    assert result["name"] == "python"
    assert result["ok"] is True


def test_run_doctor_without_optional_inputs():
    result = run_doctor()

    assert "ok" in result
    assert result["checks"]


def test_check_gh_auth_returns_structured_failure_when_gh_missing(monkeypatch):
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(subprocess, "run", raise_file_not_found)

    result = check_gh_auth()

    assert result == {"name": "gh auth", "ok": False, "detail": "gh not found"}

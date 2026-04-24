import json

from auto_maintainer.config import default_config_json


def test_default_config_json_contains_repo_and_agents(tmp_path):
    data = json.loads(default_config_json("owner/repo", tmp_path / "repo"))

    assert data["repo"]["slug"] == "owner/repo"
    assert data["repo"]["local_path"] == str(tmp_path / "repo")
    assert data["agents"]["worker"] == "opencode"

from auto_maintainer.models import Candidate, CandidateSource, Config, RepoRef
from auto_maintainer.planner import build_execution_plan, slugify


def test_build_execution_plan_uses_agents_and_candidate():
    config = Config(repo=RepoRef("owner", "repo"))
    candidate = Candidate(
        id="backlog:docs/policies/project-consistency-rules.md:41",
        title="CR-03 i18n gap",
        source=CandidateSource.DOCUMENTED_BACKLOG,
        value=3,
        risk=1,
        complexity=2,
        confidence=2,
        reason="test",
        files=["docs/policies/project-consistency-rules.md"],
    )

    plan = build_execution_plan(candidate, config)

    assert plan.worker == "opencode"
    assert plan.reviewer == "manual"
    assert plan.branch_name.startswith("auto/")
    assert plan.verification_commands == ["npm run lint", "npm run build"]
    assert plan.dry_run is True


def test_slugify_limits_unsafe_branch_characters():
    assert slugify("backlog:docs/file.md:41") == "backlog-docs-file.md-41"

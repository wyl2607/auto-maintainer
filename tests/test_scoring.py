from auto_maintainer.models import Candidate, CandidateSource, Config, Decision, RepoRef
from auto_maintainer.scoring import apply_gates, select_candidate


def test_candidate_passes_auto_execute_gates():
    config = Config(repo=RepoRef("owner", "repo"))
    candidate = Candidate(
        id="task:1",
        title="Small safe fix",
        source=CandidateSource.TODO,
        value=3,
        risk=1,
        complexity=1,
        confidence=2,
        reason="test",
    )

    candidates = apply_gates([candidate], config)

    assert candidates[0].decision == Decision.AUTO_EXECUTE
    assert select_candidate(candidates) == candidate


def test_candidate_requires_confirmation_for_sensitive_touch():
    config = Config(repo=RepoRef("owner", "repo"))
    candidate = Candidate(
        id="task:2",
        title="Auth behavior change",
        source=CandidateSource.TODO,
        value=5,
        risk=1,
        complexity=1,
        confidence=3,
        reason="test",
        touches=["auth"],
    )

    candidates = apply_gates([candidate], config)

    assert candidates[0].decision == Decision.NEEDS_CONFIRMATION
    assert select_candidate(candidates) is None

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


def _cand(**kw):
    base = dict(id="c", title="t", source=CandidateSource.TODO, value=3, risk=1, complexity=1, confidence=2, reason="r")
    base.update(kw)
    return Candidate(**base)


def test_score_formula():
    assert _cand(value=4, risk=1, complexity=2, confidence=3).score == 4


def test_gate_boundaries():
    config = Config(repo=RepoRef("o", "r"))
    cases = [
        (_cand(value=2), Decision.STOP),
        (_cand(confidence=1), Decision.STOP),
        (_cand(risk=2, complexity=2), Decision.AUTO_EXECUTE),
        (_cand(risk=3), Decision.NEEDS_CONFIRMATION),
        (_cand(complexity=3), Decision.NEEDS_CONFIRMATION),
    ]
    for candidate, expected in cases:
        assert apply_gates([candidate], config)[0].decision == expected


def test_apply_gates_orders_by_decision_then_score():
    config = Config(repo=RepoRef("o", "r"))
    stop = _cand(id="stop", value=1)
    auto_low = _cand(id="auto_low")
    auto_high = _cand(id="auto_high", value=5)

    ordered = apply_gates([stop, auto_low, auto_high], config)

    assert [c.id for c in ordered] == ["auto_high", "auto_low", "stop"]

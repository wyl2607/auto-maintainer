from __future__ import annotations

from auto_maintainer.models import Candidate, Config, Decision


def apply_gates(candidates: list[Candidate], config: Config) -> list[Candidate]:
    for candidate in candidates:
        candidate.decision, candidate.decision_reason = decide(candidate, config)
    return sorted(candidates, key=lambda item: (decision_rank(item.decision), item.score), reverse=True)


def decide(candidate: Candidate, config: Config) -> tuple[Decision, str]:
    gates = config.gates
    confirmation_touches = set(config.require_confirmation_touches)
    touches_confirmation_area = bool(confirmation_touches.intersection(candidate.touches))

    if touches_confirmation_area:
        return Decision.NEEDS_CONFIRMATION, "Touches an area that requires human confirmation."
    if candidate.risk >= gates.confirmation_risk_min:
        return Decision.NEEDS_CONFIRMATION, "Risk exceeds automatic execution threshold."
    if candidate.complexity >= gates.confirmation_complexity_min:
        return Decision.NEEDS_CONFIRMATION, "Complexity exceeds automatic execution threshold."
    if (
        candidate.value >= gates.value_min
        and candidate.risk <= gates.risk_max
        and candidate.complexity <= gates.complexity_max
        and candidate.confidence >= gates.confidence_min
    ):
        return Decision.AUTO_EXECUTE, "Passes value, risk, complexity, and confidence gates."
    return Decision.STOP, "Does not meet automatic execution gates."


def select_candidate(candidates: list[Candidate]) -> Candidate | None:
    for candidate in candidates:
        if candidate.decision == Decision.AUTO_EXECUTE:
            return candidate
    return None


def decision_rank(decision: Decision | None) -> int:
    if decision == Decision.AUTO_EXECUTE:
        return 3
    if decision == Decision.NEEDS_CONFIRMATION:
        return 2
    if decision == Decision.ANALYZE_ONLY:
        return 1
    return 0

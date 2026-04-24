from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_run_state(report_dir: Path, run_id: str) -> dict[str, Any]:
    path = state_path(report_dir, run_id)
    if not path.exists():
        return {"run_id": run_id, "attempts": 0, "status": "new", "events": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_run_state(report_dir: Path, run_id: str, state: dict[str, Any]) -> Path:
    path = state_path(report_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def record_ci_attempt(report_dir: Path, run_id: str, result: dict[str, Any], max_attempts: int) -> dict[str, Any]:
    state = load_run_state(report_dir, run_id)
    attempts = int(state.get("attempts", 0)) + 1
    classification = result.get("classification", "unknown")
    status = "ci_passed" if result.get("status") == "passed" else "ci_failed"
    stop_reason = None
    if status != "ci_passed" and attempts >= max_attempts:
        status = "stopped"
        stop_reason = f"CI failed {attempts} times; max attempts is {max_attempts}."
    state.update(
        {
            "run_id": run_id,
            "attempts": attempts,
            "max_attempts": max_attempts,
            "status": status,
            "stop_reason": stop_reason,
            "last_ci_classification": classification,
            "last_error_summary": summarize_failure(result),
        }
    )
    events = list(state.get("events", []))
    events.append({"type": "ci", "status": result.get("status"), "classification": classification})
    state["events"] = events
    save_run_state(report_dir, run_id, state)
    return state


def state_path(report_dir: Path, run_id: str) -> Path:
    return report_dir / run_id / "state.json"


def summarize_failure(result: dict[str, Any]) -> str:
    failed = result.get("failed_checks") or []
    if failed:
        first = failed[0]
        return str(first.get("workflowName") or first.get("name") or result.get("classification") or "unknown")
    evidence = result.get("evidence") or []
    if evidence:
        return str(evidence[0].get("excerpt", ""))[:300]
    return str(result.get("classification") or "unknown")

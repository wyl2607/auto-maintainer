from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Decision(str, Enum):
    AUTO_EXECUTE = "auto_execute"
    NEEDS_CONFIRMATION = "needs_confirmation"
    ANALYZE_ONLY = "analyze_only"
    STOP = "stop"


class CandidateSource(str, Enum):
    FAILING_CI = "failing_ci"
    OPEN_PR = "open_pr"
    OPEN_ISSUE = "open_issue"
    SECURITY = "security"
    DOCUMENTED_BACKLOG = "documented_backlog"
    TODO = "todo"


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str
    local_path: Path | None = None
    default_branch: str = "main"

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class Gates:
    value_min: int = 3
    risk_max: int = 2
    complexity_max: int = 2
    confidence_min: int = 2
    confirmation_risk_min: int = 3
    confirmation_complexity_min: int = 3


@dataclass
class ExecutionLimits:
    max_tasks_per_run: int = 1
    max_ci_fix_attempts: int = 3
    max_total_runtime_minutes: int = 90
    require_clean_worktree: bool = True


@dataclass
class AgentConfig:
    controller: str = "local"
    worker: str = "opencode"
    reviewer: str = "manual"


@dataclass
class Config:
    repo: RepoRef
    gates: Gates = field(default_factory=Gates)
    execution: ExecutionLimits = field(default_factory=ExecutionLimits)
    agents: AgentConfig = field(default_factory=AgentConfig)
    report_dir: Path = Path("state/runs")
    merge_mode: str = "ask_before_merge"
    require_confirmation_touches: tuple[str, ...] = (
        "auth",
        "permissions",
        "deployment",
        "secrets",
        "database_schema",
        "public_api_deletion",
        "major_dependency_upgrade",
        "large_refactor",
    )


@dataclass
class ExecutionPlan:
    candidate: Candidate
    controller: str
    worker: str
    reviewer: str
    dry_run: bool
    branch_name: str
    verification_commands: list[str]
    stop_conditions: list[str]
    next_steps: list[str]


@dataclass
class Handoff:
    plan: ExecutionPlan
    local_path: Path
    branch_created: bool
    handoff_path: Path


@dataclass
class RepoState:
    open_prs: list[dict]
    open_issues: list[dict]
    latest_checks: list[dict]
    security_alerts: list[dict]


@dataclass
class Candidate:
    id: str
    title: str
    source: CandidateSource
    value: int
    risk: int
    complexity: int
    confidence: int
    reason: str
    files: list[str] = field(default_factory=list)
    touches: list[str] = field(default_factory=list)
    decision: Decision | None = None
    decision_reason: str = ""

    @property
    def score(self) -> int:
        return self.value - self.risk - self.complexity + self.confidence


@dataclass
class RunResult:
    run_id: str
    repo: RepoRef
    state: RepoState
    candidates: list[Candidate]
    selected: Candidate | None
    outcome: str
    report_path: Path

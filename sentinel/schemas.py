from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    timed_out = "timed_out"
    unavailable = "unavailable"


class GraphNode(BaseModel):
    id: str
    kind: str
    file: str
    line: int
    label: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "calls"


class KnowledgeGraph(BaseModel):
    provider: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    blast_radius: list[str] = Field(default_factory=list)


class ChaosPlan(BaseModel):
    title: str
    rationale: str
    attack_code_b64: str
    expected_signal: str
    risk_level: int = Field(ge=1, le=5)
    generator: str = "deterministic-demo"


class TelemetrySample(BaseModel):
    elapsed_seconds: float
    cpu_percent: float = 0.0
    memory_bytes: int = 0


class SandboxResult(BaseModel):
    status: RunStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    telemetry: list[TelemetrySample] = Field(default_factory=list)
    failure_kind: str | None = None
    policy_violations: list[str] = Field(default_factory=list)
    runner: str


class PatchPlan(BaseModel):
    title: str
    rationale: str
    file_path: str = "main.py"
    patched_source_b64: str
    verification_note: str
    branch_name: str = "sentinel/fix"
    generator: str = "deterministic-demo"


class GitPatchResult(BaseModel):
    branch: str
    commit: str
    diff: str
    github_pr_url: str | None = None


class SentinelReport(BaseModel):
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    target: str
    graph: KnowledgeGraph
    chaos: ChaosPlan
    sandbox: SandboxResult
    patch: PatchPlan | None = None
    git: GitPatchResult | None = None
    verification: SandboxResult | None = None
    notes: list[str] = Field(default_factory=list)

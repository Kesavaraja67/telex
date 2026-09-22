"""
Pydantic request/response schemas — Section 9 API contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

# ── Auth ──────────────────────────────────────────────────────────────────────


class UserOut(BaseModel):
    id: uuid.UUID
    github_login: str
    email: str | None
    avatar_url: str | None

    model_config = {"from_attributes": True}


# ── Repos ─────────────────────────────────────────────────────────────────────


class CommitInfo(BaseModel):
    hash: str
    short_hash: str
    message: str
    author: str
    email: str | None = None
    date: str
    relative_time: str


class RepoOut(BaseModel):
    id: str
    full_name: str
    name: str | None = None
    owner: str | None = None
    description: str | None = None
    default_branch: str = "main"
    is_active: bool = True
    requires_tests: bool = False
    requires_typecheck: bool = False
    allow_install_scripts: bool = False
    created_at: datetime
    github_url: str
    languages: list[str] = []
    patch_count: int = 0
    status: str = "healthy"
    last_commit: CommitInfo | None = None
    dependencies: list[str] = []

    model_config = {"from_attributes": True}


class RepoUpdateIn(BaseModel):
    requires_tests: bool | None = None
    requires_typecheck: bool | None = None
    is_active: bool | None = None
    allow_install_scripts: bool | None = None


class RepoDetailOut(RepoOut):
    commits: list[CommitInfo] = []


class CommitInsight(BaseModel):
    hash: str
    impact: str
    risk_level: str


class AIExplainOut(BaseModel):
    summary: str
    commit_insights: list[CommitInsight] = []
    architecture_verdict: str
    risk_score: int
    recommended_actions: list[str] = []


class RepoToggleIn(BaseModel):
    is_active: bool


# ── Patches ───────────────────────────────────────────────────────────────────


class PatchOut(BaseModel):
    id: str
    package: str
    old_version: str
    new_version: str
    status: str
    pr_url: str | None = None
    usages_patched: int = 1
    opened_at: datetime
    diff: str | None = None
    verification_mode: str | None = None
    tests_passed: bool | None = None
    typecheck_passed: bool | None = None
    change_type: str | None = None
    change_description: str | None = None
    confidence: float | None = None
    is_semantic_risk: bool | None = None


class RepoPatchesOut(BaseModel):
    repo: str
    patches: list[PatchOut]


# ── Stats ─────────────────────────────────────────────────────────────────────


class DetectedChangeSummary(BaseModel):
    id: str
    symbol_old: str
    symbol_new: str | None = None
    change_type: str
    description: str
    created_at: datetime
    confidence: float | None = None
    is_semantic_risk: bool | None = None


class StatsOut(BaseModel):
    repos_watched: int
    prs_opened: int
    patches_generated: int
    merge_rate: float  # fraction 0.0–1.0
    recent_changes: list[DetectedChangeSummary] = []


# ── Webhooks ──────────────────────────────────────────────────────────────────


class GitHubInstallationEvent(BaseModel):
    action: str
    installation: dict
    repositories: list[dict] | None = None


# ── Rescan ────────────────────────────────────────────────────────────────────


class RescanIn(BaseModel):
    package_name: str
    old_version: str
    new_version: str
    changelog: str | None = None


# ── Organism View / Incident Graphs ───────────────────────────────────────────


class IncidentNodeOut(BaseModel):
    """One call-site node in an incident graph (one CodeUsage row)."""

    code_usage_id: str
    file_path: str
    line_start: int
    line_end: int
    status: str  # pending | patched | skipped | failed
    patch_verified: bool | None = None
    validation: dict | None = None  # {applies_cleanly, typechecks, tests_pass, scope_ok}
    pr_url: str | None = None
    pr_merged: bool | None = None

    model_config = {"from_attributes": True}


class IncidentGraphOut(BaseModel):
    """Full snapshot of one incident — root DetectedChange + all CodeUsage nodes."""

    detected_change_id: str
    repo_id: str
    package: str
    symbol_old: str
    symbol_new: str | None
    change_type: str
    confidence: float
    created_at: str
    nodes: list[IncidentNodeOut]

    model_config = {"from_attributes": True}


class IncidentEventOut(BaseModel):
    """One row from incident_events — used for the events history endpoint (replay)."""

    id: str
    event_type: str
    repo_id: str | None
    detected_change_id: str | None
    code_usage_id: str | None
    job_id: str | None
    payload: dict
    created_at: str

    model_config = {"from_attributes": True}

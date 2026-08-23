"""
Pydantic request/response schemas — Section 9 API contract.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    github_login: str
    email: Optional[str]
    avatar_url: Optional[str]

    model_config = {"from_attributes": True}


# ── Repos ─────────────────────────────────────────────────────────────────────

class CommitInfo(BaseModel):
    hash: str
    short_hash: str
    message: str
    author: str
    email: Optional[str] = None
    date: str
    relative_time: str


class RepoOut(BaseModel):
    id: str
    full_name: str
    name: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    default_branch: str = "main"
    is_active: bool = True
    created_at: datetime
    github_url: str
    languages: list[str] = []
    patch_count: int = 0
    status: str = "healthy"
    last_commit: Optional[CommitInfo] = None
    dependencies: list[str] = []

    model_config = {"from_attributes": True}


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
    pr_url: Optional[str]
    usages_patched: int
    opened_at: datetime


class RepoPatchesOut(BaseModel):
    repo: str
    patches: list[PatchOut]


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsOut(BaseModel):
    repos_watched: int
    prs_opened: int
    patches_generated: int
    merge_rate: float  # fraction 0.0–1.0


# ── Webhooks ──────────────────────────────────────────────────────────────────

class GitHubInstallationEvent(BaseModel):
    action: str
    installation: dict
    repositories: Optional[list[dict]] = None


# ── Rescan ────────────────────────────────────────────────────────────────────

class RescanIn(BaseModel):
    package_name: str
    old_version: str
    new_version: str
    changelog: Optional[str] = None


# ── Engine B — Payments & Recovery ─────────────────────────────────────────────

class VerifySignatureIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RecoveryEventOut(BaseModel):
    id: uuid.UUID
    payment_attempt_id: uuid.UUID
    failure_type: str
    classification: str
    action_taken: str
    llm_provider: str
    llm_model: str
    outcome: str
    pull_request_id: Optional[uuid.UUID] = None
    amount: Optional[int] = 0  # paise
    detected_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecoveryStatsOut(BaseModel):
    total_payment_attempts: int
    total_recovery_events: int
    recovered: int
    escalated: int
    unresolved: int
    recovery_rate: float  # fraction 0.0–1.0
    tier1_classified: int  # classified via deterministic rule (no LLM)
    tier2_classified: int  # classified via LLM call
    revenue_at_risk: int = 0  # paise
    revenue_recovered: int = 0  # paise


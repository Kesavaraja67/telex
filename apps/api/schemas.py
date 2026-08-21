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

class RepoOut(BaseModel):
    id: uuid.UUID
    full_name: str
    default_branch: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


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


# ── Engine B — Recovery ────────────────────────────────────────────────────────

class RecoveryEventOut(BaseModel):
    id: str
    payment_attempt_id: str
    failure_type: str
    classification: str
    action_taken: str
    llm_provider: str
    llm_model: str
    outcome: str
    pull_request_id: Optional[str]
    detected_at: str
    resolved_at: Optional[str]


class RecoveryStatsOut(BaseModel):
    total_payment_attempts: int
    total_recovery_events: int
    recovered: int
    escalated: int
    unresolved: int
    recovery_rate: float  # fraction 0.0–1.0
    tier1_classified: int  # classified via deterministic rule (no LLM)
    tier2_classified: int  # classified via LLM call

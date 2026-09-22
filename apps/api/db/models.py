import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    REAL,
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Users ────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_login: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    installations: Mapped[list["Installation"]] = relationship(back_populates="installed_by_user")
    api_keys: Mapped[list["UserApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ─── UserApiKeys (BYOK) ──────────────────────────────────────────────────────


class UserApiKey(Base):
    """Stores per-user, per-provider encrypted API keys for BYOK feature."""

    __tablename__ = "user_api_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_api_keys_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # e.g. "openai", "anthropic", "gemini"
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_keys")


# ─── Installations ────────────────────────────────────────────────────────────


class Installation(Base):
    __tablename__ = "installations"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('User','Organization')", name="ck_installations_account_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    account_login: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    installed_by_user: Mapped[Optional["User"]] = relationship(back_populates="installations")
    repos: Mapped[list["Repo"]] = relationship(back_populates="installation")


# ─── Repos ────────────────────────────────────────────────────────────────────


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    installation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("installations.id", ondelete="CASCADE"), nullable=False
    )
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_tests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_typecheck: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_install_scripts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    installation: Mapped["Installation"] = relationship(back_populates="repos")
    repo_packages: Mapped[list["RepoPackage"]] = relationship(back_populates="repo")
    code_usages: Mapped[list["CodeUsage"]] = relationship(back_populates="repo")
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="repo")


# ─── Packages ─────────────────────────────────────────────────────────────────


class Package(Base):
    __tablename__ = "packages"
    __table_args__ = (
        CheckConstraint("ecosystem IN ('npm','pypi')", name="ck_packages_ecosystem"),
        UniqueConstraint("ecosystem", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ecosystem: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[str | None] = mapped_column(Text)

    repo_packages: Mapped[list["RepoPackage"]] = relationship(back_populates="package")
    versions: Mapped[list["PackageVersion"]] = relationship(back_populates="package")


# ─── RepoPackages ─────────────────────────────────────────────────────────────


class RepoPackage(Base):
    __tablename__ = "repo_packages"
    __table_args__ = (UniqueConstraint("repo_id", "package_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False
    )
    current_version: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_path: Mapped[str] = mapped_column(Text, nullable=False)

    repo: Mapped["Repo"] = relationship(back_populates="repo_packages")
    package: Mapped["Package"] = relationship(back_populates="repo_packages")


# ─── PackageVersions ──────────────────────────────────────────────────────────


class PackageVersion(Base):
    __tablename__ = "package_versions"
    __table_args__ = (UniqueConstraint("package_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    changelog_raw: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    scanned_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    package: Mapped["Package"] = relationship(back_populates="versions")
    detected_changes: Mapped[list["DetectedChange"]] = relationship(
        back_populates="package_version"
    )
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="package_version")


# ─── DetectedChanges ──────────────────────────────────────────────────────────


class DetectedChange(Base):
    __tablename__ = "detected_changes"
    __table_args__ = (
        CheckConstraint(
            "change_type IN ('signature_change','removed','renamed','deprecated','behavior_change')",
            name="ck_detected_changes_type",
        ),
        CheckConstraint(
            "source IN ('npm_registry','internal_runtime')",
            name="ck_detected_changes_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("package_versions.id", ondelete="CASCADE"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="npm_registry")
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_old: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_new: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(REAL, nullable=False, default=0.8)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    package_version: Mapped["PackageVersion"] = relationship(back_populates="detected_changes")
    code_usages: Mapped[list["CodeUsage"]] = relationship(back_populates="detected_change")


# ─── CodeUsages ───────────────────────────────────────────────────────────────


class CodeUsage(Base):
    __tablename__ = "code_usages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','patched','skipped','failed')", name="ck_code_usages_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False
    )
    detected_change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("detected_changes.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    repo: Mapped["Repo"] = relationship(back_populates="code_usages")
    detected_change: Mapped["DetectedChange"] = relationship(back_populates="code_usages")
    patches: Mapped[list["Patch"]] = relationship(back_populates="code_usage")


# ─── Patches ──────────────────────────────────────────────────────────────────


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_usage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("code_usages.id", ondelete="CASCADE"), nullable=False
    )
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    code_usage: Mapped["CodeUsage"] = relationship(back_populates="patches")
    validation_runs: Mapped[list["ValidationRun"]] = relationship(back_populates="patch")


# ─── ValidationRuns ───────────────────────────────────────────────────────────


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patches.id", ondelete="CASCADE"), nullable=False
    )
    verification_mode: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # "full" | "structural_only"
    applies_cleanly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    parses: Mapped[bool] = mapped_column(Boolean, nullable=False)
    typechecks: Mapped[bool | None] = mapped_column(Boolean)
    tests_pass: Mapped[bool | None] = mapped_column(Boolean)
    scope_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    patch: Mapped["Patch"] = relationship(back_populates="validation_runs")


# ─── PullRequests ─────────────────────────────────────────────────────────────


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        CheckConstraint("status IN ('open','merged','closed')", name="ck_pull_requests_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False
    )
    package_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("package_versions.id"), nullable=True
    )
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    github_pr_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    patch_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    opened_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    merged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    repo: Mapped["Repo"] = relationship(back_populates="pull_requests")
    package_version: Mapped["PackageVersion"] = relationship(back_populates="pull_requests")


# ─── IncidentEvents ───────────────────────────────────────────────────────────


class IncidentEvent(Base):
    """Append-only log of every state transition across all pipeline entities.

    Required for two things:
    1. Live SSE streaming to already-connected clients — the in-process
       event_bus carries these to open SSE connections in the same process.
    2. Catch-up & replay — a client that joins mid-incident can call
       GET /incidents/{id}/graph for a full snapshot, then GET
       /incidents/{id}/events?since=<ts> to replay or stream from there.

    Additive only — no ALTER or UPDATE, zero risk to existing functionality.
    """

    __tablename__ = "incident_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'change_detected','scan_started','usage_found',"
            "'patch_generating','patch_generated','patch_failed',"
            "'validating','validation_passed','validation_failed',"
            "'pr_opened','pr_merged','pr_closed',"
            "'usage_skipped','usage_failed',"
            "'job_queued','job_running','job_done','job_failed'"
            ")",
            name="ck_incident_events_type",
        ),
        Index("idx_incident_events_repo_created", "repo_id", "created_at"),
        Index("idx_incident_events_change_created", "detected_change_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    detected_change_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("detected_changes.id", ondelete="CASCADE"), nullable=True
    )
    code_usage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("code_usages.id", ondelete="CASCADE"), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Small denormalized payload so the frontend doesn't need extra joins to
    # render a single event: file_path, confidence, pr_url, test outcome, etc.
    # Keep this small — it is not a replacement for the real rows.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


# ─── Jobs ─────────────────────────────────────────────────────────────────────


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('poll_registry', 'extract_changes', 'scan_repo', 'generate_patch', 'validate_patch', 'open_pr', 'build_atlas_graph')",
            name="ck_jobs_type",
        ),
        CheckConstraint(
            "status IN ('queued','running','done','failed')",
            name="ck_jobs_status",
        ),
        Index(
            "idx_jobs_status_run_after", "status", "run_after", postgresql_where="status = 'queued'"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    run_after: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ─── RepoAtlasGraph ───────────────────────────────────────────────────────────


class RepoAtlasGraph(Base):
    __tablename__ = "repo_atlas_graphs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('computing','ready','failed')",
            name="ck_repo_atlas_graphs_status",
        ),
        UniqueConstraint("repo_id", "commit_sha", name="uq_repo_atlas_graphs_repo_commit"),
        Index("idx_repo_atlas_graphs_repo_status", "repo_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="computing")
    node_count: Mapped[int | None] = mapped_column(Integer)
    edge_count: Mapped[int | None] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    graph_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

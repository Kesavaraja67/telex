import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Float, ForeignKey, Index,
    Integer, REAL, Text, TIMESTAMP, UniqueConstraint, func,
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
    email: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    installations: Mapped[List["Installation"]] = relationship(back_populates="installed_by_user")


# ─── Installations ────────────────────────────────────────────────────────────

class Installation(Base):
    __tablename__ = "installations"
    __table_args__ = (
        CheckConstraint("account_type IN ('User','Organization')", name="ck_installations_account_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    account_login: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    installed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    installed_by_user: Mapped[Optional["User"]] = relationship(back_populates="installations")
    repos: Mapped[List["Repo"]] = relationship(back_populates="installation")


# ─── Repos ────────────────────────────────────────────────────────────────────

class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("installations.id", ondelete="CASCADE"), nullable=False)
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    installation: Mapped["Installation"] = relationship(back_populates="repos")
    repo_packages: Mapped[List["RepoPackage"]] = relationship(back_populates="repo")
    code_usages: Mapped[List["CodeUsage"]] = relationship(back_populates="repo")
    pull_requests: Mapped[List["PullRequest"]] = relationship(back_populates="repo")


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
    repo_url: Mapped[Optional[str]] = mapped_column(Text)

    repo_packages: Mapped[List["RepoPackage"]] = relationship(back_populates="package")
    versions: Mapped[List["PackageVersion"]] = relationship(back_populates="package")


# ─── RepoPackages ─────────────────────────────────────────────────────────────

class RepoPackage(Base):
    __tablename__ = "repo_packages"
    __table_args__ = (UniqueConstraint("repo_id", "package_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    current_version: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_path: Mapped[str] = mapped_column(Text, nullable=False)

    repo: Mapped["Repo"] = relationship(back_populates="repo_packages")
    package: Mapped["Package"] = relationship(back_populates="repo_packages")


# ─── PackageVersions ──────────────────────────────────────────────────────────

class PackageVersion(Base):
    __tablename__ = "package_versions"
    __table_args__ = (UniqueConstraint("package_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    changelog_raw: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    scanned_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    package: Mapped["Package"] = relationship(back_populates="versions")
    detected_changes: Mapped[List["DetectedChange"]] = relationship(back_populates="package_version")
    pull_requests: Mapped[List["PullRequest"]] = relationship(back_populates="package_version")


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
    package_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("package_versions.id", ondelete="CASCADE"), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="npm_registry")
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_old: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_new: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(REAL, nullable=False, default=0.8)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    package_version: Mapped["PackageVersion"] = relationship(back_populates="detected_changes")
    code_usages: Mapped[List["CodeUsage"]] = relationship(back_populates="detected_change")


# ─── CodeUsages ───────────────────────────────────────────────────────────────

class CodeUsage(Base):
    __tablename__ = "code_usages"
    __table_args__ = (
        CheckConstraint("status IN ('pending','patched','skipped','failed')", name="ck_code_usages_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    detected_change_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("detected_changes.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    repo: Mapped["Repo"] = relationship(back_populates="code_usages")
    detected_change: Mapped["DetectedChange"] = relationship(back_populates="code_usages")
    patches: Mapped[List["Patch"]] = relationship(back_populates="code_usage")


# ─── Patches ──────────────────────────────────────────────────────────────────

class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_usage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("code_usages.id", ondelete="CASCADE"), nullable=False)
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    code_usage: Mapped["CodeUsage"] = relationship(back_populates="patches")
    validation_runs: Mapped[List["ValidationRun"]] = relationship(back_populates="patch")


# ─── ValidationRuns ───────────────────────────────────────────────────────────

class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patches.id", ondelete="CASCADE"), nullable=False)
    applies_cleanly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    parses: Mapped[bool] = mapped_column(Boolean, nullable=False)
    typechecks: Mapped[Optional[bool]] = mapped_column(Boolean)
    tests_pass: Mapped[Optional[bool]] = mapped_column(Boolean)
    scope_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    log: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    patch: Mapped["Patch"] = relationship(back_populates="validation_runs")


# ─── PullRequests ─────────────────────────────────────────────────────────────

class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        CheckConstraint("status IN ('open','merged','closed')", name="ck_pull_requests_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    package_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("package_versions.id"), nullable=True)
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    github_pr_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    patch_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    opened_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    repo: Mapped["Repo"] = relationship(back_populates="pull_requests")
    package_version: Mapped["PackageVersion"] = relationship(back_populates="pull_requests")


# ─── Jobs ─────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('poll_registry','extract_changes','scan_repo','generate_patch','open_pr')",
            name="ck_jobs_type",
        ),
        CheckConstraint(
            "status IN ('queued','running','done','failed')",
            name="ck_jobs_status",
        ),
        Index("idx_jobs_status_run_after", "status", "run_after", postgresql_where="status = 'queued'"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    run_after: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    locked_by: Mapped[Optional[str]] = mapped_column(Text)
    locked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ─── PaymentAttempts ──────────────────────────────────────────────────────────

class PaymentAttempt(Base):
    """Tracks each real or simulated Razorpay Test Mode payment attempt."""
    __tablename__ = "payment_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','success','failed')",
            name="ck_payment_attempts_status",
        ),
        Index("idx_payment_attempts_razorpay_order_id", "razorpay_order_id"),
        Index("idx_payment_attempts_batch_request_id", "batch_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razorpay_order_id: Mapped[str] = mapped_column(Text, nullable=False)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    status: Mapped[str] = mapped_column(Text, nullable=False, default="created")
    # null = organic attempt; non-null = injected failure type e.g. "timeout"
    injected_failure: Mapped[Optional[str]] = mapped_column(Text)
    # Optional idempotency key per batch-run request (section 10.5)
    batch_request_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    recovery_events: Mapped[List["RecoveryEvent"]] = relationship(back_populates="payment_attempt")


# ─── RecoveryEvents ───────────────────────────────────────────────────────────

class RecoveryEvent(Base):
    """Records each failure classification and recovery action taken."""
    __tablename__ = "recovery_events"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('transient','code_defect','unknown')",
            name="ck_recovery_events_classification",
        ),
        CheckConstraint(
            "outcome IN ('recovered','escalated','unresolved')",
            name="ck_recovery_events_outcome",
        ),
        Index("idx_recovery_events_payment_attempt_id", "payment_attempt_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_attempts.id", ondelete="CASCADE"), nullable=False
    )
    failure_type: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    action_taken: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False, default="none")
    llm_model: Mapped[str] = mapped_column(Text, nullable=False, default="none")
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="unresolved")
    # Populated when code_defect escalation produces a real PR
    pull_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("pull_requests.id"))
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    payment_attempt: Mapped["PaymentAttempt"] = relationship(back_populates="recovery_events")


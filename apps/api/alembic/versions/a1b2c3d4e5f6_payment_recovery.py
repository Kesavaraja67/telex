"""payment_recovery_engine_b

Revision ID: a1b2c3d4e5f6
Revises: 9391613f4c07
Create Date: 2026-08-21 10:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9391613f4c07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Engine B Payment Recovery schema changes."""

    # 1. payment_attempts table
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("razorpay_order_id", sa.Text(), nullable=False),
        sa.Column("razorpay_payment_id", sa.Text(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column("injected_failure", sa.Text(), nullable=True),
        sa.Column("batch_request_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('created','success','failed')", name="ck_payment_attempts_status"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. recovery_events table
    op.create_table(
        "recovery_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payment_attempt_id", sa.UUID(), nullable=False),
        sa.Column("failure_type", sa.Text(), nullable=False),
        sa.Column("classification", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("action_taken", sa.Text(), nullable=False, server_default=""),
        sa.Column("llm_provider", sa.Text(), nullable=False, server_default="none"),
        sa.Column("llm_model", sa.Text(), nullable=False, server_default="none"),
        sa.Column("outcome", sa.Text(), nullable=False, server_default="unresolved"),
        sa.Column("pull_request_id", sa.UUID(), nullable=True),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "classification IN ('transient','code_defect','unknown')",
            name="ck_recovery_events_classification",
        ),
        sa.CheckConstraint(
            "outcome IN ('recovered','escalated','unresolved')",
            name="ck_recovery_events_outcome",
        ),
        sa.ForeignKeyConstraint(["payment_attempt_id"], ["payment_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pull_request_id"], ["pull_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. detected_changes: make package_version_id nullable + add source column
    op.alter_column("detected_changes", "package_version_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("detected_changes", sa.Column("source", sa.Text(), nullable=False, server_default="npm_registry"))
    op.create_check_constraint(
        "ck_detected_changes_source",
        "detected_changes",
        "source IN ('npm_registry','internal_runtime')",
    )

    # 4. pull_requests: make package_version_id nullable (needed for Engine B PRs)
    op.alter_column("pull_requests", "package_version_id", existing_type=sa.UUID(), nullable=True)

    # 5. jobs: expand job_type CHECK constraint (add 3 new values, keep all 5 original)
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_type",
        "jobs",
        (
            "job_type IN ("
            "'poll_registry','extract_changes','scan_repo','generate_patch','open_pr',"
            "'detect_payment_failure','diagnose_runtime_failure','recover_runtime'"
            ")"
        ),
    )


def downgrade() -> None:
    """Reverse Engine B schema changes."""
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_type",
        "jobs",
        "job_type IN ('poll_registry','extract_changes','scan_repo','generate_patch','open_pr')",
    )
    op.alter_column("pull_requests", "package_version_id", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint("ck_detected_changes_source", "detected_changes", type_="check")
    op.drop_column("detected_changes", "source")
    op.alter_column("detected_changes", "package_version_id", existing_type=sa.UUID(), nullable=False)
    op.drop_table("recovery_events")
    op.drop_table("payment_attempts")

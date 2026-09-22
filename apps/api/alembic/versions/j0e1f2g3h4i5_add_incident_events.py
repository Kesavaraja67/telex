"""add_incident_events

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-09-22 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j0e1f2g3h4i5"
down_revision: Union[str, Sequence[str], None] = "i9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incident_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "detected_change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("detected_changes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "code_usage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("code_usages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
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
    )

    op.create_index(
        "idx_incident_events_repo_created",
        "incident_events",
        ["repo_id", "created_at"],
    )
    op.create_index(
        "idx_incident_events_change_created",
        "incident_events",
        ["detected_change_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_incident_events_change_created", table_name="incident_events")
    op.drop_index("idx_incident_events_repo_created", table_name="incident_events")
    op.drop_table("incident_events")

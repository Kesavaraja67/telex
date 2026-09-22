"""add repo_atlas_graphs cache table + build_atlas_graph job type

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-09-22 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "k1f2g3h4i5j6"
down_revision: Union[str, Sequence[str], None] = "j0e1f2g3h4i5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repo_atlas_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="computing"),
        sa.Column("node_count", sa.Integer(), nullable=True),
        sa.Column("edge_count", sa.Integer(), nullable=True),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("graph_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('computing','ready','failed')",
            name="ck_repo_atlas_graphs_status",
        ),
        sa.UniqueConstraint(
            "repo_id", "commit_sha", name="uq_repo_atlas_graphs_repo_commit"
        ),
    )
    op.create_index(
        "idx_repo_atlas_graphs_repo_status",
        "repo_atlas_graphs",
        ["repo_id", "status"],
    )

    # Update jobs check constraint for Postgres
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
        op.execute(
            "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type CHECK ("
            "job_type IN ('poll_registry','extract_changes','scan_repo',"
            "'generate_patch','validate_patch','open_pr','build_atlas_graph'))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
        op.execute(
            "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type CHECK ("
            "job_type IN ('poll_registry','extract_changes','scan_repo',"
            "'generate_patch','validate_patch','open_pr'))"
        )
    op.drop_index("idx_repo_atlas_graphs_repo_status", table_name="repo_atlas_graphs")
    op.drop_table("repo_atlas_graphs")

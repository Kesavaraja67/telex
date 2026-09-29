"""add atlas_nodes, atlas_edges, and atlas_state tables + update_atlas_graph job type

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-09-28 16:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "l2g3h4i5j6k7"
down_revision: Union[str, Sequence[str], None] = "k1f2g3h4i5j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. atlas_nodes
    op.create_table(
        "atlas_nodes",
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("path", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("dir", sa.Text(), nullable=False, server_default=""),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ext", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.Text(), nullable=False, server_default="plaintext"),
        sa.Column("is_binary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("unresolved_specifiers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("updated_sha", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_atlas_nodes_repo", "atlas_nodes", ["repo_id"])

    # 2. atlas_edges
    op.create_table(
        "atlas_edges",
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_path", sa.Text(), primary_key=True),
        sa.Column("target_path", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False, server_default="static"),
        sa.Column("updated_sha", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["repo_id", "source_path"],
            ["atlas_nodes.repo_id", "atlas_nodes.path"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repo_id", "target_path"],
            ["atlas_nodes.repo_id", "atlas_nodes.path"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_atlas_edges_target", "atlas_edges", ["repo_id", "target_path"])
    op.create_index("ix_atlas_edges_source", "atlas_edges", ["repo_id", "source_path"])

    # 3. atlas_state
    op.create_table(
        "atlas_state",
        sa.Column(
            "repo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("head_sha", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="idle"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_full_scan_sha", sa.Text(), nullable=True),
        sa.Column("last_full_scan_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("alias_config_hash", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. Update jobs check constraint for Postgres to include update_atlas_graph
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
        op.execute(
            "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type CHECK ("
            "job_type IN ('poll_registry','extract_changes','scan_repo',"
            "'generate_patch','validate_patch','open_pr','build_atlas_graph','update_atlas_graph'))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DELETE FROM jobs WHERE job_type = 'update_atlas_graph'")
        op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
        op.execute(
            "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type CHECK ("
            "job_type IN ('poll_registry','extract_changes','scan_repo',"
            "'generate_patch','validate_patch','open_pr','build_atlas_graph'))"
        )
    op.drop_table("atlas_state")
    op.drop_index("ix_atlas_edges_source", table_name="atlas_edges")
    op.drop_index("ix_atlas_edges_target", table_name="atlas_edges")
    op.drop_table("atlas_edges")
    op.drop_index("ix_atlas_nodes_repo", table_name="atlas_nodes")
    op.drop_table("atlas_nodes")

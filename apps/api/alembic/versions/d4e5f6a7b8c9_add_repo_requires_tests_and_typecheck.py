"""add_repo_requires_tests_and_typecheck

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-23 18:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repos",
        sa.Column("requires_tests", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "repos",
        sa.Column("requires_typecheck", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("repos", "requires_typecheck")
    op.drop_column("repos", "requires_tests")

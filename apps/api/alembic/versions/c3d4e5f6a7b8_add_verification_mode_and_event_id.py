"""add_verification_mode_and_event_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-22 18:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("verification_mode", sa.Text(), nullable=True),
    )
    op.add_column(
        "payment_attempts",
        sa.Column("razorpay_event_id", sa.Text(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payment_attempts_razorpay_event_id",
        "payment_attempts",
        ["razorpay_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payment_attempts_razorpay_event_id", "payment_attempts", type_="unique")
    op.drop_column("payment_attempts", "razorpay_event_id")
    op.drop_column("validation_runs", "verification_mode")

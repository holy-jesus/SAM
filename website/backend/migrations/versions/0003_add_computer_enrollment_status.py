"""Add enrollment_status to computers table

Revision ID: 0003_add_enrollment
Revises: 0002_subs_vulns
Create Date: 2026-11-15 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_enrollment"
down_revision = "0002_subs_vulns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add enrollment_status column to computers table
    op.add_column(
        "computers",
        sa.Column(
            "enrollment_status",
            sa.String(50),
            server_default="pending",
            nullable=False,
        ),
    )
    op.create_index(
        "idx_computers_enrollment_status",
        "computers",
        ["enrollment_status"],
    )


def downgrade() -> None:
    op.drop_index("idx_computers_enrollment_status", table_name="computers")
    op.drop_column("computers", "enrollment_status")

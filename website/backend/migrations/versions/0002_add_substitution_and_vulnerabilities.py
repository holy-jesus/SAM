"""Add import_substitutions and vulnerabilities tables

Revision ID: 0002_subs_vulns
Revises: 0001_initial
Create Date: 2026-11-15 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_subs_vulns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. import_substitutions
    op.create_table(
        "import_substitutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("foreign_software_name", sa.String(255), nullable=False),
        sa.Column("russian_software_name", sa.String(500), nullable=False),
        sa.Column("russian_reg_number", sa.String(50), nullable=True),
        sa.Column("source", sa.String(50), server_default="registry", nullable=False),
        sa.Column("owner_name", sa.String(500), nullable=True),
        sa.Column("class_code", sa.String(50), nullable=True),
        sa.Column("class_name", sa.String(255), nullable=True),
        sa.Column("registration_date", sa.String(50), nullable=True),
        sa.Column("registry_url", sa.Text(), nullable=True),
        sa.Column("ru_registry_id", sa.Integer(), sa.ForeignKey("ru_software_registry.id", ondelete="SET NULL"), nullable=True),
        sa.Column("catalog_software_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("software_catalog.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_subs_foreign", "import_substitutions", ["foreign_software_name"])
    op.create_index("idx_subs_russian", "import_substitutions", ["russian_software_name"])
    op.create_index("idx_subs_reg_num", "import_substitutions", ["russian_reg_number"])

    # 2. vulnerabilities (БДУ ФСТЭК России)
    op.create_table(
        "vulnerabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bdu_id", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("vendor", sa.String(255), nullable=False),
        sa.Column("software_name", sa.String(255), nullable=False),
        sa.Column("software_version", sa.Text(), nullable=True),
        sa.Column("software_type", sa.String(255), nullable=True),
        sa.Column("vuln_class", sa.String(255), nullable=True),
        sa.Column("severity", sa.String(50), server_default="Средний", nullable=False),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("exploit_status", sa.String(255), nullable=True),
        sa.Column("cve_id", sa.String(500), nullable=True),
        sa.Column("publish_date", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_vuln_bdu_id", "vulnerabilities", ["bdu_id"])
    op.create_index("idx_vuln_vendor", "vulnerabilities", ["vendor"])
    op.create_index("idx_vuln_sw_name", "vulnerabilities", ["software_name"])
    op.create_index("idx_vuln_severity", "vulnerabilities", ["severity"])
    op.create_index("idx_vuln_cve_id", "vulnerabilities", ["cve_id"])


def downgrade() -> None:
    op.drop_table("vulnerabilities")
    op.drop_table("import_substitutions")

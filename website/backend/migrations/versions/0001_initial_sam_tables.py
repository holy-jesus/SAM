"""Initial SAM tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-11-14 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), server_default="admin", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_users_username", "users", ["username"])

    # 2. employees
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("position", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_employees_status", "employees", ["status"])

    # 3. computers
    op.create_table(
        "computers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("serial_number", sa.String(255), unique=True, nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("mac_address", sa.String(50), nullable=True),
        sa.Column("os_name", sa.String(100), nullable=True),
        sa.Column("os_version", sa.String(100), nullable=True),
        sa.Column("cpu_info", sa.String(255), nullable=True),
        sa.Column("ram_mb", sa.Integer(), nullable=True),
        sa.Column("disk_info", sa.JSON(), nullable=True),
        sa.Column("is_online", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_computers_serial", "computers", ["serial_number"])
    op.create_index("idx_computers_employee", "computers", ["employee_id"])

    # 4. software_categories
    op.create_table(
        "software_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_problematic", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("risk_level", sa.String(20), server_default="none", nullable=False),
        sa.Column("color_hex", sa.String(7), server_default="#6B7280", nullable=False),
    )

    # 5. software_classifiers
    op.create_table(
        "software_classifiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("section_code", sa.String(20), nullable=False),
        sa.Column("section_name", sa.String(255), nullable=False),
        sa.Column("class_name", sa.String(255), nullable=False),
    )
    op.create_index("idx_classifiers_code", "software_classifiers", ["code"])

    # 6. ru_software_registry
    op.create_table(
        "ru_software_registry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reg_number", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("alternative_names", sa.Text(), nullable=True),
        sa.Column("software_class", sa.Text(), nullable=True),
        sa.Column("vendor_name", sa.String(500), nullable=True),
        sa.Column("vendor_inn", sa.String(20), nullable=True),
        sa.Column("documentation_url", sa.Text(), nullable=True),
        sa.Column("is_ai", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("excluded_at", sa.Date(), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ru_registry_name", "ru_software_registry", ["name"])

    # 7. software_catalog
    op.create_table(
        "software_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classifier_id", sa.Integer(), sa.ForeignKey("software_classifiers.id"), nullable=True),
        sa.Column("ru_registry_id", sa.Integer(), sa.ForeignKey("ru_software_registry.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("software_categories.id"), nullable=True),
        sa.Column("license_type", sa.String(50), server_default="Commercial", nullable=False),
        sa.Column("max_installations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("responsible_person", sa.String(255), server_default="Администратор SAM", nullable=False),
        sa.Column("approval_status", sa.String(50), server_default="approved", nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 8. licenses
    op.create_table(
        "licenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("software_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("software_catalog.id", ondelete="CASCADE"), nullable=False),
        sa.Column("license_name", sa.String(255), nullable=False),
        sa.Column("license_type", sa.String(50), nullable=False),
        sa.Column("license_model", sa.String(50), server_default="per_device", nullable=False),
        sa.Column("total_purchased", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("currency", sa.String(10), server_default="RUB", nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("eula_text", sa.Text(), nullable=True),
        sa.Column("eula_analysis", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_licenses_software", "licenses", ["software_id"])

    # 9. installed_software
    op.create_table(
        "installed_software",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("computer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("computers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_display_name", sa.String(500), nullable=False),
        sa.Column("raw_publisher", sa.String(500), nullable=True),
        sa.Column("raw_version", sa.String(255), nullable=True),
        sa.Column("install_path", sa.Text(), nullable=True),
        sa.Column("binary_hash", sa.String(64), nullable=True),
        sa.Column("last_launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(50), server_default="automatic", nullable=False),
        sa.Column("catalog_software_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("software_catalog.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("software_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("match_confidence", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("is_verified_by_admin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_installed_comp", "installed_software", ["computer_id"])
    op.create_index("idx_installed_catalog", "installed_software", ["catalog_software_id"])
    op.create_index("idx_installed_last_launched", "installed_software", ["last_launched_at"])

    # 10. compliance_alerts
    op.create_table(
        "compliance_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("computer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("computers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("software_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("software_catalog.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("financial_risk_amount", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_compliance_alerts_status", "compliance_alerts", ["status"])

    # 11. import_history
    op.create_table(
        "import_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("computers_affected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("software_rows_imported", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matched_automatically", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(50), server_default="success", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("import_history")
    op.drop_table("compliance_alerts")
    op.drop_table("installed_software")
    op.drop_table("licenses")
    op.drop_table("software_catalog")
    op.drop_table("ru_software_registry")
    op.drop_table("software_classifiers")
    op.drop_table("software_categories")
    op.drop_table("computers")
    op.drop_table("employees")
    op.drop_table("users")

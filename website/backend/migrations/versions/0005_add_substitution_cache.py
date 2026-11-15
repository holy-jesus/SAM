"""Add substitution_cache table and catalog substitution fields

Revision ID: 0005_substitution_cache
Revises: 0004_fix_vuln_types
Create Date: 2026-11-15 07:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_substitution_cache"
down_revision = "0004_fix_vuln_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Таблица substitution_cache
    op.create_table(
        "substitution_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("software_name", sa.String(255), nullable=False),
        sa.Column("has_substitution", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("substitutions_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_domestic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(50), server_default="checked", nullable=False),
        sa.Column(
            "catalog_software_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("software_catalog.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("idx_sub_cache_software_name", "substitution_cache", ["software_name"], unique=True)
    op.create_index("idx_sub_cache_catalog_id", "substitution_cache", ["catalog_software_id"])
    op.create_index("idx_sub_cache_expires_at", "substitution_cache", ["expires_at"])

    # 2. Поля статуса импортозамещения в software_catalog
    with op.batch_alter_table("software_catalog") as batch_op:
        batch_op.add_column(sa.Column("has_substitution", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("substitutions_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    # 3. Приведение типа embedding к vector(1536) для pgvector (вместо double precision[])
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'ru_software_registry' AND column_name = 'embedding' AND data_type = 'ARRAY'
            ) THEN
                ALTER TABLE ru_software_registry 
                ALTER COLUMN embedding TYPE vector(1536) 
                USING CASE 
                    WHEN embedding IS NULL THEN NULL 
                    ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                END;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'software_catalog' AND column_name = 'embedding' AND data_type = 'ARRAY'
            ) THEN
                ALTER TABLE software_catalog 
                ALTER COLUMN embedding TYPE vector(1536) 
                USING CASE 
                    WHEN embedding IS NULL THEN NULL 
                    ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                END;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'process_signatures' AND column_name = 'embedding' AND data_type = 'ARRAY'
            ) THEN
                ALTER TABLE process_signatures 
                ALTER COLUMN embedding TYPE vector(1536) 
                USING CASE 
                    WHEN embedding IS NULL THEN NULL 
                    ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                END;
            END IF;
        END $$;
    """)

    # 4. Расширение полей ru_software_registry для предотвращения ошибки value too long
    # В выгрузках Минцифры vendor_inn содержит списки ИНН/ОГРН через разделители (до 73+ символов),
    # а vendor_name — консорциумы и группы правообладателей (до 573+ символов).
    with op.batch_alter_table("ru_software_registry") as batch_op:
        batch_op.alter_column("vendor_inn", existing_type=sa.String(20), type_=sa.Text(), existing_nullable=True)
        batch_op.alter_column("vendor_name", existing_type=sa.String(500), type_=sa.Text(), existing_nullable=True)
        batch_op.alter_column("name", existing_type=sa.String(500), type_=sa.Text(), existing_nullable=False)
        batch_op.alter_column("reg_number", existing_type=sa.String(50), type_=sa.String(100), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("software_catalog") as batch_op:
        batch_op.drop_column("substitutions_count")
        batch_op.drop_column("has_substitution")
    op.drop_table("substitution_cache")

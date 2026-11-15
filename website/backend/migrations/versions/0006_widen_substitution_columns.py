"""Widen import_substitutions and substitution_cache text columns

Revision ID: 0006_widen_substitutions
Revises: 0005_substitution_cache
Create Date: 2026-11-15 08:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0006_widen_substitutions"
down_revision = "0005_substitution_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Расширение колонок таблицы import_substitutions:
    # В выгрузках реестра класс ПО содержит длинные составные наименования (более 255 символов),
    # а также длинные списки правообладателей и несколько кодов классов.
    with op.batch_alter_table("import_substitutions") as batch_op:
        batch_op.alter_column("class_name", existing_type=sa.String(255), type_=sa.Text(), existing_nullable=True)
        batch_op.alter_column("class_code", existing_type=sa.String(50), type_=sa.Text(), existing_nullable=True)
        batch_op.alter_column("owner_name", existing_type=sa.String(500), type_=sa.Text(), existing_nullable=True)
        batch_op.alter_column("foreign_software_name", existing_type=sa.String(255), type_=sa.Text(), existing_nullable=False)
        batch_op.alter_column("russian_software_name", existing_type=sa.String(500), type_=sa.Text(), existing_nullable=False)
        batch_op.alter_column("russian_reg_number", existing_type=sa.String(50), type_=sa.String(100), existing_nullable=True)
        batch_op.alter_column("registration_date", existing_type=sa.String(50), type_=sa.String(100), existing_nullable=True)

    with op.batch_alter_table("substitution_cache") as batch_op:
        batch_op.alter_column("software_name", existing_type=sa.String(255), type_=sa.Text(), existing_nullable=False)


def downgrade() -> None:
    pass

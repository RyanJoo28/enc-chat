"""add message recall fields

Revision ID: 20260327_0006
Revises: 20260326_0005
Create Date: 2026-03-27 02:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260327_0006"
down_revision = "20260326_0005"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("messages_v2"):
        return

    if not _has_column(inspector, "messages_v2", "is_recalled"):
        op.add_column(
            "messages_v2",
            sa.Column("is_recalled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column(inspector, "messages_v2", "recalled_at"):
        op.add_column("messages_v2", sa.Column("recalled_at", sa.DateTime(), nullable=True))
    if not _has_column(inspector, "messages_v2", "recalled_by_user_id"):
        op.add_column("messages_v2", sa.Column("recalled_by_user_id", sa.Integer(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "messages_v2", "ix_messages_v2_is_recalled"):
        op.create_index("ix_messages_v2_is_recalled", "messages_v2", ["is_recalled"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("messages_v2"):
        return

    if _has_index(inspector, "messages_v2", "ix_messages_v2_is_recalled"):
        op.drop_index("ix_messages_v2_is_recalled", table_name="messages_v2")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "messages_v2", "recalled_by_user_id"):
        op.drop_column("messages_v2", "recalled_by_user_id")
    if _has_column(inspector, "messages_v2", "recalled_at"):
        op.drop_column("messages_v2", "recalled_at")
    if _has_column(inspector, "messages_v2", "is_recalled"):
        op.drop_column("messages_v2", "is_recalled")

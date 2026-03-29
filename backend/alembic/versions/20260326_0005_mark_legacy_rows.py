"""mark legacy message and attachment rows

Revision ID: 20260326_0005
Revises: 20260326_0004
Create Date: 2026-03-26 20:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0005"
down_revision = "20260326_0004"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("messages") and not _has_column(inspector, "messages", "protocol_version"):
        op.add_column(
            "messages",
            sa.Column("protocol_version", sa.String(length=32), nullable=False, server_default="legacy"),
        )

    if inspector.has_table("attachments") and not _has_column(inspector, "attachments", "protocol_version"):
        op.add_column(
            "attachments",
            sa.Column("protocol_version", sa.String(length=32), nullable=False, server_default="legacy"),
        )

    op.execute("UPDATE messages SET protocol_version = 'legacy' WHERE protocol_version IS NULL OR protocol_version = ''")
    op.execute("UPDATE attachments SET protocol_version = 'legacy' WHERE protocol_version IS NULL OR protocol_version = ''")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("attachments") and _has_column(inspector, "attachments", "protocol_version"):
        op.drop_column("attachments", "protocol_version")

    if inspector.has_table("messages") and _has_column(inspector, "messages", "protocol_version"):
        op.drop_column("messages", "protocol_version")

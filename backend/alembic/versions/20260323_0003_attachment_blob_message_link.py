"""link e2ee attachment blobs to messages

Revision ID: 20260323_0003
Revises: 20260323_0002
Create Date: 2026-03-23 12:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0003"
down_revision = "20260323_0002"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    blob_columns = _column_names("attachment_blobs_v2")
    if "message_id" not in blob_columns:
        op.add_column("attachment_blobs_v2", sa.Column("message_id", sa.Integer(), nullable=True))
        op.create_index("ix_attachment_blobs_v2_message_id", "attachment_blobs_v2", ["message_id"], unique=False)
        op.create_foreign_key(
            "fk_attachment_blobs_v2_message_id_messages_v2",
            "attachment_blobs_v2",
            "messages_v2",
            ["message_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    blob_columns = _column_names("attachment_blobs_v2")
    if "message_id" in blob_columns:
        op.drop_constraint("fk_attachment_blobs_v2_message_id_messages_v2", "attachment_blobs_v2", type_="foreignkey")
        op.drop_index("ix_attachment_blobs_v2_message_id", table_name="attachment_blobs_v2")
        op.drop_column("attachment_blobs_v2", "message_id")

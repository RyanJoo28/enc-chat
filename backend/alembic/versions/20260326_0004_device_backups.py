"""add encrypted device backups

Revision ID: 20260326_0004
Revises: 20260323_0003
Create Date: 2026-03-26 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0004"
down_revision = "20260323_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("device_backups"):
        return

    op.create_table(
        "device_backups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("backup_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_device_db_id", sa.Integer(), nullable=True),
        sa.Column("source_device_public_id", sa.String(length=64), nullable=False),
        sa.Column("source_device_name", sa.String(length=255), nullable=True),
        sa.Column("source_platform", sa.String(length=64), nullable=True),
        sa.Column("backup_version", sa.String(length=32), nullable=False, server_default="device_backup_v1"),
        sa.Column("encryption_metadata", sa.Text(), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("ciphertext_size", sa.Integer(), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'complete', 'deleted')", name="ck_device_backups_status"),
        sa.ForeignKeyConstraint(["source_device_db_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("backup_id", name="uq_device_backups_backup_id"),
    )
    op.create_index("ix_device_backups_id", "device_backups", ["id"], unique=False)
    op.create_index("ix_device_backups_backup_id", "device_backups", ["backup_id"], unique=False)
    op.create_index("ix_device_backups_user_id", "device_backups", ["user_id"], unique=False)
    op.create_index("ix_device_backups_source_device_db_id", "device_backups", ["source_device_db_id"], unique=False)
    op.create_index("ix_device_backups_source_device_public_id", "device_backups", ["source_device_public_id"], unique=False)
    op.create_index("ix_device_backups_status", "device_backups", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("device_backups"):
        return

    op.drop_index("ix_device_backups_status", table_name="device_backups")
    op.drop_index("ix_device_backups_source_device_public_id", table_name="device_backups")
    op.drop_index("ix_device_backups_source_device_db_id", table_name="device_backups")
    op.drop_index("ix_device_backups_user_id", table_name="device_backups")
    op.drop_index("ix_device_backups_backup_id", table_name="device_backups")
    op.drop_index("ix_device_backups_id", table_name="device_backups")
    op.drop_table("device_backups")

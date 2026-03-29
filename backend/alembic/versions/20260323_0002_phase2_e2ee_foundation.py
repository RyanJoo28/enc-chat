"""phase 2 e2ee foundation tables

Revision ID: 20260323_0002
Revises: 20260323_0001
Create Date: 2026-03-23 00:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0002"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _drop_indexes_for_exact_columns(table_name: str, column_names: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    target_columns = list(column_names)
    seen_names = set()

    for index in inspector.get_indexes(table_name):
        index_name = index.get("name")
        if not index_name or index_name in seen_names:
            continue
        if list(index.get("column_names") or []) == target_columns:
            op.execute(sa.text(f"ALTER TABLE `{table_name}` DROP INDEX `{index_name}`"))
            seen_names.add(index_name)

    for constraint in inspector.get_unique_constraints(table_name):
        constraint_name = constraint.get("name")
        if not constraint_name or constraint_name in seen_names:
            continue
        if list(constraint.get("column_names") or []) == target_columns:
            op.execute(sa.text(f"ALTER TABLE `{table_name}` DROP INDEX `{constraint_name}`"))
            seen_names.add(constraint_name)


def _create_devices_table() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("identity_key_curve", sa.String(length=32), nullable=False, server_default="X25519"),
        sa.Column("identity_key_public", sa.Text(), nullable=False),
        sa.Column("signing_key_curve", sa.String(length=32), nullable=False, server_default="Ed25519"),
        sa.Column("signing_key_public", sa.Text(), nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", name="uq_devices_device_id"),
        sa.UniqueConstraint("user_id", "device_id", name="uq_devices_user_public_device"),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"], unique=False)
    op.create_index("ix_devices_id", "devices", ["id"], unique=False)
    op.create_index("ix_devices_is_active", "devices", ["is_active"], unique=False)
    op.create_index("ix_devices_user_id", "devices", ["user_id"], unique=False)


def _create_device_signed_prekeys_table() -> None:
    op.create_table(
        "device_signed_prekeys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.Integer(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("published_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "key_id", name="uq_device_signed_prekeys_device_key"),
    )
    op.create_index("ix_device_signed_prekeys_device_id", "device_signed_prekeys", ["device_id"], unique=False)
    op.create_index("ix_device_signed_prekeys_id", "device_signed_prekeys", ["id"], unique=False)
    op.create_index("ix_device_signed_prekeys_is_active", "device_signed_prekeys", ["is_active"], unique=False)


def _create_device_one_time_prekeys_table() -> None:
    op.create_table(
        "device_one_time_prekeys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.Integer(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("is_consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "key_id", name="uq_device_one_time_prekeys_device_key"),
    )
    op.create_index("ix_device_one_time_prekeys_device_id", "device_one_time_prekeys", ["device_id"], unique=False)
    op.create_index("ix_device_one_time_prekeys_id", "device_one_time_prekeys", ["id"], unique=False)
    op.create_index("ix_device_one_time_prekeys_is_consumed", "device_one_time_prekeys", ["is_consumed"], unique=False)


def _create_conversations_v2_table() -> None:
    op.create_table(
        "conversations_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_key", sa.String(length=128), nullable=False),
        sa.Column("conversation_type", sa.String(length=20), nullable=False),
        sa.Column("pair_user_low_id", sa.Integer(), nullable=True),
        sa.Column("pair_user_high_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(conversation_type = 'private' AND pair_user_low_id IS NOT NULL AND pair_user_high_id IS NOT NULL "
            "AND pair_user_low_id < pair_user_high_id AND group_id IS NULL) OR "
            "(conversation_type = 'group' AND group_id IS NOT NULL AND pair_user_low_id IS NULL AND pair_user_high_id IS NULL)",
            name="ck_conversations_v2_scope",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pair_user_high_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pair_user_low_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_key", name="uq_conversations_v2_key"),
        sa.UniqueConstraint("group_id", name="uq_conversations_v2_group"),
    )
    op.create_index("ix_conversations_v2_conversation_key", "conversations_v2", ["conversation_key"], unique=False)
    op.create_index("ix_conversations_v2_conversation_type", "conversations_v2", ["conversation_type"], unique=False)
    op.create_index("ix_conversations_v2_group_id", "conversations_v2", ["group_id"], unique=False)
    op.create_index("ix_conversations_v2_id", "conversations_v2", ["id"], unique=False)
    op.create_index("ix_conversations_v2_pair_user_high_id", "conversations_v2", ["pair_user_high_id"], unique=False)
    op.create_index("ix_conversations_v2_pair_user_low_id", "conversations_v2", ["pair_user_low_id"], unique=False)


def _create_messages_v2_table() -> None:
    op.create_table(
        "messages_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=False),
        sa.Column("sender_device_id", sa.Integer(), nullable=True),
        sa.Column("client_message_id", sa.String(length=128), nullable=True),
        sa.Column("protocol_version", sa.String(length=32), nullable=False, server_default="e2ee_v1"),
        sa.Column("message_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sender_device_id", "client_message_id", name="uq_messages_v2_sender_client_message"),
    )
    op.create_index("ix_messages_v2_conversation_id", "messages_v2", ["conversation_id"], unique=False)
    op.create_index("ix_messages_v2_created_at", "messages_v2", ["created_at"], unique=False)
    op.create_index("ix_messages_v2_id", "messages_v2", ["id"], unique=False)
    op.create_index("ix_messages_v2_sender_device_id", "messages_v2", ["sender_device_id"], unique=False)
    op.create_index("ix_messages_v2_sender_user_id", "messages_v2", ["sender_user_id"], unique=False)


def _create_message_payloads_table() -> None:
    op.create_table(
        "message_payloads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_device_id", sa.Integer(), nullable=False),
        sa.Column("envelope_type", sa.String(length=32), nullable=False, server_default="signal"),
        sa.Column("protocol_version", sa.String(length=32), nullable=False, server_default="e2ee_v1"),
        sa.Column("envelope", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["message_id"], ["messages_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "recipient_device_id", name="uq_message_payloads_message_device"),
    )
    op.create_index("ix_message_payloads_id", "message_payloads", ["id"], unique=False)
    op.create_index("ix_message_payloads_message_id", "message_payloads", ["message_id"], unique=False)
    op.create_index("ix_message_payloads_recipient_device_id", "message_payloads", ["recipient_device_id"], unique=False)
    op.create_index("ix_message_payloads_recipient_user_id", "message_payloads", ["recipient_user_id"], unique=False)


def _create_message_deliveries_table() -> None:
    op.create_table(
        "message_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_device_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('pending', 'delivered', 'read', 'failed')", name="ck_message_deliveries_status"),
        sa.ForeignKeyConstraint(["message_id"], ["messages_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "recipient_device_id", name="uq_message_deliveries_message_device"),
    )
    op.create_index("ix_message_deliveries_id", "message_deliveries", ["id"], unique=False)
    op.create_index("ix_message_deliveries_message_id", "message_deliveries", ["message_id"], unique=False)
    op.create_index("ix_message_deliveries_recipient_device_id", "message_deliveries", ["recipient_device_id"], unique=False)
    op.create_index("ix_message_deliveries_recipient_user_id", "message_deliveries", ["recipient_user_id"], unique=False)
    op.create_index("ix_message_deliveries_status", "message_deliveries", ["status"], unique=False)


def _create_attachment_blobs_v2_table() -> None:
    op.create_table(
        "attachment_blobs_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("blob_id", sa.String(length=36), nullable=False),
        sa.Column("uploader_user_id", sa.Integer(), nullable=False),
        sa.Column("uploader_device_id", sa.Integer(), nullable=True),
        sa.Column("storage_backend", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("ciphertext_size", sa.Integer(), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("upload_expires_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('pending', 'complete', 'aborted', 'expired')", name="ck_attachment_blobs_v2_status"),
        sa.ForeignKeyConstraint(["uploader_device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blob_id", name="uq_attachment_blobs_v2_blob_id"),
    )
    op.create_index("ix_attachment_blobs_v2_blob_id", "attachment_blobs_v2", ["blob_id"], unique=False)
    op.create_index("ix_attachment_blobs_v2_id", "attachment_blobs_v2", ["id"], unique=False)
    op.create_index("ix_attachment_blobs_v2_status", "attachment_blobs_v2", ["status"], unique=False)
    op.create_index("ix_attachment_blobs_v2_uploader_device_id", "attachment_blobs_v2", ["uploader_device_id"], unique=False)
    op.create_index("ix_attachment_blobs_v2_uploader_user_id", "attachment_blobs_v2", ["uploader_user_id"], unique=False)


def _create_group_sender_key_epochs_table() -> None:
    op.create_table(
        "group_sender_key_epochs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("rotated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("distribution_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_group_sender_key_epochs_status"),
        sa.ForeignKeyConstraint(["distribution_message_id"], ["messages_v2.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rotated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "epoch", name="uq_group_sender_key_epochs_group_epoch"),
    )
    op.create_index("ix_group_sender_key_epochs_group_id", "group_sender_key_epochs", ["group_id"], unique=False)
    op.create_index("ix_group_sender_key_epochs_id", "group_sender_key_epochs", ["id"], unique=False)
    op.create_index("ix_group_sender_key_epochs_status", "group_sender_key_epochs", ["status"], unique=False)


def _create_auth_sessions_table() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("session_family_id", sa.String(length=36), nullable=False),
        sa.Column("user_session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("rotated_from_session_id", sa.Integer(), nullable=True),
        sa.Column("replaced_by_session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('active', 'rotated', 'revoked', 'expired')", name="ck_auth_sessions_status"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["replaced_by_session_id"], ["auth_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rotated_from_session_id"], ["auth_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"),
        sa.UniqueConstraint("session_id", name="uq_auth_sessions_session_id"),
    )
    op.create_index("ix_auth_sessions_device_id", "auth_sessions", ["device_id"], unique=False)
    op.create_index("ix_auth_sessions_id", "auth_sessions", ["id"], unique=False)
    op.create_index("ix_auth_sessions_refresh_token_hash", "auth_sessions", ["refresh_token_hash"], unique=False)
    op.create_index("ix_auth_sessions_session_family_id", "auth_sessions", ["session_family_id"], unique=False)
    op.create_index("ix_auth_sessions_session_id", "auth_sessions", ["session_id"], unique=False)
    op.create_index("ix_auth_sessions_status", "auth_sessions", ["status"], unique=False)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)


def upgrade() -> None:
    user_columns = _column_names("users")
    if "avatar" not in user_columns:
        op.add_column("users", sa.Column("avatar", sa.String(length=512), nullable=True))
    _drop_indexes_for_exact_columns("users", ["username"])
    op.alter_column("users", "username", existing_type=sa.String(length=255), type_=sa.String(length=1024), existing_nullable=False)
    op.alter_column("users", "avatar", existing_type=sa.String(length=512), type_=sa.String(length=2048), existing_nullable=True)
    if "username_hash" not in user_columns:
        op.add_column("users", sa.Column("username_hash", sa.String(length=64), nullable=True))
        op.create_unique_constraint("uq_users_username_hash", "users", ["username_hash"])
    if "session_version" not in user_columns:
        op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
        op.alter_column("users", "session_version", server_default=None)
    if "e2ee_enabled" not in user_columns:
        op.add_column("users", sa.Column("e2ee_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("users", "e2ee_enabled", server_default=None)

    group_columns = _column_names("groups")
    if "avatar" not in group_columns:
        op.add_column("groups", sa.Column("avatar", sa.String(length=512), nullable=True))
    op.alter_column("groups", "name", existing_type=sa.String(length=255), type_=sa.String(length=1024), existing_nullable=False)
    op.alter_column("groups", "avatar", existing_type=sa.String(length=512), type_=sa.String(length=2048), existing_nullable=True)

    attachment_columns = _column_names("attachments")
    _drop_indexes_for_exact_columns("attachments", ["stored_filename"])
    op.alter_column(
        "attachments",
        "stored_filename",
        existing_type=sa.String(length=512),
        type_=sa.String(length=1024),
        existing_nullable=False,
    )
    op.alter_column(
        "attachments",
        "original_name",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=2048),
        existing_nullable=False,
    )
    if "stored_filename_hash" not in attachment_columns:
        op.add_column("attachments", sa.Column("stored_filename_hash", sa.String(length=64), nullable=True))
        op.create_unique_constraint("uq_attachments_stored_filename_hash", "attachments", ["stored_filename_hash"])

    existing_tables = _table_names()
    if "devices" not in existing_tables:
        _create_devices_table()
    if "device_signed_prekeys" not in existing_tables:
        _create_device_signed_prekeys_table()
    if "device_one_time_prekeys" not in existing_tables:
        _create_device_one_time_prekeys_table()
    if "conversations_v2" not in existing_tables:
        _create_conversations_v2_table()
    if "messages_v2" not in existing_tables:
        _create_messages_v2_table()
    if "message_payloads" not in existing_tables:
        _create_message_payloads_table()
    if "message_deliveries" not in existing_tables:
        _create_message_deliveries_table()
    if "attachment_blobs_v2" not in existing_tables:
        _create_attachment_blobs_v2_table()
    if "group_sender_key_epochs" not in existing_tables:
        _create_group_sender_key_epochs_table()
    if "auth_sessions" not in existing_tables:
        _create_auth_sessions_table()


def downgrade() -> None:
    existing_tables = _table_names()

    if "auth_sessions" in existing_tables:
        op.drop_table("auth_sessions")
    if "group_sender_key_epochs" in existing_tables:
        op.drop_table("group_sender_key_epochs")
    if "attachment_blobs_v2" in existing_tables:
        op.drop_table("attachment_blobs_v2")
    if "message_deliveries" in existing_tables:
        op.drop_table("message_deliveries")
    if "message_payloads" in existing_tables:
        op.drop_table("message_payloads")
    if "messages_v2" in existing_tables:
        op.drop_table("messages_v2")
    if "conversations_v2" in existing_tables:
        op.drop_table("conversations_v2")
    if "device_one_time_prekeys" in existing_tables:
        op.drop_table("device_one_time_prekeys")
    if "device_signed_prekeys" in existing_tables:
        op.drop_table("device_signed_prekeys")
    if "devices" in existing_tables:
        op.drop_table("devices")

    if "users" in _table_names():
        op.alter_column("attachments", "original_name", existing_type=sa.String(length=2048), type_=sa.String(length=1024), existing_nullable=False)
        op.alter_column("attachments", "stored_filename", existing_type=sa.String(length=1024), type_=sa.String(length=512), existing_nullable=False)
        op.alter_column("groups", "avatar", existing_type=sa.String(length=2048), type_=sa.String(length=512), existing_nullable=True)
        op.alter_column("groups", "name", existing_type=sa.String(length=1024), type_=sa.String(length=255), existing_nullable=False)
        op.alter_column("users", "avatar", existing_type=sa.String(length=2048), type_=sa.String(length=512), existing_nullable=True)
        op.alter_column("users", "username", existing_type=sa.String(length=1024), type_=sa.String(length=255), existing_nullable=False)
        user_columns = _column_names("users")
        if "e2ee_enabled" in user_columns:
            op.drop_column("users", "e2ee_enabled")
        if "session_version" in user_columns:
            op.drop_column("users", "session_version")

"""legacy schema baseline

Revision ID: 20260323_0001
Revises:
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_users_table() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("username_hash", sa.String(length=64), nullable=True),
        sa.Column("password", sa.String(length=100), nullable=False),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username_hash", name="uq_users_username_hash"),
    )


def _create_groups_table() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_group_members_table() -> None:
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_member_pair"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"], unique=False)
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"], unique=False)


def _create_messages_table() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("msg_type", sa.String(length=10), nullable=True, server_default="text"),
        sa.Column("content", sa.String(length=5000), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_group_id", "messages", ["group_id"], unique=False)
    op.create_index("ix_messages_receiver_id", "messages", ["receiver_id"], unique=False)
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"], unique=False)


def _create_attachments_table() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stored_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_filename_hash", sa.String(length=64), nullable=True),
        sa.Column("original_name", sa.String(length=1024), nullable=False),
        sa.Column("msg_type", sa.String(length=10), nullable=False),
        sa.Column("uploader_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "(message_id IS NULL AND receiver_id IS NULL AND group_id IS NULL) OR "
            "(message_id IS NOT NULL AND ((receiver_id IS NOT NULL AND group_id IS NULL) OR "
            "(receiver_id IS NULL AND group_id IS NOT NULL)))",
            name="ck_attachment_binding_scope",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_attachments_message_id"),
        sa.UniqueConstraint("stored_filename_hash", name="uq_attachments_stored_filename_hash"),
    )
    op.create_index("ix_attachments_group_id", "attachments", ["group_id"], unique=False)
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"], unique=False)
    op.create_index("ix_attachments_receiver_id", "attachments", ["receiver_id"], unique=False)
    op.create_index("ix_attachments_stored_filename_hash", "attachments", ["stored_filename_hash"], unique=False)
    op.create_index("ix_attachments_uploader_id", "attachments", ["uploader_id"], unique=False)


def _create_user_search_tokens_table() -> None:
    op.create_table(
        "user_search_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "token_hash", name="uq_user_search_token_pair"),
    )
    op.create_index("ix_user_search_tokens_token_hash", "user_search_tokens", ["token_hash"], unique=False)
    op.create_index("ix_user_search_tokens_user_id", "user_search_tokens", ["user_id"], unique=False)


def _create_group_search_tokens_table() -> None:
    op.create_table(
        "group_search_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "token_hash", name="uq_group_search_token_pair"),
    )
    op.create_index("ix_group_search_tokens_group_id", "group_search_tokens", ["group_id"], unique=False)
    op.create_index("ix_group_search_tokens_token_hash", "group_search_tokens", ["token_hash"], unique=False)


def _create_friend_requests_table() -> None:
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("pair_key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("sender_id <> receiver_id", name="ck_friend_request_not_self"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_friend_request_status",
        ),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair_key", "status", name="uq_friend_request_pair_state"),
    )
    op.create_index("ix_friend_requests_pair_key", "friend_requests", ["pair_key"], unique=False)
    op.create_index("ix_friend_requests_receiver_id", "friend_requests", ["receiver_id"], unique=False)
    op.create_index("ix_friend_requests_sender_id", "friend_requests", ["sender_id"], unique=False)
    op.create_index("ix_friend_requests_status", "friend_requests", ["status"], unique=False)


def _create_friendships_table() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_one_id", sa.Integer(), nullable=False),
        sa.Column("user_two_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("user_one_id < user_two_id", name="ck_friendship_order"),
        sa.ForeignKeyConstraint(["user_one_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_two_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_one_id", "user_two_id", name="uq_friendship_pair"),
    )
    op.create_index("ix_friendships_user_one_id", "friendships", ["user_one_id"], unique=False)
    op.create_index("ix_friendships_user_two_id", "friendships", ["user_two_id"], unique=False)


def _create_private_chat_access_table() -> None:
    op.create_table(
        "private_chat_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_one_id", sa.Integer(), nullable=False),
        sa.Column("user_two_id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("user_one_id < user_two_id", name="ck_private_chat_access_order"),
        sa.ForeignKeyConstraint(["user_one_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_two_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_one_id", "user_two_id", name="uq_private_chat_access_pair"),
    )
    op.create_index("ix_private_chat_access_user_one_id", "private_chat_access", ["user_one_id"], unique=False)
    op.create_index("ix_private_chat_access_user_two_id", "private_chat_access", ["user_two_id"], unique=False)


def _create_group_invites_table() -> None:
    op.create_table(
        "group_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("inviter_id", sa.Integer(), nullable=False),
        sa.Column("invitee_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("inviter_id <> invitee_id", name="ck_group_invite_not_self"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled', 'expired')",
            name="ck_group_invite_status",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "invitee_id", "status", name="uq_group_invite_state"),
    )
    op.create_index("ix_group_invites_group_id", "group_invites", ["group_id"], unique=False)
    op.create_index("ix_group_invites_invitee_id", "group_invites", ["invitee_id"], unique=False)
    op.create_index("ix_group_invites_inviter_id", "group_invites", ["inviter_id"], unique=False)
    op.create_index("ix_group_invites_status", "group_invites", ["status"], unique=False)


def _create_group_join_requests_table() -> None:
    op.create_table(
        "group_join_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_group_join_request_status",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "requester_id", "status", name="uq_group_join_request_state"),
    )
    op.create_index("ix_group_join_requests_group_id", "group_join_requests", ["group_id"], unique=False)
    op.create_index("ix_group_join_requests_requester_id", "group_join_requests", ["requester_id"], unique=False)
    op.create_index("ix_group_join_requests_status", "group_join_requests", ["status"], unique=False)


def _create_token_blacklist_table() -> None:
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("blacklisted_on", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_token_blacklist_token"),
    )
    op.create_index("ix_token_blacklist_token", "token_blacklist", ["token"], unique=False)


def upgrade() -> None:
    existing_tables = _table_names()

    if "users" not in existing_tables:
        _create_users_table()
    if "groups" not in existing_tables:
        _create_groups_table()
    if "group_members" not in existing_tables:
        _create_group_members_table()
    if "messages" not in existing_tables:
        _create_messages_table()
    if "attachments" not in existing_tables:
        _create_attachments_table()
    if "user_search_tokens" not in existing_tables:
        _create_user_search_tokens_table()
    if "group_search_tokens" not in existing_tables:
        _create_group_search_tokens_table()
    if "friend_requests" not in existing_tables:
        _create_friend_requests_table()
    if "friendships" not in existing_tables:
        _create_friendships_table()
    if "private_chat_access" not in existing_tables:
        _create_private_chat_access_table()
    if "group_invites" not in existing_tables:
        _create_group_invites_table()
    if "group_join_requests" not in existing_tables:
        _create_group_join_requests_table()
    if "token_blacklist" not in existing_tables:
        _create_token_blacklist_table()


def downgrade() -> None:
    existing_tables = _table_names()

    if "token_blacklist" in existing_tables:
        op.drop_table("token_blacklist")
    if "group_join_requests" in existing_tables:
        op.drop_table("group_join_requests")
    if "group_invites" in existing_tables:
        op.drop_table("group_invites")
    if "private_chat_access" in existing_tables:
        op.drop_table("private_chat_access")
    if "friendships" in existing_tables:
        op.drop_table("friendships")
    if "friend_requests" in existing_tables:
        op.drop_table("friend_requests")
    if "group_search_tokens" in existing_tables:
        op.drop_table("group_search_tokens")
    if "user_search_tokens" in existing_tables:
        op.drop_table("user_search_tokens")
    if "attachments" in existing_tables:
        op.drop_table("attachments")
    if "messages" in existing_tables:
        op.drop_table("messages")
    if "group_members" in existing_tables:
        op.drop_table("group_members")
    if "groups" in existing_tables:
        op.drop_table("groups")
    if "users" in existing_tables:
        op.drop_table("users")

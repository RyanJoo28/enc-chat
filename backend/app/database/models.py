from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _encryption_module():
    from ..utils import encryption

    return encryption


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    _username = Column("username", String(1024), nullable=False)
    username_hash = Column(String(64), unique=True, nullable=True, index=True)
    _password = Column("password", String(512), nullable=False)
    _avatar = Column("avatar", String(2048), nullable=True)
    session_version = Column(Integer, nullable=False, default=0)
    e2ee_enabled = Column(Boolean, nullable=False, default=False)

    @property
    def username(self) -> str:
        encryption = _encryption_module()
        return encryption.db_decrypt(self._username)

    @username.setter
    def username(self, value: str):
        encryption = _encryption_module()
        self._username = encryption.db_encrypt(value)
        self.username_hash = encryption.metadata_hash(value, case_insensitive=True, namespace="user.username")

    @property
    def password(self) -> str:
        encryption = _encryption_module()
        return encryption.db_decrypt(self._password)

    @password.setter
    def password(self, value: str):
        encryption = _encryption_module()
        self._password = encryption.db_encrypt(value)

    @property
    def avatar(self) -> str | None:
        if self._avatar is None:
            return None
        encryption = _encryption_module()
        return encryption.db_decrypt(self._avatar)

    @avatar.setter
    def avatar(self, value: str | None):
        encryption = _encryption_module()
        self._avatar = encryption.db_encrypt(value) if value else None


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    _name = Column("name", String(1024), nullable=False)
    _avatar = Column("avatar", String(2048), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    @property
    def name(self) -> str:
        encryption = _encryption_module()
        return encryption.db_decrypt(self._name)

    @name.setter
    def name(self, value: str):
        encryption = _encryption_module()
        self._name = encryption.db_encrypt(value)

    @property
    def avatar(self) -> str | None:
        if self._avatar is None:
            return None
        encryption = _encryption_module()
        return encryption.db_decrypt(self._avatar)

    @avatar.setter
    def avatar(self, value: str | None):
        encryption = _encryption_module()
        self._avatar = encryption.db_encrypt(value) if value else None


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.now)


class UserSearchToken(Base):
    __tablename__ = "user_search_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "token_hash", name="uq_user_search_token_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)


class GroupSearchToken(Base):
    __tablename__ = "group_search_tokens"
    __table_args__ = (
        UniqueConstraint("group_id", "token_hash", name="uq_group_search_token_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    __table_args__ = (
        CheckConstraint("sender_id <> receiver_id", name="ck_friend_request_not_self"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_friend_request_status"
        ),
        UniqueConstraint("pair_key", "status", name="uq_friend_request_pair_state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pair_key = Column(String(32), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=datetime.now)
    responded_at = Column(DateTime, nullable=True)


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user_one_id < user_two_id", name="ck_friendship_order"),
        UniqueConstraint("user_one_id", "user_two_id", name="uq_friendship_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_one_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_two_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)


class PrivateChatAccess(Base):
    __tablename__ = "private_chat_access"
    __table_args__ = (
        CheckConstraint("user_one_id < user_two_id", name="ck_private_chat_access_order"),
        UniqueConstraint("user_one_id", "user_two_id", name="uq_private_chat_access_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_one_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_two_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GroupInvite(Base):
    __tablename__ = "group_invites"
    __table_args__ = (
        CheckConstraint("inviter_id <> invitee_id", name="ck_group_invite_not_self"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled', 'expired')",
            name="ck_group_invite_status"
        ),
        UniqueConstraint("group_id", "invitee_id", "status", name="uq_group_invite_state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    inviter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invitee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=datetime.now)
    responded_at = Column(DateTime, nullable=True)


class GroupJoinRequest(Base):
    __tablename__ = "group_join_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_group_join_request_status"
        ),
        UniqueConstraint("group_id", "requester_id", "status", name="uq_group_join_request_state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    _note = Column("note", String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    responded_at = Column(DateTime, nullable=True)

    @property
    def note(self) -> str | None:
        if self._note is None:
            return None
        encryption = _encryption_module()
        return encryption.db_decrypt(self._note)

    @note.setter
    def note(self, value: str | None):
        if value is None:
            self._note = None
        else:
            encryption = _encryption_module()
            self._note = encryption.db_encrypt(value)


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    blacklisted_on = Column(DateTime, default=datetime.now)


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("device_id", name="uq_devices_device_id"),
        UniqueConstraint("user_id", "device_id", name="uq_devices_user_public_device"),
    )

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(36), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String(255), nullable=False)
    platform = Column(String(64), nullable=True)
    identity_key_curve = Column(String(32), nullable=False, default="X25519")
    identity_key_public = Column(Text, nullable=False)
    signing_key_curve = Column(String(32), nullable=False, default="Ed25519")
    signing_key_public = Column(Text, nullable=False)
    registration_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DeviceSignedPrekey(Base):
    __tablename__ = "device_signed_prekeys"
    __table_args__ = (
        UniqueConstraint("device_id", "key_id", name="uq_device_signed_prekeys_device_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    key_id = Column(Integer, nullable=False)
    public_key = Column(Text, nullable=False)
    signature = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    published_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True)
    replaced_at = Column(DateTime, nullable=True)


class DeviceOneTimePrekey(Base):
    __tablename__ = "device_one_time_prekeys"
    __table_args__ = (
        UniqueConstraint("device_id", "key_id", name="uq_device_one_time_prekeys_device_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    key_id = Column(Integer, nullable=False)
    public_key = Column(Text, nullable=False)
    is_consumed = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime, default=datetime.now)
    consumed_at = Column(DateTime, nullable=True)


class ConversationV2(Base):
    __tablename__ = "conversations_v2"
    __table_args__ = (
        CheckConstraint(
            "(conversation_type = 'private' AND pair_user_low_id IS NOT NULL AND pair_user_high_id IS NOT NULL "
            "AND pair_user_low_id < pair_user_high_id AND group_id IS NULL) OR "
            "(conversation_type = 'group' AND group_id IS NOT NULL AND pair_user_low_id IS NULL AND pair_user_high_id IS NULL)",
            name="ck_conversations_v2_scope"
        ),
        UniqueConstraint("conversation_key", name="uq_conversations_v2_key"),
        UniqueConstraint("group_id", name="uq_conversations_v2_group"),
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_key = Column(String(128), nullable=False, index=True)
    conversation_type = Column(String(20), nullable=False, index=True)
    pair_user_low_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    pair_user_high_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    last_message_at = Column(DateTime, nullable=True)


class MessageV2(Base):
    __tablename__ = "messages_v2"
    __table_args__ = (
        UniqueConstraint("sender_device_id", "client_message_id", name="uq_messages_v2_sender_client_message"),
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_device_id = Column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    client_message_id = Column(String(128), nullable=True)
    protocol_version = Column(String(32), nullable=False, default="e2ee_v1")
    message_type = Column(String(32), nullable=False, default="text")
    has_attachments = Column(Boolean, nullable=False, default=False)
    is_recalled = Column(Boolean, nullable=False, default=False, index=True)
    recalled_at = Column(DateTime, nullable=True)
    recalled_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)


class MessagePayload(Base):
    __tablename__ = "message_payloads"
    __table_args__ = (
        UniqueConstraint("message_id", "recipient_device_id", name="uq_message_payloads_message_device"),
    )

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    envelope_type = Column(String(32), nullable=False, default="signal")
    protocol_version = Column(String(32), nullable=False, default="e2ee_v1")
    _envelope = Column("envelope", Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    @property
    def envelope(self) -> str:
        encryption = _encryption_module()
        return encryption.db_decrypt(self._envelope)

    @envelope.setter
    def envelope(self, value: str):
        encryption = _encryption_module()
        self._envelope = encryption.db_encrypt(value)


class MessageDelivery(Base):
    __tablename__ = "message_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered', 'read', 'failed')",
            name="ck_message_deliveries_status"
        ),
        UniqueConstraint("message_id", "recipient_device_id", name="uq_message_deliveries_message_device"),
    )

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    last_error = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AttachmentBlobV2(Base):
    __tablename__ = "attachment_blobs_v2"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'complete', 'aborted', 'expired')",
            name="ck_attachment_blobs_v2_status"
        ),
        UniqueConstraint("blob_id", name="uq_attachment_blobs_v2_blob_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    blob_id = Column(String(36), nullable=False, index=True)
    uploader_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    uploader_device_id = Column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    message_id = Column(Integer, ForeignKey("messages_v2.id", ondelete="SET NULL"), nullable=True, index=True)
    storage_backend = Column(String(32), nullable=False, default="local")
    storage_path = Column(String(1024), nullable=False)
    mime_type = Column(String(255), nullable=False)
    ciphertext_size = Column(Integer, nullable=False)
    ciphertext_sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    upload_expires_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class GroupSenderKeyEpoch(Base):
    __tablename__ = "group_sender_key_epochs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'retired')",
            name="ck_group_sender_key_epochs_status"
        ),
        UniqueConstraint("group_id", "epoch", name="uq_group_sender_key_epochs_group_epoch"),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    epoch = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="active", index=True)
    rotated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    distribution_message_id = Column(Integer, ForeignKey("messages_v2.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    retired_at = Column(DateTime, nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'rotated', 'revoked', 'expired')",
            name="ck_auth_sessions_status"
        ),
        UniqueConstraint("session_id", name="uq_auth_sessions_session_id"),
        UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    refresh_token_hash = Column(String(128), nullable=False, index=True)
    session_family_id = Column(String(36), nullable=False, index=True)
    user_session_version = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active", index=True)
    user_agent = Column(String(512), nullable=True)
    _ip_address = Column("ip_address", String(200), nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    rotated_from_session_id = Column(Integer, ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True)
    replaced_by_session_id = Column(Integer, ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    @property
    def ip_address(self) -> str | None:
        if self._ip_address is None:
            return None
        encryption = _encryption_module()
        return encryption.db_decrypt(self._ip_address)

    @ip_address.setter
    def ip_address(self, value: str | None):
        if value is None:
            self._ip_address = None
        else:
            encryption = _encryption_module()
            self._ip_address = encryption.db_encrypt(value)


ACTIVE_BOOTSTRAP_TABLES = [
    User.__table__,
    Group.__table__,
    GroupMember.__table__,
    UserSearchToken.__table__,
    GroupSearchToken.__table__,
    FriendRequest.__table__,
    Friendship.__table__,
    PrivateChatAccess.__table__,
    GroupInvite.__table__,
    GroupJoinRequest.__table__,
    TokenBlacklist.__table__,
    Device.__table__,
    DeviceSignedPrekey.__table__,
    DeviceOneTimePrekey.__table__,
    ConversationV2.__table__,
    MessageV2.__table__,
    MessagePayload.__table__,
    MessageDelivery.__table__,
    AttachmentBlobV2.__table__,
    GroupSenderKeyEpoch.__table__,
    AuthSession.__table__,
]

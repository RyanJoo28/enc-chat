from typing import Optional

from pydantic import BaseModel, Field


class SignedPrekeyInput(BaseModel):
    key_id: int = Field(..., ge=1)
    public_key: str = Field(..., min_length=1)
    signature: str = Field(..., min_length=1)


class OneTimePrekeyInput(BaseModel):
    key_id: int = Field(..., ge=1)
    public_key: str = Field(..., min_length=1)


class DeviceBootstrapRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    device_name: str = Field(..., min_length=1, max_length=255)
    platform: Optional[str] = Field(default=None, max_length=64)
    identity_key_public: str = Field(..., min_length=1)
    signing_key_public: str = Field(..., min_length=1)
    registration_id: Optional[int] = Field(default=None, ge=1)
    signed_prekey: SignedPrekeyInput
    one_time_prekeys: list[OneTimePrekeyInput] = Field(default_factory=list)


class DevicePrekeyRefreshRequest(BaseModel):
    signed_prekey: Optional[SignedPrekeyInput] = None
    one_time_prekeys: list[OneTimePrekeyInput] = Field(default_factory=list)


class AttachmentInitRequest(BaseModel):
    mime_type: str = Field(..., min_length=1, max_length=255)
    ciphertext_size: int = Field(..., ge=1)
    ciphertext_sha256: str = Field(..., min_length=64, max_length=64)


class AttachmentCompleteRequest(BaseModel):
    ciphertext_sha256: str = Field(..., min_length=64, max_length=64)

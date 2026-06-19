"""Pydantic models for MAX Bot API and Hermes data structures."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── MAX Bot API Models ───────────────────────────────────────────────────────


class UpdateType(str, Enum):
    """MAX API update types."""
    MESSAGE_CREATED = "message_created"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_REMOVED = "message_removed"
    MESSAGE_CALLBACK = "message_callback"
    BOT_ADDED = "bot_added"
    BOT_REMOVED = "bot_removed"
    BOT_STARTED = "bot_started"
    CHAT_CREATED = "chat_created"


class MAXUser(BaseModel):
    """User info from MAX API."""
    user_id: int
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    username: Optional[str] = None
    is_bot: bool = False
    last_activity_time: Optional[int] = None

    class Config:
        extra = "allow"


class MAXRecipient(BaseModel):
    """Message recipient."""
    chat_id: int
    chat_type: str = "dialog"
    user_id: Optional[int] = None
    type: str = "dialog"

    class Config:
        extra = "allow"


class MAXAttachmentPayload(BaseModel):
    """Attachment payload — contains URL and access token."""
    url: Optional[str] = None
    token: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class MAXAttachment(BaseModel):
    """Single attachment from MAX message."""
    type: str = ""  # image, video, audio, file, contact, location, inline_keyboard
    payload: MAXAttachmentPayload = Field(default_factory=MAXAttachmentPayload)

    class Config:
        extra = "allow"

    @property
    def is_media(self) -> bool:
        return self.type in ("image", "video", "audio")

    @property
    def is_file(self) -> bool:
        return self.type == "file"

    @property
    def is_image(self) -> bool:
        return self.type == "image"


class MAXMessageBody(BaseModel):
    """Message body."""
    text: Optional[str] = None
    mid: Optional[str] = None  # message ID (string!)
    seq: Optional[int] = None
    attachments: list[MAXAttachment] = Field(default_factory=list)

    class Config:
        extra = "allow"


class MAXMessage(BaseModel):
    """Message object from MAX API."""
    sender: MAXUser
    recipient: MAXRecipient
    body: MAXMessageBody
    timestamp: int

    class Config:
        extra = "allow"


class MAXUpdate(BaseModel):
    """Incoming update from MAX API."""
    update_type: UpdateType
    message: Optional[MAXMessage] = None
    callback: Optional[dict[str, Any]] = None
    timestamp: int
    user_locale: Optional[str] = None

    class Config:
        extra = "allow"


class SendMessageResponse(BaseModel):
    """Response from POST /messages."""
    message_id: Optional[str] = None
    ok: bool = True
    error: Optional[str] = None


class SubscriptionResponse(BaseModel):
    """Response from POST /subscriptions."""
    id: Optional[str] = None
    url: Optional[str] = None
    ok: bool = True

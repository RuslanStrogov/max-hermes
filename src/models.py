"""Pydantic models for MAX Bot API and Hermes webhook data structures."""

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
    name: str
    username: Optional[str] = None


class MAXRecipient(BaseModel):
    """Message recipient."""
    chat_id: int
    type: str  # "chat", "channel", "user"


class MAXMessageBody(BaseModel):
    """Message body."""
    text: Optional[str] = None
    mid: Optional[str] = None  # message ID
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class MAXMessage(BaseModel):
    """Message object from MAX API."""
    sender: MAXUser
    recipient: MAXRecipient
    body: MAXMessageBody
    timestamp: int


class MAXCallbackPayload(BaseModel):
    """Callback from inline keyboard button."""
    callback: dict[str, Any]
    message: MAXMessage


class MAXUpdate(BaseModel):
    """Incoming update from MAX API."""
    update_type: UpdateType
    message: Optional[MAXMessage] = None
    callback: Optional[dict[str, Any]] = None
    timestamp: int


class NewMessageBody(BaseModel):
    """Body for sending a message via MAX API."""
    text: Optional[str] = None
    format: Optional[str] = None  # "markdown" or "html"
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    """Request to POST /messages."""
    chat_id: int
    text: Optional[str] = None
    format: Optional[str] = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    reply_to: Optional[int] = None


class SendMessageResponse(BaseModel):
    """Response from POST /messages."""
    message_id: Optional[str] = None
    ok: bool = True
    error: Optional[str] = None


class SubscriptionRequest(BaseModel):
    """Request to POST /subscriptions."""
    url: str
    update_types: list[str] = Field(default_factory=lambda: [
        "message_created", "message_callback"
    ])


class SubscriptionResponse(BaseModel):
    """Response from POST /subscriptions."""
    id: Optional[str] = None
    url: Optional[str] = None
    ok: bool = True


# ─── Hermes Webhook Models ───────────────────────────────────────────────────


class HermesWebhookPayload(BaseModel):
    """Payload sent to Hermes webhook."""
    message: str
    chat_id: str
    user_id: str
    user_name: str
    platform: str = "max"
    reply_to: Optional[str] = None
    raw_update: Optional[dict[str, Any]] = None


class HermesWebhookResponse(BaseModel):
    """Response from Hermes webhook (agent output)."""
    status: str
    message: Optional[str] = None
    error: Optional[str] = None

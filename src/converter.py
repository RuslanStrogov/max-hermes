"""Message format converter between MAX API and Hermes webhook."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.models import MAXUpdate, MAXMessage, UpdateType

logger = logging.getLogger(__name__)


class MessageConverter:
    """Converts between MAX API format and Hermes webhook format."""

    # ── MAX → Hermes ────────────────────────────────────────────────────────

    @staticmethod
    def max_update_to_hermes_message(update: MAXUpdate) -> Optional[dict[str, Any]]:
        """Convert MAX Update to Hermes webhook message payload.

        Returns None if the update type is not supported.
        """
        if update.update_type == UpdateType.MESSAGE_CREATED:
            if update.message is None:
                return None
            return MessageConverter._message_created_to_hermes(update.message)
        elif update.update_type == UpdateType.MESSAGE_CALLBACK:
            return MessageConverter._callback_to_hermes(update)
        elif update.update_type == UpdateType.BOT_STARTED:
            return MessageConverter._bot_started_to_hermes(update.message)
        else:
            logger.debug("Unsupported update type: %s", update.update_type)
            return None

    @staticmethod
    def _message_created_to_hermes(message: MAXMessage) -> dict[str, Any]:
        """Convert message_created update to Hermes payload."""
        text = message.body.text or ""

        # Handle attachments
        if message.body.attachments:
            attachment_text = MessageConverter._format_attachments(message.body.attachments)
            if attachment_text:
                text = f"{text}\n{attachment_text}" if text else attachment_text

        return {
            "message": text,
            "chat_id": str(message.recipient.chat_id),
            "user_id": str(message.sender.user_id),
            "user_name": message.sender.name,
            "platform": "max",
            "reply_to": message.body.mid,
            "raw_update": {
                "update_type": "message_created",
                "message_id": message.body.mid,
                "timestamp": message.timestamp,
            },
        }

    @staticmethod
    def _callback_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert callback (button press) to Hermes payload."""
        callback_data = update.callback or {}
        message = update.message

        button_text = callback_data.get("text", "")
        payload = callback_data.get("payload", "")

        text = f"[Кнопка: {button_text}]"
        if payload:
            text += f"\nPayload: {payload}"

        if message:
            return {
                "message": text,
                "chat_id": str(message.recipient.chat_id),
                "user_id": str(message.sender.user_id),
                "user_name": message.sender.name,
                "platform": "max",
                "reply_to": message.body.mid,
                "raw_update": {
                    "update_type": "message_callback",
                    "callback_id": callback_data.get("id"),
                    "payload": payload,
                },
            }
        else:
            return {
                "message": text,
                "chat_id": str(callback_data.get("chat_id", "")),
                "user_id": str(callback_data.get("user_id", "")),
                "user_name": callback_data.get("user_name", "Unknown"),
                "platform": "max",
                "raw_update": {
                    "update_type": "message_callback",
                    "callback_id": callback_data.get("id"),
                    "payload": payload,
                },
            }

    @staticmethod
    def _bot_started_to_hermes(message: Optional[MAXMessage]) -> dict[str, Any]:
        """Convert bot_started event to Hermes payload."""
        if message:
            return {
                "message": "/start",
                "chat_id": str(message.recipient.chat_id),
                "user_id": str(message.sender.user_id),
                "user_name": message.sender.name,
                "platform": "max",
            }
        return {
            "message": "/start",
            "chat_id": "unknown",
            "user_id": "unknown",
            "user_name": "Unknown",
            "platform": "max",
        }

    @staticmethod
    def _format_attachments(attachments: list[dict[str, Any]]) -> str:
        """Format MAX attachments for Hermes message text."""
        parts = []
        for att in attachments:
            att_type = att.get("type", "")
            if att_type == "image":
                parts.append("[Изображение]")
            elif att_type == "video":
                parts.append("[Видео]")
            elif att_type == "audio":
                parts.append("[Аудио]")
            elif att_type == "file":
                name = att.get("name", "Файл")
                parts.append(f"[Файл: {name}]")
            elif att_type == "contact":
                parts.append("[Контакт]")
            elif att_type == "inline_keyboard":
                # Keyboard is handled separately
                pass
            else:
                parts.append(f"[{att_type}]")
        return "\n".join(parts)

    # ── Hermes → MAX ────────────────────────────────────────────────────────

    @staticmethod
    def hermes_response_to_max_message(
        response: dict[str, Any],
        chat_id: int,
    ) -> dict[str, Any]:
        """Convert Hermes agent response to MAX API message format."""
        text = response.get("message", response.get("text", ""))

        if not text:
            text = "..."

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }

        # Detect if response contains markdown
        if MessageConverter._has_markdown(text):
            payload["format"] = "markdown"

        return payload

    @staticmethod
    def _has_markdown(text: str) -> bool:
        """Check if text contains markdown formatting."""
        markdown_patterns = [
            r"\*\*.*\*\*",  # bold
            r"\*.*\*",  # italic
            r"~~.*~~",  # strikethrough
            r"\[.*\]\(.*\)",  # links
            r"`.*`",  # code
            r"^#{1,6}\s",  # headers
            r"^>\s",  # blockquote
            r"^\s*[-*+]\s",  # lists
        ]
        import re
        return any(re.search(p, text, re.MULTILINE) for p in markdown_patterns)

    # ── Utility ─────────────────────────────────────────────────────────────

    @staticmethod
    def parse_max_webhook_payload(raw_body: bytes) -> MAXUpdate:
        """Parse raw webhook payload from MAX into MAXUpdate."""
        data = json.loads(raw_body)
        return MAXUpdate(**data)

    @staticmethod
    def build_inline_keyboard(
        buttons: list[list[dict[str, str]]],
    ) -> dict[str, Any]:
        """Build MAX inline keyboard attachment.

        Args:
            buttons: List of rows, each row is a list of button dicts.
                    Each button: {"type": "callback", "text": "...", "payload": "..."}

        Returns:
            MAX API attachment dict.
        """
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": buttons,
            },
        }

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

        Returns None if the update type is not supported / should be silently ignored.
        """
        handlers = {
            UpdateType.MESSAGE_CREATED: MessageConverter._message_created_to_hermes,
            UpdateType.MESSAGE_EDITED: MessageConverter._message_edited_to_hermes,
            UpdateType.MESSAGE_REMOVED: MessageConverter._message_removed_to_hermes,
            UpdateType.MESSAGE_CALLBACK: lambda u: MessageConverter._callback_to_hermes(u),
            UpdateType.BOT_STARTED: lambda u: MessageConverter._bot_started_to_hermes(u.message),
            UpdateType.BOT_ADDED: lambda u: MessageConverter._bot_added_to_hermes(u),
            UpdateType.BOT_REMOVED: lambda u: MessageConverter._bot_removed_to_hermes(u),
            UpdateType.CHAT_CREATED: lambda u: MessageConverter._chat_created_to_hermes(u),
        }

        handler = handlers.get(update.update_type)
        if handler is None:
            logger.debug("Unsupported update type: %s", update.update_type)
            return None

        # For message-based events, ensure message exists
        if update.update_type in (
            UpdateType.MESSAGE_CREATED,
            UpdateType.MESSAGE_EDITED,
            UpdateType.MESSAGE_REMOVED,
        ):
            if update.message is None:
                return None

        return handler(update)

    @staticmethod
    def _message_created_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert message_created update to Hermes payload."""
        message = update.message
        if message is None:
            return {
                "message": "",
                "chat_id": "unknown",
                "user_id": "unknown",
                "user_name": "Unknown",
                "platform": "max",
            }
        text = message.body.text or ""

        # Handle attachments - pass URLs and metadata
        attachments_info = []
        if message.body.attachments:
            for att in message.body.attachments:
                att_type = att.type
                payload = att.payload
                att_info = {
                    "type": att_type,
                    "url": payload.url,
                    "token": payload.token,
                    "metadata": payload.metadata,
                }
                attachments_info.append(att_info)

            attachment_text = MessageConverter._format_attachments(
                [a.model_dump() if hasattr(a, 'model_dump') else a for a in message.body.attachments]
            )
            if attachment_text:
                text = f"{text}\n{attachment_text}" if text else attachment_text

        # Build user name from first_name + last_name if name is empty
        user_name = message.sender.name
        if not user_name:
            parts = [message.sender.first_name, message.sender.last_name]
            user_name = " ".join(p for p in parts if p) or "Unknown"

        return {
            "message": text,
            "chat_id": str(message.recipient.chat_id),
            "user_id": str(message.sender.user_id),
            "user_name": user_name,
            "platform": "max",
            "reply_to": message.body.mid,
            "attachments": attachments_info,
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
    def _message_edited_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert message_edited update to Hermes payload."""
        message = update.message
        if message is None:
            return {
                "message": "[Отредактировано]",
                "chat_id": "unknown",
                "user_id": "unknown",
                "user_name": "Unknown",
                "platform": "max",
            }
        text = message.body.text or ""
        return {
            "message": f"[Отредактировано] {text}",
            "chat_id": str(message.recipient.chat_id),
            "user_id": str(message.sender.user_id),
            "user_name": message.sender.name,
            "platform": "max",
            "reply_to": message.body.mid,
            "raw_update": {
                "update_type": "message_edited",
                "message_id": message.body.mid,
                "timestamp": message.timestamp,
            },
        }

    @staticmethod
    def _message_removed_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert message_removed update to Hermes payload."""
        message = update.message
        if message is None:
            return {
                "message": "[Сообщение удалено]",
                "chat_id": "unknown",
                "user_id": "unknown",
                "user_name": "Unknown",
                "platform": "max",
            }
        return {
            "message": "[Сообщение удалено]",
            "chat_id": str(message.recipient.chat_id),
            "user_id": str(message.sender.user_id),
            "user_name": message.sender.name,
            "platform": "max",
            "raw_update": {
                "update_type": "message_removed",
                "message_id": message.body.mid,
                "timestamp": message.timestamp,
            },
        }

    @staticmethod
    def _bot_added_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert bot_added event to Hermes payload (bot added to group)."""
        message = update.message
        if message:
            return {
                "message": "[Бот добавлен в чат]",
                "chat_id": str(message.recipient.chat_id),
                "user_id": str(message.sender.user_id),
                "user_name": message.sender.name,
                "platform": "max",
                "raw_update": {
                    "update_type": "bot_added",
                    "timestamp": update.timestamp,
                },
            }
        return {
            "message": "[Бот добавлен в чат]",
            "chat_id": "unknown",
            "user_id": "unknown",
            "user_name": "Unknown",
            "platform": "max",
        }

    @staticmethod
    def _bot_removed_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert bot_removed event to Hermes payload (bot removed from group)."""
        message = update.message
        if message:
            return {
                "message": "[Бот удалён из чата]",
                "chat_id": str(message.recipient.chat_id),
                "user_id": str(message.sender.user_id),
                "user_name": message.sender.name,
                "platform": "max",
                "raw_update": {
                    "update_type": "bot_removed",
                    "timestamp": update.timestamp,
                },
            }
        return {
            "message": "[Бот удалён из чата]",
            "chat_id": "unknown",
            "user_id": "unknown",
            "user_name": "Unknown",
            "platform": "max",
        }

    @staticmethod
    def _chat_created_to_hermes(update: MAXUpdate) -> dict[str, Any]:
        """Convert chat_created event to Hermes payload."""
        message = update.message
        if message:
            return {
                "message": "[Чат создан]",
                "chat_id": str(message.recipient.chat_id),
                "user_id": str(message.sender.user_id),
                "user_name": message.sender.name,
                "platform": "max",
                "raw_update": {
                    "update_type": "chat_created",
                    "timestamp": update.timestamp,
                },
            }
        return {
            "message": "[Чат создан]",
            "chat_id": "unknown",
            "user_id": "unknown",
            "user_name": "Unknown",
            "platform": "max",
        }

    @staticmethod
    def _format_attachments(attachments: list[dict[str, Any]]) -> str:
        """Format MAX attachments for Hermes message text with URLs."""
        parts = []
        for att in attachments:
            att_type = att.get("type", "")
            payload = att.get("payload", {})
            url = payload.get("url", "")
            token = payload.get("token", "")

            if att_type == "image":
                label = "🖼 [Изображение]"
                if url:
                    label += f"\nURL: {url}"
                parts.append(label)
            elif att_type == "video":
                label = "🎬 [Видео]"
                if url:
                    label += f"\nURL: {url}"
                parts.append(label)
            elif att_type == "audio":
                label = "🎤 [Голосовое сообщение]"
                if url:
                    label += f"\nURL: {url}"
                parts.append(label)
            elif att_type == "file":
                name = att.get("name", "Файл")
                label = f"📎 [Файл: {name}]"
                if url:
                    label += f"\nURL: {url}"
                parts.append(label)
            elif att_type == "contact":
                parts.append("[Контакт]")
            elif att_type == "inline_keyboard":
                # Keyboard is handled separately
                pass
            else:
                label = f"[{att_type}]"
                if url:
                    label += f"\nURL: {url}"
                parts.append(label)
        return "\n".join(parts)

    # ── Hermes → MAX ────────────────────────────────────────────────────────

    @staticmethod
    def hermes_response_to_max_message(
        response: dict[str, Any],
        chat_id: int,
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Convert Hermes agent response to MAX API message format.

        For dialogs (DM): pass user_id — takes priority over chat_id
        For group chats: pass chat_id only
        """
        text = response.get("message", response.get("text", ""))

        if not text:
            text = "..."

        payload: dict[str, Any] = {
            "text": text,
        }

        # For dialogs, user_id is required; for groups, chat_id
        if user_id is not None and user_id > 0:
            payload["user_id"] = user_id
        elif chat_id > 0:
            payload["chat_id"] = chat_id
        else:
            logger.warning("Neither user_id nor chat_id available for response")

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

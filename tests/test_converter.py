"""Tests for message converter."""

import pytest

from src.converter import MessageConverter
from src.models import (
    MAXUpdate,
    MAXMessage,
    MAXUser,
    MAXRecipient,
    MAXMessageBody,
    UpdateType,
)


@pytest.fixture
def sample_message():
    return MAXMessage(
        sender=MAXUser(user_id=12345, name="Иван Иванов", username="ivan"),
        recipient=MAXRecipient(chat_id=67890, type="chat"),
        body=MAXMessageBody(text="Привет, бот!", mid="msg_abc123"),
        timestamp=1737500130100,
    )


@pytest.fixture
def sample_update(sample_message):
    return MAXUpdate(
        update_type=UpdateType.MESSAGE_CREATED,
        message=sample_message,
        timestamp=1737500130100,
    )


class TestMessageConverter:
    def test_message_created_to_hermes(self, sample_update):
        result = MessageConverter.max_update_to_hermes_message(sample_update)
        assert result is not None
        assert result["message"] == "Привет, бот!"
        assert result["chat_id"] == "67890"
        assert result["user_id"] == "12345"
        assert result["user_name"] == "Иван Иванов"
        assert result["platform"] == "max"

    def test_callback_to_hermes(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CALLBACK,
            callback={
                "id": "cb_123",
                "text": "Кнопка 1",
                "payload": "btn_1_pressed",
            },
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="chat"),
                body=MAXMessageBody(mid="msg_456"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_hermes_message(update)
        assert result is not None
        assert "[Кнопка: Кнопка 1]" in result["message"]
        assert "btn_1_pressed" in result["message"]

    def test_unsupported_update_type(self):
        # All known update types are now supported.
        # Test that an unknown/unhandled type returns None.
        # Since UpdateType enum covers all known types, we test
        # that CHAT_CREATED is now handled (not None).
        update = MAXUpdate(
            update_type=UpdateType.CHAT_CREATED,
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_hermes_message(update)
        assert result is not None
        assert result["message"] == "[Чат создан]"
        assert result["platform"] == "max"

    def test_message_edited_to_hermes(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_EDITED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="chat"),
                body=MAXMessageBody(text="Отредактированный текст", mid="msg_789"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_hermes_message(update)
        assert result is not None
        assert "[Отредактировано]" in result["message"]
        assert "Отредактированный текст" in result["message"]

    def test_message_removed_to_hermes(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_REMOVED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="chat"),
                body=MAXMessageBody(mid="msg_deleted"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_hermes_message(update)
        assert result is not None
        assert result["message"] == "[Сообщение удалено]"

    def test_bot_added_to_hermes(self):
        update = MAXUpdate(
            update_type=UpdateType.BOT_ADDED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="chat"),
                body=MAXMessageBody(mid="msg_001"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_hermes_message(update)
        assert result is not None
        assert result["message"] == "[Бот добавлен в чат]"

    def test_bot_removed_to_hermes(self):
        update = MAXUpdate(
            update_type=UpdateType.BOT_REMOVED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="chat"),
                body=MAXMessageBody(mid="msg_002"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_hermes_message(update)
        assert result is not None
        assert result["message"] == "[Бот удалён из чата]"

    def test_hermes_response_to_max(self):
        response = {"message": "Ответ от бота"}
        result = MessageConverter.hermes_response_to_max_message(response, chat_id=67890)
        assert result["chat_id"] == 67890
        assert result["text"] == "Ответ от бота"

    def test_markdown_detection(self):
        assert MessageConverter._has_markdown("**жирный**") is True
        assert MessageConverter._has_markdown("*курсив*") is True
        assert MessageConverter._has_markdown("обычный текст") is False

    def test_build_inline_keyboard(self):
        buttons = [
            [{"type": "callback", "text": "Да", "payload": "yes"}],
            [{"type": "callback", "text": "Нет", "payload": "no"}],
        ]
        result = MessageConverter.build_inline_keyboard(buttons)
        assert result["type"] == "inline_keyboard"
        assert len(result["payload"]["buttons"]) == 2

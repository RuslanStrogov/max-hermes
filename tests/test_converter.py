"""Tests for message converter."""

import pytest

from max_shared.constants import GROUP_CHAT_TYPES
from max_shared.converter import MessageConverter
from max_shared.markdown import has_markdown
from max_shared.models import (
    MAXUpdate,
    MAXMessage,
    MAXUser,
    MAXRecipient,
    MAXMessageBody,
    MAXAttachment,
    MAXAttachmentPayload,
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
    def test_message_created(self, sample_update):
        result = MessageConverter.max_update_to_message(sample_update)
        assert result is not None
        assert result["message"] == "Привет, бот!"
        assert result["chat_id"] == "67890"
        assert result["user_id"] == "12345"
        assert result["user_name"] == "Иван Иванов"
        assert result["platform"] == "max"

    def test_callback(self):
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
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "[Кнопка: Кнопка 1]" in result["message"]
        assert "btn_1_pressed" in result["message"]

    def test_chat_created(self):
        update = MAXUpdate(
            update_type=UpdateType.CHAT_CREATED,
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert result["message"] == "[Чат создан]"
        assert result["platform"] == "max"

    def test_message_edited(self):
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
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "[Отредактировано]" in result["message"]
        assert "Отредактированный текст" in result["message"]

    def test_message_removed(self):
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
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert result["message"] == "[Сообщение удалено]"

    def test_bot_added(self):
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
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert result["message"] == "[Бот добавлен в чат]"

    def test_bot_removed(self):
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
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert result["message"] == "[Бот удалён из чата]"

    def test_response_to_max(self):
        response = {"message": "Ответ от бота"}
        result = MessageConverter.response_to_max_message(response, chat_id=67890)
        assert result["chat_id"] == 67890
        assert result["text"] == "Ответ от бота"

    def test_response_with_markdown(self):
        response = {"message": "**жирный**"}
        result = MessageConverter.response_to_max_message(response, chat_id=67890)
        assert result.get("format") == "markdown"

    def test_response_plain_no_markdown(self):
        response = {"message": "обычный текст"}
        result = MessageConverter.response_to_max_message(response, chat_id=67890)
        assert "format" not in result

    def test_build_inline_keyboard(self):
        buttons = [
            [{"type": "callback", "text": "Да", "payload": "yes"}],
            [{"type": "callback", "text": "Нет", "payload": "no"}],
        ]
        result = MessageConverter.build_inline_keyboard(buttons)
        assert result["type"] == "inline_keyboard"
        assert len(result["payload"]["buttons"]) == 2

    def test_voice_message(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="dialog"),
                body=MAXMessageBody(
                    text="",
                    mid="msg_voice_001",
                    attachments=[
                        MAXAttachment(
                            type="audio",
                            payload=MAXAttachmentPayload(
                                url="https://cdn.max.ru/audio/abc123.ogg",
                                token="audio_token_xyz",
                            ),
                        )
                    ],
                ),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "[Голосовое]" in result["message"] or "🎤" in result["message"]
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["type"] == "audio"

    def test_voice_message_with_caption(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="dialog"),
                body=MAXMessageBody(
                    text="Слушай это",
                    mid="msg_voice_002",
                    attachments=[
                        MAXAttachment(
                            type="audio",
                            payload=MAXAttachmentPayload(
                                url="https://cdn.max.ru/audio/def456.ogg",
                                token="audio_token_abc",
                            ),
                        )
                    ],
                ),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Слушай это" in result["message"]

    def test_image_message(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="dialog"),
                body=MAXMessageBody(
                    text="Смотри фото",
                    mid="msg_img_001",
                    attachments=[
                        MAXAttachment(
                            type="image",
                            payload=MAXAttachmentPayload(
                                url="https://cdn.max.ru/image/photo.jpg",
                                token="img_token_abc",
                            ),
                        )
                    ],
                ),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Смотри фото" in result["message"]
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["type"] == "image"

    def test_file_message(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="dialog"),
                body=MAXMessageBody(
                    text="Вот документ",
                    mid="msg_file_001",
                    attachments=[
                        MAXAttachment(
                            type="file",
                            payload=MAXAttachmentPayload(
                                url="https://cdn.max.ru/files/report.pdf",
                                token="file_token_xyz",
                            ),
                        )
                    ],
                ),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Вот документ" in result["message"]
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["type"] == "file"

    def test_multiple_attachments(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(chat_id=67890, type="dialog"),
                body=MAXMessageBody(
                    text="Фото и документ",
                    mid="msg_multi_001",
                    attachments=[
                        MAXAttachment(
                            type="image",
                            payload=MAXAttachmentPayload(
                                url="https://cdn.max.ru/image/photo.jpg",
                                token="img_token_1",
                            ),
                        ),
                        MAXAttachment(
                            type="file",
                            payload=MAXAttachmentPayload(
                                url="https://cdn.max.ru/files/doc.pdf",
                                token="file_token_1",
                            ),
                        ),
                    ],
                ),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Фото и документ" in result["message"]
        assert len(result["attachments"]) == 2

    def test_group_message(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(
                    chat_id=999888777, type="group", chat_type="group"
                ),
                body=MAXMessageBody(text="Привет всем!", mid="msg_group_001"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert result["chat_id"] == "999888777"
        assert result["user_id"] == "12345"
        assert result["message"] == "Привет всем!"

    def test_determine_reply_target_dialog(self):
        sender = MAXUser(user_id=123, name="Test")
        recipient = MAXRecipient(chat_id=456, chat_type="dialog")
        chat_id, user_id = MessageConverter.determine_reply_target(
            recipient, sender
        )
        assert user_id == 123
        assert chat_id is None

    def test_determine_reply_target_group(self):
        sender = MAXUser(user_id=123, name="Test")
        recipient = MAXRecipient(chat_id=456, chat_type="group")
        chat_id, user_id = MessageConverter.determine_reply_target(
            recipient, sender
        )
        assert chat_id == 456
        assert user_id is None

    def test_user_added_event(self):
        update = MAXUpdate(
            update_type=UpdateType.USER_ADDED,
            message=MAXMessage(
                sender=MAXUser(user_id=67890, name="Петр"),
                recipient=MAXRecipient(
                    chat_id=999888777, type="group", chat_type="group"
                ),
                body=MAXMessageBody(mid="msg_event_001"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Пользователь добавлен в чат" in result["message"]
        assert "Петр" in result["message"]

    def test_user_removed_event(self):
        update = MAXUpdate(
            update_type=UpdateType.USER_REMOVED,
            message=MAXMessage(
                sender=MAXUser(user_id=67890, name="Петр"),
                recipient=MAXRecipient(
                    chat_id=999888777, type="group", chat_type="group"
                ),
                body=MAXMessageBody(mid="msg_event_002"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Пользователь покинул чат" in result["message"]
        assert "Петр" in result["message"]

    def test_chat_title_changed_event(self):
        update = MAXUpdate(
            update_type=UpdateType.CHAT_TITLE_CHANGED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Иван"),
                recipient=MAXRecipient(
                    chat_id=999888777, type="group", chat_type="group"
                ),
                body=MAXMessageBody(mid="msg_event_003"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert "Название чата изменено" in result["message"]

    def test_channel_message(self):
        update = MAXUpdate(
            update_type=UpdateType.MESSAGE_CREATED,
            message=MAXMessage(
                sender=MAXUser(user_id=12345, name="Автор"),
                recipient=MAXRecipient(
                    chat_id=111222333, type="channel", chat_type="channel"
                ),
                body=MAXMessageBody(text="Новость", mid="msg_ch_001"),
                timestamp=1737500130100,
            ),
            timestamp=1737500130100,
        )
        result = MessageConverter.max_update_to_message(update)
        assert result is not None
        assert result["chat_id"] == "111222333"
        assert result["message"] == "Новость"

    def test_response_routing_fallback(self):
        response = {"message": "Тест"}
        result = MessageConverter.response_to_max_message(
            response, chat_id=None, user_id=None
        )
        assert "chat_id" not in result
        assert "user_id" not in result
        assert result["text"] == "Тест"

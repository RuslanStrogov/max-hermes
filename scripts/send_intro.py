#!/usr/bin/env python3
"""Send self-introduction message to MAX group chats."""

import asyncio
import os
import sys

# Add project paths
sys.path.insert(0, "/mnt/data/projects/max-hermes")
sys.path.insert(0, "/mnt/data/projects/max-hermes-plugin")

from max_shared.max_client import MAXClient


INTRO_MESSAGE = """Привет всем! 👋 Я КИСКА 🐾 — AI-помощник Руслана Строгова.

Немного о себе:
• Работаю на базе Hermes Agent от Nous Research
• Интегрирована с MAX Messenger через собственный мост (max-hermes bridge)
• Умею отвечать на вопросы, искать информацию, работать с файлами и кодом
• Подключена к GitHub, Google Drive, Telegram и другим сервисам
• Помогаю с проектами: MAX-Hermes Bridge, WB Auto Pricing и другими
• Могу работать с изображениями, видео, аудио и документами
• Умею запускать код, деплоить приложения, мониторить серверы

Если нужна помощь — пишите в чат! Я тут 😊"""

# Target chats to send to
TARGET_CHATS = [
    3433333112,  # ЛИГА КУПЦОВ AI
    317331419,   # Текущий чат
]


async def main():
    token = os.environ.get("MAX_BOT_TOKEN", "")
    if not token:
        # Try to read from .env
        env_path = "/mnt/data/projects/max-hermes/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MAX_BOT_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                        break

    if not token:
        print("ERROR: MAX_BOT_TOKEN not found")
        sys.exit(1)

    client = MAXClient(token=token)

    try:
        # Verify bot connection
        bot_info = await client.get_bot_info()
        print(f"Connected as: {bot_info.get('name')} (@{bot_info.get('username')})")

        for chat_id in TARGET_CHATS:
            try:
                result = await client.send_message(
                    chat_id=chat_id,
                    text=INTRO_MESSAGE,
                )
                print(f"✅ Sent to chat {chat_id}: message_id={result.message_id}")
            except Exception as e:
                print(f"❌ Failed to send to chat {chat_id}: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

"""HTTP webhook server for receiving MAX updates."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from aiohttp import web

from max_shared.constants import GROUP_CHAT_TYPES
from max_shared.converter import MessageConverter
from max_shared.max_client import MAXClient, MAXApiError
from max_shared.models import MAXAttachment, MAXUpdate

from src.config import Config
from src.hermes_client import HermesClient, HermesClientError

logger = logging.getLogger(__name__)

# Deduplication constants
DEDUP_WINDOW = 300  # 5 minutes
DEDUP_MAX_SIZE = 1000

# Default system prompt / role for the bridge bot
DEFAULT_SYSTEM_PROMPT = (
    "Ты — MAX Bridge Bot. Общайся на русском. "
    "Будь полезным и отвечай по существу."
)


class WebhookServer:
    """HTTP server that receives MAX webhook updates and routes them to Hermes."""

    def __init__(
        self,
        config: Config,
        max_client: MAXClient,
        hermes_client: HermesClient,
        bot_username: str = "",
    ):
        self._config = config
        self._max = max_client
        self._hermes = hermes_client
        self._bot_username = bot_username
        self._converter = MessageConverter()
        self._app = web.Application()
        self._app["hermes_client"] = hermes_client
        self._app["max_client"] = max_client
        self._processed_ids: dict[str, float] = {}
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register HTTP routes."""
        self._app.router.add_post("/webhook", self._handle_webhook)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/status", self._handle_status)

    @property
    def app(self) -> web.Application:
        """Get aiohttp application."""
        return self._app

    # ── Request handlers ────────────────────────────────────────────────────

    async def _handle_health(self, request: web.Request) -> web.Response:
        """GET /health — health check."""
        return web.json_response({"status": "ok", "service": "max-bridge"})

    async def _handle_status(self, request: web.Request) -> web.Response:
        """GET /status — bridge status."""
        try:
            bot_info = await self._max.get_bot_info()
            return web.json_response({
                "status": "ok",
                "bot": bot_info,
                "hermes_bin": self._config.hermes_bin,
            })
        except Exception as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=503,
            )

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """POST /webhook — receive MAX update."""
        if not self._verify_signature(request):
            logger.warning("Invalid webhook signature from %s", request.remote)
            return web.json_response({"error": "Invalid signature"}, status=401)

        try:
            raw_body = await request.read()
            data = json.loads(raw_body)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Failed to parse webhook body: %s", e)
            return web.json_response({"error": "Invalid JSON"}, status=400)

        logger.debug("Raw MAX payload: %s", raw_body[:2000])

        # Sanitize: ensure attachments is never None (Pydantic v2 fails on null with List)
        if data.get("message", {}).get("body", {}).get("attachments") is None:
            if "message" in data and "body" in data["message"]:
                data["message"]["body"]["attachments"] = []

        try:
            update = MAXUpdate(**data)
        except Exception as e:
            logger.error("Failed to parse update: %s", e)
            return web.json_response({"error": "Invalid update format"}, status=400)

        logger.info(
            "Received update: type=%s, user=%s, chat=%s",
            update.update_type,
            update.message.sender.name if update.message else "N/A",
            update.message.recipient.chat_id if update.message else "N/A",
        )

        # Deduplication: extract message ID from raw payload
        raw_msg = data.get("message", {}) if data.get("message") else {}
        msg_id = raw_msg.get("body", {}).get("mid", "") if raw_msg else ""
        if msg_id and self._is_duplicate(msg_id):
            return web.json_response({"ok": True, "dedup": True})

        # Access control
        if self._config.allowed_users and update.message:
            if update.message.sender.user_id not in self._config.allowed_users:
                logger.warning(
                    "Unauthorized user %d — ignoring",
                    update.message.sender.user_id,
                )
                return web.json_response({"ok": True, "ignored": True})

        # Handle bot commands directly (before forwarding to Hermes)
        command_response = await self._handle_bot_command(update)
        if command_response:
            logger.info("Handled command directly: %s", command_response["cmd"])
            return command_response["http_response"]

        # ── Group chat filtering ─────────────────────────────────────────────
        # Only respond in groups when explicitly mentioned (@bot_username)
        # Groups have negative chat_id (e.g. -69536335178338)

        if update.message and update.message.recipient.chat_id < 0:
            # 1. Ignore messages from other bots (prevents bot loops)
            if update.message.sender.is_bot:
                logger.info(
                    "Ignoring bot message in group %d from %s — skipping",
                    update.message.recipient.chat_id,
                    update.message.sender.display_name,
                )
                return web.json_response({"ok": True, "ignored": "bot_message"})

            # 2. Only respond if @bot_username is in the message text
            text = (update.message.body.text or "").strip()
            if self._bot_username and f"@{self._bot_username.lower()}" not in text.lower():
                logger.info(
                    "Bot not mentioned in group %d — ignoring. text=%r",
                    update.message.recipient.chat_id,
                    text[:100],
                )
                return web.json_response({"ok": True, "ignored": "not_mentioned"})
            elif not self._bot_username:
                logger.warning(
                    "bot_username not set — cannot check mention in group %d",
                    update.message.recipient.chat_id,
                )

        # Convert and forward to Hermes
        hermes_payload = self._converter.max_update_to_message(update)

        if hermes_payload is None:
            logger.debug(
                "Update type %s not supported — skipping", update.update_type
            )
            return web.json_response({"ok": True, "skipped": True})

        # Initialise keep-typing handle before try so except blocks can cancel it
        typing_task: Optional[asyncio.Task] = None

        try:
            # Start keep-typing loop so the user sees continuous feedback
            if update.message:
                recipient = update.message.recipient
                typing_task = asyncio.create_task(
                    self._keep_typing(chat_id=recipient.chat_id)
                )

            # Download attachments
            content_items = []
            if update.message and update.message.body.attachments:
                content_items = await self._download_attachments(
                    update.message.body.attachments
                )
                if content_items:
                    hermes_payload["content_items"] = content_items

            # Send to Hermes with role instructions
            hermes_payload["system_prompt"] = DEFAULT_SYSTEM_PROMPT
            hermes_response = await self._hermes.send_message(**hermes_payload)

            # Cancel keep-typing – answer is ready
            if typing_task:
                typing_task.cancel()
                typing_task = None

            # Send response back to MAX
            agent_text = hermes_response.get(
                "message", hermes_response.get("text", "")
            )

            # Truncate if exceeds MAX API 4000-char limit
            MAX_TEXT_LIMIT = 3950  # safe margin
            if len(agent_text) > MAX_TEXT_LIMIT:
                truncated = True
                agent_text = agent_text[:MAX_TEXT_LIMIT]
                # Try to break at a sentence boundary
                for splitter in ("\n\n", "\n", ". ", "! ", "? "):
                    idx = agent_text.rfind(splitter)
                    if idx > 3000:
                        agent_text = agent_text[: idx + len(splitter)]
                        break
                agent_text += (
                    f"\n\n*[Сообщение сокращено — "
                    f"было {len(hermes_response.get('message', hermes_response.get('text', '')))} "
                    f"символов, макс. {MAX_TEXT_LIMIT}]"
                )
                logger.info(
                    "Response truncated from %d to %d chars for MAX API limit",
                    len(hermes_response.get("message", hermes_response.get("text", ""))),
                    len(agent_text),
                )

            if agent_text and update.message:
                recipient = update.message.recipient
                sender = update.message.sender

                # MAX API requires chat_id for sending messages.
                # For group chats: use recipient.chat_id.
                # For DM (dialog): recipient.chat_id == sender.user_id (the chat owner).
                target_chat_id = recipient.chat_id
                target_user_id = None

                logger.info(
                    "Sending response to MAX: chat_id=%s, user_id=%s, text_len=%d",
                    target_chat_id,
                    target_user_id,
                    len(agent_text),
                )

                max_msg = MessageConverter.response_to_max_message(
                    hermes_response,
                    chat_id=target_chat_id,
                    user_id=target_user_id,
                    reply_to=(
                        update.message.body.mid
                        if update.message.body and update.message.body.mid
                        else None
                    ),
                )
                logger.info("MAX send_message payload: %s", max_msg)
                await self._max.send_message(**max_msg)

            # Turn off typing indicator after response is sent
            if update.message:
                try:
                    await self._max.send_chat_action(
                        chat_id=update.message.recipient.chat_id,
                        action="typing_off",
                    )
                except Exception:
                    logger.debug("Failed to send typing_off (non-critical)")

            return web.json_response({"ok": True})

        except HermesClientError as e:
            logger.error("Hermes error: %s", e)
            if typing_task:
                typing_task.cancel()
            return web.json_response({"ok": True, "hermes_error": str(e)})

        except MAXApiError as e:
            logger.error("MAX API error sending response: %s", e)
            if typing_task:
                typing_task.cancel()
            return web.json_response({"ok": True, "max_error": str(e)})

        except Exception as e:
            logger.exception("Unexpected error processing update: %s", e)
            if typing_task:
                typing_task.cancel()
            return web.json_response({"ok": True, "error": str(e)})

    async def _download_attachments(
        self, attachments: list[MAXAttachment]
    ) -> list[dict[str, Any]]:
        """Download media attachments from MAX CDN."""
        import os
        import tempfile

        content_items = []
        tmp_dir = tempfile.mkdtemp(prefix="max_attachments_")

        for att in attachments:
            if not att.is_media and not att.is_file:
                continue
            if not att.payload.url:
                continue

            try:
                token = att.payload.get_effective_token()
                data = await self._max.download_attachment(
                    att.payload.url, token=token
                )

                if att.is_image:
                    ext = ".png"
                    ctype = "image"
                elif att.is_video:
                    ext = ".mp4"
                    ctype = "video"
                elif att.is_audio:
                    ext = ".ogg"
                    ctype = "audio"
                else:
                    ext = ".bin"
                    ctype = "file"

                dest = os.path.join(tmp_dir, f"{att.type}_{id(att)}{ext}")
                with open(dest, "wb") as f:
                    f.write(data)

                content_items.append({
                    "content_type": ctype,
                    "local_path": dest,
                    "original_url": att.payload.url,
                    "mime_type": f"{ctype}/{ext[1:]}",
                    "size_bytes": len(data),
                })
                logger.info(
                    "Downloaded attachment: %s -> %s (%d bytes)",
                    att.type,
                    dest,
                    len(data),
                )
            except Exception as e:
                logger.warning(
                    "Failed to download attachment %s: %s", att.type, e
                )

        return content_items

    # ── Bot Commands ──────────────────────────────────────────────────────────
    #
    # Команды разделены на две категории:
    #
    #   1. VISIBLE_COMMANDS — отображаются в меню "/" (регистрируются через MAX API).
    #   2. INVISIBLE_COMMANDS — скрытые: работают по вводу, но в меню не показываются.
    #
    # Для регистрации через MAX API используется список REGISTERED_COMMANDS
    # (имена без слеша, с кратким описанием).
    #
    # Telegram-стиль: все обрабатываемые команды живут в едином словаре,
    # а видимость в меню определяется отдельным списком.

    VISIBLE_COMMANDS: dict[str, str] = {
        "/start": (
            "👋 **Привет!** Я — MAX Bridge Bot, соединяю MAX и Hermes.\n\n"
            "Пиши любой вопрос или задачу — я передам её Hermes AI.\n\n"
            "**Команды:**\n"
            "• `/help` — помощь\n"
            "• `/about` — информация"
        ),
        "/help": (
            "ℹ️ **Помощь по MAX Bridge Bot**\n\n"
            "Этот бот — мост между MAX и Hermes AI.\n\n"
            "**Как пользоваться:**\n"
            "Просто пиши сообщение, и я передам его Hermes.\n"
            "Я поддерживаю текст, изображения, аудио и файлы.\n\n"
            "**Команды:**\n"
            "• `/start` — начать диалог\n"
            "• `/help` — эта справка\n"
            "• `/about` — информация о боте\n\n"
            "**Скрытые команды:**\n"
            "• `/id` — информация об ID чата и пользователя\n"
            "• `/ping` — проверка соединения\n"
            "• `/stats` — статистика моста\n"
            "• `/admin` — панель администратора"
        ),
        "/about": (
            "🤖 **MAX Bridge Bot**\n\n"
            "Версия: 1.0.0\n"
            "Платформа: Hermes AI + MAX\n\n"
            "Разработано специально для интеграции MAX и Hermes.\n"
            "Использует технологии: асинхронный Python, aiohttp, MAX API."
        ),
    }

    INVISIBLE_COMMANDS: dict[str, str] = {
        "/ping": "🏓 Понг! Всё работает.",
    }

    # ── Команды, регистрируемые в меню через MAX API ────────────────────────

    REGISTERED_COMMANDS: list[dict[str, str]] = [
        {"name": "start", "description": "Начать диалог с ботом"},
        {"name": "help", "description": "Помощь и информация о боте"},
        {"name": "about", "description": "О боте и его возможностях"},
    ]

    # ── Обработчики невидимых команд, требующих динамического ответа ─────────
    #
    # Если команде нужно подставить данные (ID, статистику и т.п.),
    # добавляем сюда функцию-обработчик. Ключ — команда со слешем.

    _INVISIBLE_HANDLERS: dict[str, str] = {
        "/id": "_cmd_id",
        "/stats": "_cmd_stats",
        "/admin": "_cmd_admin",
    }

    async def _cmd_id(self, update: MAXUpdate) -> str:
        """Обработчик /id — показывает ID чата и пользователя."""
        chat_id = update.message.recipient.chat_id if update.message else "?"
        user_id = update.message.sender.user_id if update.message else "?"
        display = update.message.sender.display_name if update.message else "?"
        return (
            f"🔢 **ID:**\n\n"
            f"Chat ID: `{chat_id}`\n"
            f"User ID: `{user_id}`\n"
            f"Username: `{display}`"
        )

    async def _cmd_stats(self, update: MAXUpdate) -> str:
        """Обработчик /stats — статистика моста."""
        if not hasattr(self, "_cmd_stats_counter"):
            self._cmd_stats_counter = 0
        self._cmd_stats_counter += 1
        return (
            f"📊 **Статистика моста**\n\n"
            f"Запросов к /stats: `{self._cmd_stats_counter}`\n"
            f"Обработано команд (с начала сессии): хранение не реализовано"
        )

    async def _cmd_admin(self, update: MAXUpdate) -> str:
        """Обработчик /admin — панель администратора."""
        user_id = update.message.sender.user_id if update.message else 0
        if self._config.allowed_users and user_id in self._config.allowed_users:
            return (
                "⚙️ **Панель администратора**\n\n"
                "• `Uptime` — (будет реализовано)\n"
                "• `Logs` — (будет реализовано)\n"
                "• `Config` — (будет реализовано)"
            )
        return "⛔ Доступ запрещён. Эта команда только для администраторов."

    # ── Общий метод обработки команд ─────────────────────────────────────────

    async def _handle_bot_command(self, update: MAXUpdate) -> Optional[dict]:
        """Обработать команду бота (видимую или невидимую).

        Сначала проверяет VISIBLE_COMMANDS, затем INVISIBLE_COMMANDS,
        затем динамические обработчики (_INVISIBLE_HANDLERS).

        Возвращает dict с 'cmd' и 'http_response' или None,
        если сообщение не является командой.
        """
        if not update.message:
            return None

        text = (update.message.body.text or "").strip().lower()
        recipient = update.message.recipient
        target_chat_id = recipient.chat_id

        response_text: Optional[str] = None

        # 1. Visible commands (static text)
        response_text = self.VISIBLE_COMMANDS.get(text)

        # 2. Invisible commands (static text)
        if response_text is None:
            response_text = self.INVISIBLE_COMMANDS.get(text)

        # 3. Invisible handlers (dynamic — требуют логики)
        if response_text is None and text in self._INVISIBLE_HANDLERS:
            handler_name = self._INVISIBLE_HANDLERS[text]
            handler = getattr(self, handler_name, None)
            if handler:
                try:
                    response_text = await handler(update)
                except Exception as e:
                    logger.error("Command handler %s error: %s", text, e)
                    response_text = f"⚠️ Ошибка выполнения команды `{text}`."

        if response_text is None:
            return None

        # Send the handler response back to MAX
        await self._max.send_message(
            chat_id=target_chat_id,
            user_id=None,
            text=response_text,
            format="markdown",
        )
        return {"cmd": text, "http_response": web.json_response({"ok": True})}

    def _verify_signature(self, request: web.Request) -> bool:
        """Verify HMAC signature from MAX webhook.

        TODO: Implement full HMAC-SHA256 verification.
        For now, accept all requests (MAX webhook auth is via URL + token).
        """
        return True

    def _is_duplicate(self, msg_id: str) -> bool:
        """Check if a message ID was already processed (dedup within window)."""
        now = time.time()
        if msg_id in self._processed_ids:
            logger.debug("Duplicate message %s — ignoring", msg_id)
            return True
        self._processed_ids[msg_id] = now
        # Cleanup old entries when cache gets large
        if len(self._processed_ids) > DEDUP_MAX_SIZE:
            cutoff = now - DEDUP_WINDOW
            self._processed_ids = {
                k: v for k, v in self._processed_ids.items() if v > cutoff
            }
        return False

    async def _keep_typing(self, chat_id: int) -> None:
        """Keep sending typing_on every ~3 seconds until cancelled.

        The MAX 'typing_on' action only lasts ~5–10 seconds.
        This loop re-sends it periodically so the user sees
        continuous feedback while Hermes prepares the answer.
        """
        try:
            while True:
                await self._max.send_chat_action(
                    chat_id=chat_id, action="typing_on"
                )
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning(
                "Failed to send keep-typing indicator", exc_info=True
            )

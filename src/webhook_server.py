"""HTTP webhook server for receiving MAX updates."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from aiohttp import web

from max_shared.constants import GROUP_CHAT_TYPES
from max_shared.converter import MessageConverter
from max_shared.max_client import MAXClient, MAXApiError
from max_shared.models import MAXAttachment, MAXUpdate

from src.config import Config
from src.hermes_client import HermesClient, HermesClientError

logger = logging.getLogger(__name__)


class WebhookServer:
    """HTTP server that receives MAX webhook updates and routes them to Hermes."""

    def __init__(
        self,
        config: Config,
        max_client: MAXClient,
        hermes_client: HermesClient,
    ):
        self._config = config
        self._max = max_client
        self._hermes = hermes_client
        self._converter = MessageConverter()
        self._app = web.Application()
        self._app["hermes_client"] = hermes_client
        self._app["max_client"] = max_client
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

        # Access control
        if self._config.allowed_users and update.message:
            if update.message.sender.user_id not in self._config.allowed_users:
                logger.warning(
                    "Unauthorized user %d — ignoring",
                    update.message.sender.user_id,
                )
                return web.json_response({"ok": True, "ignored": True})

        # Convert and forward to Hermes
        hermes_payload = self._converter.max_update_to_message(update)

        if hermes_payload is None:
            logger.debug(
                "Update type %s not supported — skipping", update.update_type
            )
            return web.json_response({"ok": True, "skipped": True})

        try:
            # Send typing indicator
            if update.message:
                recipient = update.message.recipient
                await self._max.send_chat_action(
                    chat_id=recipient.chat_id, action="typing_on"
                )

            # Download attachments
            content_items = []
            if update.message and update.message.body.attachments:
                content_items = await self._download_attachments(
                    update.message.body.attachments
                )
                if content_items:
                    hermes_payload["content_items"] = content_items

            # Send to Hermes
            hermes_response = await self._hermes.send_message(**hermes_payload)

            # Send response back to MAX
            agent_text = hermes_response.get(
                "message", hermes_response.get("text", "")
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
                )
                logger.info("MAX send_message payload: %s", max_msg)
                await self._max.send_message(**max_msg)

            return web.json_response({"ok": True})

        except HermesClientError as e:
            logger.error("Hermes error: %s", e)
            return web.json_response({"ok": True, "hermes_error": str(e)})

        except MAXApiError as e:
            logger.error("MAX API error sending response: %s", e)
            return web.json_response({"ok": True, "max_error": str(e)})

        except Exception as e:
            logger.exception("Unexpected error processing update: %s", e)
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

    def _verify_signature(self, request: web.Request) -> bool:
        """Verify HMAC signature from MAX webhook.

        TODO: Implement full HMAC-SHA256 verification.
        For now, accept all requests (MAX webhook auth is via URL + token).
        """
        return True

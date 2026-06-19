"""HTTP webhook server for receiving MAX updates."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from aiohttp import web

from src.config import Config
from src.converter import MessageConverter
from src.hermes_client import HermesClient, HermesClientError
from src.max_client import MAXClient, MAXApiError
from src.models import MAXUpdate

logger = logging.getLogger(__name__)


class WebhookServer:
    """HTTP server that receives MAX webhook updates and routes them to Hermes."""

    def __init__(self, config: Config, max_client: MAXClient, hermes_client: HermesClient):
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
        # ── Auth ─────────────────────────────────────────────────────────
        if not self._verify_signature(request):
            logger.warning("Invalid webhook signature from %s", request.remote)
            return web.json_response({"error": "Invalid signature"}, status=401)

        # ── Parse payload ────────────────────────────────────────────────
        try:
            raw_body = await request.read()
            data = json.loads(raw_body)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Failed to parse webhook body: %s", e)
            return web.json_response({"error": "Invalid JSON"}, status=400)

        logger.debug("Raw MAX payload: %s", raw_body[:2000])

        # ── Process update ───────────────────────────────────────────────
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

        # ── Access control ───────────────────────────────────────────────
        if self._config.allowed_users and update.message:
            if update.message.sender.user_id not in self._config.allowed_users:
                logger.warning(
                    "Unauthorized user %d — ignoring",
                    update.message.sender.user_id,
                )
                return web.json_response({"ok": True, "ignored": True})

        # ── Convert and forward to Hermes ────────────────────────────────
        hermes_payload = self._converter.max_update_to_hermes_message(update)

        if hermes_payload is None:
            logger.debug("Update type %s not supported — skipping", update.update_type)
            return web.json_response({"ok": True, "skipped": True})

        try:
            # Send typing indicator to MAX while Hermes is thinking
            if update.message:
                recipient = update.message.recipient
                await self._max.send_chat_action(chat_id=recipient.chat_id, action="typing_on")

            # Send to Hermes webhook and get agent response
            hermes_response = await self._hermes.send_message(**hermes_payload)

            # Extract agent response text
            agent_text = hermes_response.get("message", hermes_response.get("text", ""))

            if agent_text and update.message:
                # Send response back to MAX
                # In dialogs: recipient.user_id = bot's ID, sender.user_id = user's ID
                # We need the user's ID to send the reply
                recipient = update.message.recipient
                sender = update.message.sender
                # Always use sender.user_id for dialogs (the human who wrote)
                # recipient.user_id in dialogs is the bot itself
                target_user_id = sender.user_id
                logger.info(
                    "Sending response to MAX: chat_id=%s, user_id=%s, text_len=%d",
                    recipient.chat_id,
                    target_user_id,
                    len(agent_text),
                )
                max_msg = self._converter.hermes_response_to_max_message(
                    hermes_response,
                    chat_id=recipient.chat_id,
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

    # ── Auth ───────────────────────────────────────────────────────────────

    def _verify_signature(self, request: web.Request) -> bool:
        """Verify HMAC signature from MAX webhook.

        MAX may not send signatures in all cases. If no signature is present
        and a secret is configured, we still accept (for compatibility).
        In production, implement full HMAC-SHA256 verification.
        """
        # TODO: Implement full HMAC-SHA256 signature verification
        # For now, accept all requests (MAX webhook auth is via URL + token)
        return True

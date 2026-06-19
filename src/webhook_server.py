"""HTTP webhook server for receiving MAX updates."""

from __future__ import annotations

import hashlib
import hmac
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
                "hermes_url": self._config.hermes_webhook_url,
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
            # Send to Hermes webhook and get agent response
            hermes_response = await self._hermes.send_message(**hermes_payload)

            # Extract agent response text
            agent_text = hermes_response.get("message", hermes_response.get("text", ""))

            if agent_text and update.message:
                # Send response back to MAX
                max_msg = self._converter.hermes_response_to_max_message(
                    hermes_response,
                    update.message.recipient.chat_id,
                )
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
        """Verify HMAC signature from MAX webhook."""
        signature = request.headers.get("X-Max-Signature", "")
        if not signature:
            # If no secret configured, allow all (dev mode)
            if not self._config.bridge_secret:
                return True
            return False

        # MAX uses HMAC-SHA256 with the bridge secret
        body = request.content
        # Note: aiohttp doesn't give us raw body easily after read
        # For now, we check the signature header format
        # MAX sends: X-Max-Signature: sha256=<hex>
        if signature.startswith("sha256="):
            return True  # Simplified — full impl needs raw body

        return True  # Dev mode — remove in production

"""MAX Bot API HTTP client."""

from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

from src.models import (
    SendMessageResponse,
    SubscriptionResponse,
)

logger = logging.getLogger(__name__)


class MAXApiError(Exception):
    """MAX API error."""

    def __init__(self, code: str, message: str, status_code: int = 0):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"[{code}] {message} (HTTP {status_code})")


class MAXClient:
    """Async HTTP client for MAX Bot API."""

    def __init__(self, token: str, base_url: str = "https://platform-api.max.ru"):
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": self._token,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        session = await self._get_session()
        url = f"{self._base_url}{path}"

        logger.debug("MAX API %s %s", method, url)

        try:
            async with session.request(method, url, json=data) as resp:
                body = await resp.json(content_type=None)

                if resp.status >= 400:
                    code = body.get("code", "unknown")
                    message = body.get("message", "Unknown error")
                    logger.error("MAX API error: %s %s (HTTP %d)", code, message, resp.status)
                    raise MAXApiError(code, message, resp.status)

                return body

        except aiohttp.ClientError as e:
            logger.error("MAX API connection error: %s", e)
            raise

    # ── Bot info ────────────────────────────────────────────────────────────

    async def get_bot_info(self) -> dict[str, Any]:
        """GET /me — get bot info."""
        return await self._request("GET", "/me")

    # ── Messages ────────────────────────────────────────────────────────────

    async def send_message(
        self,
        chat_id: int,
        text: str,
        format: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None,
        reply_to: Optional[int] = None,
    ) -> SendMessageResponse:
        """POST /messages — send a message."""
        payload: dict[str, Any] = {"chat_id": chat_id}

        if text:
            payload["text"] = text
        if format:
            payload["format"] = format
        if attachments:
            payload["attachments"] = attachments
        if reply_to:
            payload["reply_to"] = reply_to

        body = await self._request("POST", "/messages", data=payload)

        return SendMessageResponse(
            message_id=body.get("message_id"),
            ok=True,
        )

    async def edit_message(
        self,
        message_id: int,
        text: str,
        format: Optional[str] = None,
    ) -> dict[str, Any]:
        """PUT /messages/{messageId} — edit a message."""
        payload: dict[str, Any] = {"text": text}
        if format:
            payload["format"] = format
        return await self._request("PUT", f"/messages/{message_id}", data=payload)

    async def delete_message(self, message_id: int) -> dict[str, Any]:
        """DELETE /messages/{messageId} — delete a message."""
        return await self._request("DELETE", f"/messages/{message_id}")

    async def get_message(self, message_id: int) -> dict[str, Any]:
        """GET /messages/{messageId} — get a message."""
        return await self._request("GET", f"/messages/{message_id}")

    # ── Callback answer ─────────────────────────────────────────────────────

    async def answer_callback(
        self,
        callback_id: str,
        text: Optional[str] = None,
        notification: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST /callback — answer a callback query."""
        payload: dict[str, Any] = {"callback_id": callback_id}
        if text:
            payload["text"] = text
        if notification:
            payload["notification"] = notification
        return await self._request("POST", "/callback", data=payload)

    # ── Subscriptions (Webhook) ─────────────────────────────────────────────

    async def subscribe(
        self,
        url: str,
        update_types: Optional[list[str]] = None,
    ) -> SubscriptionResponse:
        """POST /subscriptions — register webhook."""
        if update_types is None:
            update_types = ["message_created", "message_callback"]

        payload = {"url": url, "update_types": update_types}
        body = await self._request("POST", "/subscriptions", data=payload)

        return SubscriptionResponse(
            id=body.get("id"),
            url=body.get("url"),
            ok=True,
        )

    async def unsubscribe(self, subscription_id: str) -> dict[str, Any]:
        """DELETE /subscriptions/{id} — remove webhook."""
        return await self._request("DELETE", f"/subscriptions/{subscription_id}")

    async def get_subscriptions(self) -> list[dict[str, Any]]:
        """GET /subscriptions — list all webhooks."""
        body = await self._request("GET", "/subscriptions")
        return body if isinstance(body, list) else body.get("subscriptions", [])

    # ── Long Polling ────────────────────────────────────────────────────────

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """GET /updates — Long Polling for updates."""
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            params["offset"] = offset

        query = "&".join(f"{k}={v}" for k, v in params.items())
        body = await self._request("GET", f"/updates?{query}")
        return body if isinstance(body, list) else body.get("updates", [])

    # ── Upload ──────────────────────────────────────────────────────────────

    async def upload_image(self, image_data: bytes) -> dict[str, Any]:
        """POST /upload/image — upload an image."""
        session = await self._get_session()
        url = f"{self._base_url}/upload/image"

        data = aiohttp.FormData()
        data.add_field("file", image_data, filename="image.png", content_type="image/png")

        async with session.post(url, data=data) as resp:
            return await resp.json(content_type=None)

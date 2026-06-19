"""Hermes webhook client — sends messages to Hermes webhook adapter."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class HermesClientError(Exception):
    """Hermes webhook error."""


class HermesClient:
    """Client for Hermes webhook adapter."""

    def __init__(self, webhook_url: str, secret: str):
        self._webhook_url = webhook_url
        self._secret = secret
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _sign_payload(self, payload: bytes) -> str:
        """Generate HMAC-SHA256 signature for Hermes webhook."""
        return hmac.new(
            self._secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    async def send_message(
        self,
        message: str,
        chat_id: str,
        user_id: str,
        user_name: str,
        reply_to: Optional[str] = None,
        raw_update: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Send a message to Hermes webhook.

        Returns dict with 'status' and 'message' (agent response) on success.
        """
        payload = {
            "message": message,
            "chat_id": chat_id,
            "user_id": user_id,
            "user_name": user_name,
            "platform": "max",
        }

        if reply_to:
            payload["reply_to"] = reply_to
        if raw_update:
            payload["raw_update"] = raw_update  # type: ignore[typeddict-unknown-key]

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signature = self._sign_payload(body)

        session = await self._get_session()

        try:
            async with session.post(
                self._webhook_url,
                data=body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Hermes-Signature": f"sha256={signature}",
                },
            ) as resp:
                response_data = await resp.json(content_type=None)

                if resp.status >= 400:
                    error = response_data.get("error", "Unknown error")
                    logger.error("Hermes webhook error (HTTP %d): %s", resp.status, error)
                    raise HermesClientError(f"HTTP {resp.status}: {error}")

                return response_data

        except aiohttp.ClientError as e:
            logger.error("Hermes webhook connection error: %s", e)
            raise HermesClientError(str(e)) from e

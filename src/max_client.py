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
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        text: str = "",
        format: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None,
        reply_to: Optional[str] = None,
    ) -> SendMessageResponse:
        """POST /messages — send a message.

        For dialogs (DM): pass user_id
        For group chats: pass chat_id
        """
        logger.info("send_message: chat_id=%s, user_id=%s, text_len=%d", chat_id, user_id, len(text))

        params: dict[str, Any] = {}
        if chat_id is not None:
            params["chat_id"] = str(chat_id)
        if user_id is not None:
            params["user_id"] = str(user_id)

        payload: dict[str, Any] = {}
        if text:
            payload["text"] = text
        if format:
            payload["format"] = format
        if attachments:
            payload["attachments"] = attachments
        if reply_to:
            payload["reply_to"] = reply_to

        if not params:
            logger.error("send_message called without chat_id or user_id")
            raise MAXApiError("validation", "Either chat_id or user_id must be provided", 400)

        query = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"/messages?{query}" if query else "/messages"

        body = await self._request("POST", path, data=payload)

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

    # ── Chat actions ──────────────────────────────────────────────────────────

    async def send_chat_action(
        self,
        chat_id: int,
        action: str = "typing_on",
    ) -> dict[str, Any]:
        """POST /chats/{chatId}/actions — send chat action (e.g. typing indicator).

        Common actions: 'typing_on', 'typing_off'
        """
        payload = {"action": action}
        return await self._request("POST", f"/chats/{chat_id}/actions", data=payload)

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

    async def upload_audio(
        self,
        audio_data: bytes,
        file_name: str = "audio.ogg",
        content_type: str = "audio/ogg",
    ) -> dict[str, Any]:
        """POST /uploads — upload an audio file (voice message).

        MAX Bot API accepts audio in OGG/Opus format.
        Returns dict with attachment_id / token on success.

        Example response:
            {"attachment_id": "abc123", "token": "xyz789"}
        """
        session = await self._get_session()
        url = f"{self._base_url}/uploads"

        data = aiohttp.FormData()
        data.add_field("file", audio_data, filename=file_name, content_type=content_type)

        logger.info("Uploading audio: %s (%d bytes)", file_name, len(audio_data))

        async with session.post(url, data=data) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                code = body.get("code", "unknown")
                message = body.get("message", "Unknown error")
                raise MAXApiError(code, message, resp.status)
            logger.info("Audio upload response: %s", body)
            return body

    async def upload_file(
        self,
        file_data: bytes,
        file_name: str = "file",
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """POST /uploads — upload a generic file.

        Returns dict with attachment_id on success.
        """
        session = await self._get_session()
        url = f"{self._base_url}/uploads"

        data = aiohttp.FormData()
        data.add_field("file", file_data, filename=file_name, content_type=content_type)

        logger.info("Uploading file: %s (%d bytes)", file_name, len(file_data))

        async with session.post(url, data=data) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                code = body.get("code", "unknown")
                message = body.get("message", "Unknown error")
                raise MAXApiError(code, message, resp.status)
            logger.info("Upload response: %s", body)
            return body

    # ── Send media messages ─────────────────────────────────────────────────

    async def send_audio_message(
        self,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        audio_token: str = "",
        text: str = "",
        reply_to: Optional[str] = None,
    ) -> SendMessageResponse:
        """POST /messages with audio attachment — send a voice message.

        Args:
            chat_id: Group chat ID (for groups)
            user_id: User ID (for DMs)
            audio_token: Token from upload_audio response
            text: Optional caption text
            reply_to: Message ID to reply to
        """
        attachments = [{
            "type": "audio",
            "payload": {"token": audio_token},
        }]
        return await self.send_message(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            reply_to=reply_to,
        )

    async def send_image_message(
        self,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        image_token: str = "",
        text: str = "",
        reply_to: Optional[str] = None,
    ) -> SendMessageResponse:
        """POST /messages with image attachment — send an image.

        Args:
            chat_id: Group chat ID (for groups)
            user_id: User ID (for DMs)
            image_token: Token from upload_image response
            text: Optional caption text
            reply_to: Message ID to reply to
        """
        attachments = [{
            "type": "image",
            "payload": {"token": image_token},
        }]
        return await self.send_message(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            reply_to=reply_to,
        )

    async def send_file_message(
        self,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        file_token: str = "",
        file_name: str = "",
        text: str = "",
        reply_to: Optional[str] = None,
    ) -> SendMessageResponse:
        """POST /messages with file attachment — send a generic file.

        Args:
            chat_id: Group chat ID (for groups)
            user_id: User ID (for DMs)
            file_token: Token from upload_file response
            file_name: Original filename (shown to user)
            text: Optional caption text
            reply_to: Message ID to reply to
        """
        payload = {"token": file_token}
        if file_name:
            payload["name"] = file_name
        attachments = [{
            "type": "file",
            "payload": payload,
        }]
        return await self.send_message(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            reply_to=reply_to,
        )

    # ── Download attachments ────────────────────────────────────────────────

    async def download_attachment(
        self,
        url: str,
        token: Optional[str] = None,
    ) -> bytes:
        """Download an attachment from MAX CDN.

        Args:
            url: The attachment URL from MAX API payload.
            token: Optional access token for authenticated download.

        Returns:
            Raw bytes of the downloaded file.
        """
        session = await self._get_session()

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        logger.debug("Downloading attachment: %s", url[:100])

        async with session.get(url, headers=headers) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise MAXApiError(
                    "download_failed",
                    f"HTTP {resp.status}: {body[:200]}",
                    resp.status,
                )
            data = await resp.read()
            logger.info("Downloaded attachment: %s (%d bytes)", url[:80], len(data))
            return data

    async def download_attachment_to_file(
        self,
        url: str,
        dest_path: str,
        token: Optional[str] = None,
    ) -> str:
        """Download an attachment and save to a local file.

        Args:
            url: The attachment URL.
            dest_path: Local file path to save to.
            token: Optional access token.

        Returns:
            Absolute path to the saved file.
        """
        import os

        data = await self.download_attachment(url, token=token)

        dest = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        with open(dest, "wb") as f:
            f.write(data)

        logger.info("Saved attachment to: %s (%d bytes)", dest, len(data))
        return dest

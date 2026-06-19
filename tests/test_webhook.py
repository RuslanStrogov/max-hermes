"""Tests for webhook server."""

import json
import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Config
from src.hermes_client import HermesClient
from src.max_client import MAXClient
from src.webhook_server import WebhookServer


@pytest.fixture
def config():
    return Config(
        max_bot_token="test-token",
        hermes_webhook_url="http://localhost:8644/webhooks/max-bot",
        hermes_webhook_secret="test-secret",
        bridge_secret="",
    )


@pytest.fixture
def max_client():
    client = AsyncMock(spec=MAXClient)
    return client


@pytest.fixture
def hermes_client():
    client = AsyncMock(spec=HermesClient)
    return client


@pytest.fixture
def server(config, max_client, hermes_client):
    return WebhookServer(config, max_client, hermes_client)


class TestWebhookServer(AioHTTPTestCase):
    async def get_application(self):
        config = Config(
            max_bot_token="test-token",
            hermes_webhook_url="http://localhost:8644/webhooks/max-bot",
            hermes_webhook_secret="test-secret",
            bridge_secret="",
        )
        max_client = AsyncMock(spec=MAXClient)
        hermes_client = AsyncMock(spec=HermesClient)
        server = WebhookServer(config, max_client, hermes_client)
        return server.app

    @unittest_run_loop
    async def test_health(self):
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"

    @unittest_run_loop
    async def test_webhook_message_created(self):
        payload = {
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": 12345, "name": "Иван"},
                "recipient": {"chat_id": 67890, "type": "dialog", "user_id": 12345},
                "body": {"text": "Привет", "mid": "msg_123"},
                "timestamp": 1737500130100,
            },
            "timestamp": 1737500130100,
        }

        # Mock Hermes response
        hermes_resp = {"message": "Привет! Как дела?"}
        self.app["hermes_client"].send_message = AsyncMock(return_value=hermes_resp)
        self.app["max_client"].send_message = AsyncMock()

        resp = await self.client.request(
            "POST",
            "/webhook",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200

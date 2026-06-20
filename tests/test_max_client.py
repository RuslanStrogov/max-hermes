"""Tests for MAX client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from max_shared.max_client import MAXClient, MAXApiError
from max_shared.models import SendMessageResponse


@pytest.fixture
def client():
    return MAXClient(token="test-token")


@pytest.mark.asyncio
async def test_get_bot_info(client):
    mock_response = {
        "user_id": 123,
        "name": "Test Bot",
        "username": "test_bot",
        "is_bot": True,
    }

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await client.get_bot_info()
        assert result["name"] == "Test Bot"
        mock_req.assert_called_once_with("GET", "/me")


@pytest.mark.asyncio
async def test_send_message(client):
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"message_id": "msg_123"}
        result = await client.send_message(
            chat_id=456,
            text="Hello",
            format="markdown",
        )
        assert result.ok is True
        assert result.message_id == "msg_123"


@pytest.mark.asyncio
async def test_api_error(client):
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = MAXApiError("unauthorized", "Invalid token", 401)
        with pytest.raises(MAXApiError):
            await client.get_bot_info()

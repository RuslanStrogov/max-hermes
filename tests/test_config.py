"""Test configuration."""

import pytest

from src.config import Config


class TestConfig:
    def test_default_config(self):
        config = Config()
        assert config.max_api_base_url == "https://platform-api.max.ru"
        assert config.bridge_port == 8787

    def test_validate_missing_token(self):
        config = Config(max_bot_token="")
        errors = config.validate()
        assert any("MAX_BOT_TOKEN" in e for e in errors)

    def test_validate_missing_hermes_url(self):
        config = Config(max_bot_token="test", hermes_webhook_url="")
        errors = config.validate()
        assert any("HERMES_WEBHOOK_URL" in e for e in errors)

    def test_validate_bad_port(self):
        config = Config(max_bot_token="test", bridge_port=99999)
        errors = config.validate()
        assert any("BRIDGE_PORT" in e for e in errors)

    def test_allowed_users_parsing(self):
        import os
        os.environ["ALLOWED_USERS"] = "123,456,789"
        config = Config.from_env()
        assert config.allowed_users == {123, 456, 789}
        del os.environ["ALLOWED_USERS"]

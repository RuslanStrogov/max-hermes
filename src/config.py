"""Configuration loader for MAX Bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env from project root or /etc/max-bridge/."""
    # Try project root first
    project_env = Path(__file__).resolve().parent.parent / ".env"
    if project_env.exists():
        load_dotenv(project_env)
        return

    # Try system config
    system_env = Path("/etc/max-bridge/.env")
    if system_env.exists():
        load_dotenv(system_env)
        return

    # Try environment only
    load_dotenv()


_load_env()


@dataclass(frozen=True)
class Config:
    """Bridge configuration."""

    # MAX Bot API
    max_bot_token: str = ""
    max_api_base_url: str = "https://platform-api.max.ru"

    # Hermes webhook
    hermes_webhook_url: str = "http://127.0.0.1:8644/webhooks/max-bot"
    hermes_webhook_secret: str = "max-bridge-secret"

    # Bridge HTTP server
    bridge_host: str = "0.0.0.0"
    bridge_port: int = 8787
    bridge_secret: str = "max-bridge-secret"

    # Logging
    log_level: str = "INFO"
    log_file: str = "/var/log/max-bridge/bridge.log"

    # Access control
    allowed_users: set[int] = field(default_factory=set)

    @classmethod
    def from_env(cls) -> Config:
        """Create Config from environment variables."""
        allowed_users_raw = os.getenv("ALLOWED_USERS", "").strip()
        allowed_users = set()
        if allowed_users_raw:
            allowed_users = {int(u.strip()) for u in allowed_users_raw.split(",") if u.strip()}

        return cls(
            max_bot_token=os.getenv("MAX_BOT_TOKEN", "").strip(),
            max_api_base_url=os.getenv("MAX_API_BASE_URL", "https://platform-api.max.ru").strip(),
            hermes_webhook_url=os.getenv("HERMES_WEBHOOK_URL", "http://127.0.0.1:8644/webhooks/max-bot").strip(),
            hermes_webhook_secret=os.getenv("HERMES_WEBHOOK_SECRET", "max-bridge-secret").strip(),
            bridge_host=os.getenv("BRIDGE_HOST", "0.0.0.0").strip(),
            bridge_port=int(os.getenv("BRIDGE_PORT", "8787")),
            bridge_secret=os.getenv("BRIDGE_SECRET", "max-bridge-secret").strip(),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip(),
            log_file=os.getenv("LOG_FILE", "/var/log/max-bridge/bridge.log").strip(),
            allowed_users=allowed_users,
        )

    def validate(self) -> list[str]:
        """Validate config, return list of errors."""
        errors = []
        if not self.max_bot_token:
            errors.append("MAX_BOT_TOKEN is required")
        if not self.hermes_webhook_url:
            errors.append("HERMES_WEBHOOK_URL is required")
        if not self.hermes_webhook_secret:
            errors.append("HERMES_WEBHOOK_SECRET is required")
        if self.bridge_port < 1 or self.bridge_port > 65535:
            errors.append(f"BRIDGE_PORT {self.bridge_port} is out of range")
        return errors

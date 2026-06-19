"""MAX-Hermes Bridge — main entry point.

Receives webhook updates from MAX Bot API, forwards them to Hermes Agent
via webhook, and sends agent responses back to MAX.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import signal
import sys
from pathlib import Path

from aiohttp import web

from src.config import Config
from src.hermes_client import HermesClient
from src.max_client import MAXClient
from src.webhook_server import WebhookServer


def setup_logging(config: Config) -> None:
    """Configure logging."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if config.log_file:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            config.log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        )
        file_handler.setFormatter(file_fmt)
        root_logger.addHandler(file_handler)


async def setup_max_webhook(max_client: MAXClient, bridge_url: str) -> None:
    """Register webhook subscription in MAX API."""
    logger = logging.getLogger("setup")

    try:
        # Check existing subscriptions
        subs = await max_client.get_subscriptions()
        logger.info("Existing subscriptions: %d", len(subs))

        # Check if already registered
        for sub in subs:
            if sub.get("url") == bridge_url:
                logger.info("Webhook already registered: %s", bridge_url)
                return

        # Register new subscription
        result = await max_client.subscribe(
            url=bridge_url,
            update_types=[
                "message_created",
                "message_edited",
                "message_callback",
                "bot_started",
            ],
        )
        logger.info("Webhook registered: %s (id=%s)", result.url, result.id)

    except Exception as e:
        logger.error("Failed to setup MAX webhook: %s", e)
        raise


async def create_app(config: Config) -> tuple[web.Application, MAXClient, HermesClient]:
    """Create and configure the bridge application."""
    # Clients
    max_client = MAXClient(
        token=config.max_bot_token,
        base_url=config.max_api_base_url,
    )

    hermes_client = HermesClient(
        hermes_bin=config.hermes_bin,
        model=config.hermes_model,
        timeout=config.hermes_timeout,
    )

    # Webhook server
    server = WebhookServer(
        config=config,
        max_client=max_client,
        hermes_client=hermes_client,
    )

    return server.app, max_client, hermes_client


async def main() -> None:
    """Main entry point."""
    # Load config
    config = Config.from_env()

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger("main")

    logger.info("=" * 60)
    logger.info("MAX-Hermes Bridge starting...")
    logger.info("=" * 60)

    # Validate config
    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        sys.exit(1)

    logger.info("MAX API: %s", config.max_api_base_url)
    logger.info("Hermes webhook: %s", config.hermes_webhook_url)
    logger.info("Bridge: %s:%d", config.bridge_host, config.bridge_port)

    # Create app
    app, max_client, hermes_client = await create_app(config)

    # Test MAX API connection
    try:
        bot_info = await max_client.get_bot_info()
        logger.info("Bot info: %s (@%s)", bot_info.get("name"), bot_info.get("username"))
    except Exception as e:
        logger.error("Failed to connect to MAX API: %s", e)
        sys.exit(1)

    # Setup webhook (if bridge is publicly accessible)
    bridge_url = f"http://localhost:{config.bridge_port}/webhook"
    # For production, replace with your public URL:
    # bridge_url = "https://your-domain.com/webhook"
    try:
        await setup_max_webhook(max_client, bridge_url)
    except Exception as e:
        logger.warning("Webhook setup failed (will use Long Polling): %s", e)

    # Run HTTP server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.bridge_host, config.bridge_port)

    await site.start()
    logger.info("Bridge server listening on %s:%d", config.bridge_host, config.bridge_port)

    # Graceful shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Wait for shutdown
    try:
        await shutdown_event.wait()
    finally:
        logger.info("Shutting down...")
        await max_client.close()
        await hermes_client.close()
        await runner.cleanup()
        logger.info("Bridge stopped.")


if __name__ == "__main__":
    asyncio.run(main())

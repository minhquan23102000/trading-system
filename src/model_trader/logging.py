"""Centralized loguru configuration for model_trader.

External notification sinks (Telegram, Discord, Slack, generic webhook) are
wired up as no-op stubs here. Each is enabled by setting its env var(s); when
unset, the sink is skipped entirely. Fill in the request logic later without
touching call sites — every `logger.error(...)`/`logger.success(...)` call
already routes through these.
"""

import os
import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_dir: Path | None = None, level: str = "INFO") -> None:
    """Setup loguru with rotation, console output, and notification sinks.

    Args:
        log_dir: Directory for log files. If None, file logging disabled.
        level: Log level for console output (default "INFO").
    """
    # Remove default handler
    logger.remove()

    # Console: INFO+, human-readable format
    logger.add(
        sys.stderr,
        level=level,
        format="{time:HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
    )

    # File: DEBUG+ with rotation (7 days, 500MB)
    if log_dir:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "model_trader.log"
            logger.add(
                str(log_file),
                level="DEBUG",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
                rotation="500 MB",
                retention="7 days",
            )
        except (OSError, PermissionError):
            # Fall back to console-only if log directory cannot be created
            logger.warning(f"Cannot write to {log_dir}, logging to console only")

    # External notification sinks: ERROR+ by default. Each sink checks its
    # own env var and no-ops when not configured.
    logger.add(telegram_sink, level="ERROR", format="{message}")
    logger.add(discord_sink, level="ERROR", format="{message}")
    logger.add(slack_sink, level="ERROR", format="{message}")
    logger.add(webhook_sink, level="ERROR", format="{message}")


def telegram_sink(message: str) -> None:
    """Send a log message to Telegram via bot API.

    Enable by setting TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    No-op (not yet implemented) when unset.

    Args:
        message: Formatted log message.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    # TODO: POST to https://api.telegram.org/bot{token}/sendMessage


def discord_sink(message: str) -> None:
    """Send a log message to a Discord channel via webhook.

    Enable by setting DISCORD_WEBHOOK_URL.
    No-op (not yet implemented) when unset.

    Args:
        message: Formatted log message.
    """
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return
    # TODO: POST {"content": message} to url


def slack_sink(message: str) -> None:
    """Send a log message to a Slack channel via incoming webhook.

    Enable by setting SLACK_WEBHOOK_URL.
    No-op (not yet implemented) when unset.

    Args:
        message: Formatted log message.
    """
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return
    # TODO: POST {"text": message} to url


def webhook_sink(message: str) -> None:
    """Send a log message to a generic JSON webhook.

    Enable by setting NOTIFY_WEBHOOK_URL.
    No-op (not yet implemented) when unset.

    Args:
        message: Formatted log message.
    """
    url = os.environ.get("NOTIFY_WEBHOOK_URL")
    if not url:
        return
    # TODO: POST {"message": message} to url


# Initialize logging on module import
configure_logging(log_dir=Path.home() / ".model_trader" / "logs")

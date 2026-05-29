"""Loguru bootstrap shared by CLIs."""

from __future__ import annotations

import sys

from loguru import logger

from backend.settings import get_settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=get_settings().harness_log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
        "<cyan>{name}</cyan> - <level>{message}</level>",
    )

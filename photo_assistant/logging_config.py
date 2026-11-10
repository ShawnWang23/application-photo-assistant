from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def user_log_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", Path.home()))
    return base / "ApplicationPhotoAssistant" / "logs"


def configure_logging() -> logging.Logger:
    """Create a rotating diagnostic log without recording photo bytes or API keys."""

    logger = logging.getLogger("photo_assistant")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        directory = user_log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "application.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


LOGGER = configure_logging()

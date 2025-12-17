"""Logging configuration for the application.

Provides configurable logging with debug mode support.
"""
import logging
import sys
from typing import Optional

from ..config import get_settings


def setup_logging(debug: Optional[bool] = None) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        debug: Override debug setting. If None, uses settings.debug.

    Returns:
        Configured logger instance.
    """
    settings = get_settings()
    is_debug = debug if debug is not None else settings.debug

    # Create logger
    logger = logging.getLogger("warframe_market_analyzer")

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Set level based on debug mode
    logger.setLevel(logging.DEBUG if is_debug else logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if is_debug else logging.INFO)

    # Format
    if is_debug:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the application logger.

    Returns:
        The configured logger instance.
    """
    logger = logging.getLogger("warframe_market_analyzer")
    if not logger.handlers:
        return setup_logging()
    return logger

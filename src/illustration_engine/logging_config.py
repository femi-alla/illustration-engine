"""Structured JSON logging so CloudWatch Logs Insights can query fields directly."""

from __future__ import annotations

import logging
import os
import sys

from pythonjsonlogger.json import JsonFormatter


def configure_logging(level: str | None = None) -> None:
    """Route all loggers (including uvicorn's) through one JSON handler."""
    level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level_name)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(noisy)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

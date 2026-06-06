# -*- coding: utf-8 -*-
"""Cấu hình logging dùng chung."""

import logging

LOG_LEVEL: int = logging.INFO
LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def get_logging_config(level: int = LOG_LEVEL) -> dict[str, object]:
    """Trả về dictConfig logging đơn giản cho script và service."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
                "datefmt": DATE_FORMAT,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
    }

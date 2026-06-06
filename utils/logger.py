# -*- coding: utf-8 -*-
"""Helper tạo logger dùng lại trong các module."""

import logging
import logging.config

from configs.logging import get_logging_config


def setup_logging(level: int = logging.INFO) -> None:
    """Khởi tạo logging console với format thống nhất."""
    logging.config.dictConfig(get_logging_config(level=level))


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Trả về logger theo tên module và đảm bảo logging đã được cấu hình."""
    setup_logging(level=level)
    return logging.getLogger(name)

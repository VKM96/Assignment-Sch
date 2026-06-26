"""
server_logging.py - centralized logging configuration for the server

This module configures structured logging for the server and provides helpers
for named loggers and access-control-aware logging filters.
"""

import logging
import os
from typing import Any, Dict, Optional


class AccessControlFilter(logging.Filter):
    """
    A logging filter that can restrict records based on client or role metadata.

    This is a reusable extension point for future access-controlled logging.
    """

    def __init__(self, allowed_clients: Optional[set] = None, allowed_roles: Optional[set] = None):
        super().__init__()
        self.allowed_clients = set(allowed_clients or [])
        self.allowed_roles = set(allowed_roles or [])

    def filter(self, record: logging.LogRecord) -> bool:
        if self.allowed_clients and getattr(record, "client_id", None) not in self.allowed_clients:
            return False
        if self.allowed_roles and getattr(record, "role", None) not in self.allowed_roles:
            return False
        return True


def configure_logging(config: Dict[str, Any], logger_name: str = "server", level: int = logging.INFO, access_filter: Optional[logging.Filter] = None) -> logging.Logger:
    """
    Configure root logging handlers from server configuration.

    Args:
        config: Server configuration dict containing `log_dir` and `log_file`.
        logger_name: Name of the logger returned by this helper.
        level: Default logging level.
        access_filter: Optional logging filter to apply to handlers.

    Returns:
        logging.Logger: Named logger instance for the server.
    """
    log_dir = config.get("log_dir", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, config.get("log_file", "server.log"))

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    if access_filter is not None:
        file_handler.addFilter(access_filter)
        stream_handler.addFilter(access_filter)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    return get_logger(logger_name)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a named logger for the application.

    Args:
        name: Optional logger name. Defaults to "server".
    """
    return logging.getLogger(name if name else "server")


def get_logger_adapter(logger: logging.Logger, extra: Optional[Dict[str, Any]] = None) -> logging.LoggerAdapter:
    """
    Return a LoggerAdapter that can attach contextual metadata to log records.
    """
    return logging.LoggerAdapter(logger, extra or {})

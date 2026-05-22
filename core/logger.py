import logging
import os
import sys
from datetime import datetime

_logger: logging.Logger | None = None
_log_path: str | None = None


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    global _logger, _log_path

    log_dir = os.path.join(os.getenv("APPDATA", ""), "voice_input")
    os.makedirs(log_dir, exist_ok=True)
    _log_path = os.path.join(log_dir, "voice_input.log")

    _logger = logging.getLogger("voice_input")
    _logger.setLevel(level)

    if _logger.handlers:
        _logger.handlers.clear()

    file_handler = logging.FileHandler(_log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    _logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    _logger.addHandler(console_handler)

    _logger.debug("=" * 60)
    _logger.debug("Voice Input 启动")
    _logger.debug(f"Python: {sys.version}")
    _logger.debug(f"日志文件: {_log_path}")

    return _logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return setup_logging()
    return _logger


def get_log_path() -> str | None:
    return _log_path

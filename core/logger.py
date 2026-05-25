import logging
import os
import sys

_logger: logging.Logger | None = None
_log_path: str | None = None

LOG_LEVELS = {
    "OFF": None,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def normalize_log_level(level: int | str | None) -> str:
    if isinstance(level, int):
        for name, value in LOG_LEVELS.items():
            if value == level:
                return name
        return "DEBUG"

    name = str(level or "OFF").strip().upper()
    return name if name in LOG_LEVELS else "OFF"


def setup_logging(level: int | str | None = "OFF") -> logging.Logger:
    global _logger, _log_path

    _logger = logging.getLogger("voice_input")
    _logger.disabled = False
    _logger.propagate = False

    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)
        handler.close()

    level_name = normalize_log_level(level)
    numeric_level = LOG_LEVELS[level_name]
    if numeric_level is None:
        _log_path = None
        _logger.setLevel(logging.CRITICAL + 1)
        _logger.addHandler(logging.NullHandler())
        _logger.disabled = True
        return _logger

    log_dir = os.path.join(os.getenv("APPDATA", ""), "voice_input")
    os.makedirs(log_dir, exist_ok=True)
    _log_path = os.path.join(log_dir, "voice_input.log")

    _logger.setLevel(numeric_level)

    file_handler = logging.FileHandler(_log_path, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    _logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(max(numeric_level, logging.INFO))
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    _logger.addHandler(console_handler)

    _logger.debug("=" * 60)
    _logger.debug("Voice Input started")
    _logger.debug(f"Python: {sys.version}")
    _logger.debug(f"Log file: {_log_path}")

    return _logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return setup_logging()
    return _logger


def get_log_path() -> str | None:
    return _log_path

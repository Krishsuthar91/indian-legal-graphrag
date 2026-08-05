"""Logging configuration using structlog (stdlib integration).

structlog is wired through the standard logging system, so every structured
entry lands in the console AND in the correct file sink.

Sinks:
  - console            all levels
  - logs/app.log       everything (aggregate)
  - logs/api.log       logger names in the api channel
  - logs/llm.log       logger names in the llm channel
  - logs/retrieval.log logger names in the retrieval channel
  - logs/error.log     logger names in the error channel (reserved)
  - logs/audit.log     logger names in the audit channel (reserved)

Rotation is enabled with settings.LOG_ROTATION_ENABLED (midnight roll,
retaining settings.LOG_BACKUP_COUNT files).
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog

from src.config.settings import settings

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# Channel -> (file name, logger names routed to that file).
CHANNELS: dict[str, tuple[str, tuple[str, ...]]] = {
    "api": ("api.log", ("api", "qa_api", "qa_service", "health")),
    "llm": ("llm.log", ("llm", "explanation", "prompts")),
    "retrieval": (
        "retrieval.log",
        ("retrieval", "retriever", "ranker", "scorer", "context", "query"),
    ),
    "error": ("error.log", ("error",)),
    "audit": ("audit.log", ("audit",)),
}

# Flatten channel name sets for quick lookup.
_CHANNEL_NAMES: dict[str, set[str]] = {
    channel: set(names) for channel, (_, names) in CHANNELS.items()
}
_CHANNEL_FILES: dict[str, str] = {
    channel: filename for channel, (filename, _) in CHANNELS.items()
}


class ChannelFilter(logging.Filter):
    """Accept only records whose logger name belongs to a channel."""

    def __init__(self, names: set[str]) -> None:
        super().__init__()
        self._names = names

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name in self._names


def _make_file_handler(filename: str, level: int, names: set[str] | None = None) -> logging.Handler:
    """Build a (optionally filtered) file handler with daily rotation support."""
    log_file = _LOG_DIR / filename
    if settings.LOG_ROTATION_ENABLED:
        handler: logging.Handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    else:
        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    handler.setLevel(level)
    if names is not None:
        handler.addFilter(ChannelFilter(names))
    return handler


def _make_formatter() -> structlog.stdlib.ProcessorFormatter:
    """Shared formatter rendering structlog events as JSON in files."""
    return structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog and the console + per-channel rotating file handlers."""
    log_level = logging.getLevelName(level.upper())
    if not isinstance(log_level, int):
        log_level = logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    file_formatter = _make_formatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    app_handler = _make_file_handler("app.log", log_level)
    app_handler.setFormatter(file_formatter)
    root_logger.addHandler(app_handler)

    for channel, filename in _CHANNEL_FILES.items():
        handler = _make_file_handler(filename, log_level, names=_CHANNEL_NAMES[channel])
        handler.setFormatter(file_formatter)
        root_logger.addHandler(handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a bound logger instance routed to a channel by its name."""
    return structlog.get_logger(name)

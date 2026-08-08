"""Privacy-safe local diagnostics for application startup failures."""

from __future__ import annotations

import logging
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType


_LOGGER = logging.getLogger("dscode_assistant.diagnostics")
_LOGGER.setLevel(logging.ERROR)
_LOGGER.propagate = False


def configure_exception_logging(data_dir: Path) -> Path:
    """Configure a small local error log without request or message content."""
    log_directory = data_dir / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "errors.log"

    for handler in list(_LOGGER.handlers):
        handler.close()
        _LOGGER.removeHandler(handler)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=512_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _LOGGER.addHandler(handler)
    return log_path


def record_exception(
    exception_type: type[BaseException],
    traceback_value: TracebackType | None,
) -> None:
    """Record only exception type and stack locations, never exception text."""
    frames = traceback.extract_tb(traceback_value) if traceback_value else []
    locations = " > ".join(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames
    )
    _LOGGER.error(
        "Unhandled %s%s",
        exception_type.__name__,
        f" at {locations}" if locations else "",
    )


def shutdown_exception_logging() -> None:
    """Flush and close local diagnostic file handles."""
    for handler in list(_LOGGER.handlers):
        handler.flush()
        handler.close()
        _LOGGER.removeHandler(handler)

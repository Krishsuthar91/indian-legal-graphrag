"""General utility helpers."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Generator
from contextlib import contextmanager


def generate_id() -> str:
    """Generate a short deterministic id from current time."""
    raw = f"{time.time_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@contextmanager
def timer(label: str = "operation") -> Generator[None, None, None]:
    """Context manager that logs elapsed time."""
    from src.config.logging_config import get_logger

    log = get_logger("helpers")
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    log.info("timer", label=label, elapsed_ms=round(elapsed * 1000, 2))


def truncate(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."

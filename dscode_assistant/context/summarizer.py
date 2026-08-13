"""Summary contract reserved for later context optimization phases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class ContextSummarizer(Protocol):
    """Contract for a future local or explicitly configured summarizer."""

    def summarize(self, messages: Sequence[Mapping[str, str]]) -> str:
        """Return a summary for the supplied messages."""
        ...


class SummaryNotAvailableError(NotImplementedError):
    """Raised when a strategy requests an unavailable summary implementation."""

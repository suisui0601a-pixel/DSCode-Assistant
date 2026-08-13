"""Context optimizer entry point and dependency-free token estimation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .models import ContextBudget, ContextResult, OptimizationLevel
from .strategies import LightStrategy, RawStrategy


class LightweightTokenEstimator:
    """Estimate tokens locally without a provider-specific tokenizer.

    The estimate is intentionally conservative and must not be presented as
    provider usage. ASCII text is approximated at four characters per token;
    non-ASCII text receives a higher weight. A small fixed message overhead is
    included for chat-protocol framing.
    """

    def __init__(self, message_overhead: int = 4) -> None:
        if message_overhead < 0:
            raise ValueError("message_overhead cannot be negative.")
        self._message_overhead = message_overhead

    def estimate_text(self, text: str) -> int:
        """Return a deterministic approximate token count for text."""
        if not text:
            return 0
        weighted_characters = sum(0.25 if char.isascii() else 0.6 for char in text)
        return max(1, math.ceil(weighted_characters))

    def estimate_messages(self, messages: Sequence[Mapping[str, str]]) -> int:
        """Estimate tokens for chat messages, including framing overhead."""
        return sum(
            self._message_overhead
            + self.estimate_text(message.get("role", ""))
            + self.estimate_text(message.get("content", ""))
            for message in messages
        )


class ContextOptimizer:
    """Prepare model messages using an explicitly selected local strategy."""

    def __init__(self, estimator: LightweightTokenEstimator | None = None) -> None:
        self._estimator = estimator or LightweightTokenEstimator()
        self._strategies = {
            OptimizationLevel.RAW: RawStrategy(),
            OptimizationLevel.LIGHT: LightStrategy(),
        }

    def prepare(
        self,
        messages: Sequence[Mapping[str, str]],
        level: OptimizationLevel = OptimizationLevel.RAW,
        budget: ContextBudget | None = None,
    ) -> ContextResult:
        """Prepare messages and return local before/after token estimates.

        ``budget`` is accepted for a stable future interface. Raw and Light do
        not truncate content to fit it because silent truncation would violate
        their deterministic, loss-minimizing contract.
        """
        try:
            normalized_level = OptimizationLevel(level)
        except ValueError as error:
            raise ValueError(f"Unsupported context optimization level: {level}") from error

        strategy = self._strategies.get(normalized_level)
        if strategy is None:
            raise NotImplementedError(
                f"Context optimization level {normalized_level.value} is not implemented."
            )

        estimated_before = self._estimator.estimate_messages(messages)
        prepared = strategy.apply(messages)
        estimated_after = self._estimator.estimate_messages(prepared)

        return ContextResult(
            messages=prepared,
            level=normalized_level,
            estimated_tokens_before=estimated_before,
            estimated_tokens_after=estimated_after,
        )

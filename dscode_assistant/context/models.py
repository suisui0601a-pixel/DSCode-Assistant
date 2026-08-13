"""Data models for deterministic context optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from .protection import ProtectionResult


class OptimizationLevel(IntEnum):
    """Available context optimization levels."""

    RAW = 0
    LIGHT = 1
    BALANCED = 2
    DEEP = 3
    EXTREME = 4


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Local input-token budget used by future optimization levels."""

    max_input_tokens: int
    reserved_output_tokens: int = 0
    target_input_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.max_input_tokens <= 0:
            raise ValueError("max_input_tokens must be positive.")
        if self.reserved_output_tokens < 0:
            raise ValueError("reserved_output_tokens cannot be negative.")
        if self.reserved_output_tokens >= self.max_input_tokens:
            raise ValueError("reserved_output_tokens must be below max_input_tokens.")
        if self.target_input_tokens is not None and not (
            0 < self.target_input_tokens
            <= self.max_input_tokens - self.reserved_output_tokens
        ):
            raise ValueError("target_input_tokens is outside the usable input budget.")

    @property
    def usable_input_tokens(self) -> int:
        """Return the input capacity left after reserving output tokens."""
        return self.max_input_tokens - self.reserved_output_tokens


@dataclass(slots=True)
class ContextResult:
    """Prepared provider messages and local token estimates."""

    messages: list[dict[str, str]]
    level: OptimizationLevel
    estimated_tokens_before: int
    estimated_tokens_after: int
    protection: ProtectionResult = field(default_factory=ProtectionResult)

    @property
    def estimated_tokens_saved(self) -> int:
        """Return the estimated reduction without allowing a negative value."""
        return max(0, self.estimated_tokens_before - self.estimated_tokens_after)

    @property
    def estimated_reduction_percent(self) -> float:
        """Return the estimated percentage saved from the original context."""
        if self.estimated_tokens_before <= 0:
            return 0.0
        return self.estimated_tokens_saved / self.estimated_tokens_before * 100.0

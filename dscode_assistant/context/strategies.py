"""Deterministic context optimization strategies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final


MessageMapping = Mapping[str, str]
PreparedMessage = dict[str, str]


class RawStrategy:
    """Copy messages without changing their order or values."""

    def apply(self, messages: Sequence[MessageMapping]) -> list[PreparedMessage]:
        return [dict(message) for message in messages]


class LightStrategy:
    """Apply small deterministic reductions without semantic rewriting."""

    _FAILED_STATUSES: Final = {"failed", "pending", "streaming"}
    _MERGEABLE_ROLES: Final = {"user", "assistant"}

    def __init__(
        self,
        short_message_limit: int = 240,
        merged_message_limit: int = 480,
    ) -> None:
        if short_message_limit <= 0 or merged_message_limit <= 0:
            raise ValueError("Light strategy limits must be positive.")
        if merged_message_limit < short_message_limit:
            raise ValueError("merged_message_limit cannot be below short_message_limit.")
        self._short_message_limit = short_message_limit
        self._merged_message_limit = merged_message_limit

    def apply(self, messages: Sequence[MessageMapping]) -> list[PreparedMessage]:
        prepared: list[PreparedMessage] = []

        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")
            status = message.get("status", "").casefold()

            if not role or not content.strip() or status in self._FAILED_STATUSES:
                continue

            current = {"role": role, "content": content}
            if prepared and prepared[-1] == current:
                continue

            if prepared and self._can_merge(prepared[-1], current):
                prepared[-1]["content"] = (
                    f"{prepared[-1]['content']}\n\n{current['content']}"
                )
                continue

            prepared.append(current)

        return prepared

    def _can_merge(
        self,
        previous: PreparedMessage,
        current: PreparedMessage,
    ) -> bool:
        if previous["role"] != current["role"]:
            return False
        if current["role"] not in self._MERGEABLE_ROLES:
            return False

        previous_content = previous["content"]
        current_content = current["content"]
        if "```" in previous_content or "```" in current_content:
            return False
        if (
            len(previous_content) > self._short_message_limit
            or len(current_content) > self._short_message_limit
        ):
            return False
        return len(previous_content) + 2 + len(current_content) <= self._merged_message_limit

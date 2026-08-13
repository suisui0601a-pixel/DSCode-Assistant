"""Deterministic context optimization strategies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from .protection import ProtectionPlan


MessageMapping = Mapping[str, str]
PreparedMessage = dict[str, str]


class RawStrategy:
    """Copy messages without changing their order or values."""

    def apply(
        self,
        messages: Sequence[MessageMapping],
        protection_plan: ProtectionPlan | None = None,
    ) -> list[PreparedMessage]:
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

    def apply(
        self,
        messages: Sequence[MessageMapping],
        protection_plan: ProtectionPlan | None = None,
    ) -> list[PreparedMessage]:
        prepared: list[PreparedMessage] = []
        plan = protection_plan or ProtectionPlan()
        pending_short_run: list[PreparedMessage] = []

        def flush_short_run() -> None:
            if not pending_short_run:
                return
            combined_length = sum(
                len(message["content"]) for message in pending_short_run
            ) + 2 * (len(pending_short_run) - 1)
            if len(pending_short_run) > 1 and combined_length <= self._merged_message_limit:
                prepared.append(
                    {
                        "role": pending_short_run[0]["role"],
                        "content": "\n\n".join(
                            message["content"] for message in pending_short_run
                        ),
                    }
                )
            else:
                prepared.extend(pending_short_run)
            pending_short_run.clear()

        for index, message in enumerate(messages):
            role = message.get("role", "")
            content = message.get("content", "")
            status = message.get("status", "").casefold()
            protected = plan.protects(index)

            if protected:
                flush_short_run()
                prepared.append({"role": role, "content": content})
                continue

            if not role or not content.strip() or status in self._FAILED_STATUSES:
                continue

            current = {"role": role, "content": content}
            if self._is_short_merge_candidate(current):
                if pending_short_run and pending_short_run[-1]["role"] != role:
                    flush_short_run()
                if pending_short_run and pending_short_run[-1] == current:
                    continue
                pending_short_run.append(current)
                continue

            flush_short_run()
            if prepared and prepared[-1] == current:
                continue
            prepared.append(current)

        flush_short_run()
        return prepared

    def _is_short_merge_candidate(self, message: PreparedMessage) -> bool:
        return (
            message["role"] in self._MERGEABLE_ROLES
            and len(message["content"]) <= self._short_message_limit
        )

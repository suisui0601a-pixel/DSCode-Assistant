"""Deterministic local rules for protecting critical context messages."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final


MessageMapping = Mapping[str, str]


class ProtectionReason(str, Enum):
    """Reasons that prevent a message from being reduced by Light mode."""

    SYSTEM = "system"
    CURRENT_TASK = "current_task"
    RECENT_RESPONSE = "recent_response"
    CODE_BLOCK = "code_block"
    PATCH = "patch"
    ERROR_LOG = "error_log"
    EXPLICIT_CONSTRAINT = "explicit_constraint"
    FILE_REFERENCE = "file_reference"


@dataclass(frozen=True, slots=True)
class ProtectedMessage:
    """An original message index and every reason it must be preserved."""

    index: int
    reasons: frozenset[ProtectionReason]

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("Protected message index cannot be negative.")
        if not self.reasons:
            raise ValueError("Protected message must have at least one reason.")


@dataclass(frozen=True, slots=True)
class ProtectionPlan:
    """Immutable protection decisions for one original message sequence."""

    protected_messages: tuple[ProtectedMessage, ...] = ()

    def protects(self, index: int) -> bool:
        """Return whether the original message at ``index`` is protected."""
        return any(message.index == index for message in self.protected_messages)

    def reasons_for(self, index: int) -> frozenset[ProtectionReason]:
        """Return all protection reasons for an original message index."""
        for message in self.protected_messages:
            if message.index == index:
                return message.reasons
        return frozenset()


class ContextProtector:
    """Inspect chat messages using local, deterministic safety rules."""

    _INVALID_STATUSES: Final = {"failed", "pending", "streaming"}
    _CODE_FENCE_PATTERN: Final = re.compile(r"(?:^|\n)\s*(?:```|~~~)")
    _PATCH_PATTERN: Final = re.compile(
        r"(?:^|\n)(?:diff --git |Index: |---\s+\S+\n\+\+\+\s+\S+|@@\s+-\d|\*\*\* Begin Patch)",
        re.IGNORECASE,
    )
    _ERROR_PATTERN: Final = re.compile(
        r"Traceback \(most recent call last\):"
        r"|\b(?:[A-Za-z_][\w.]*)?(?:Error|Exception)\b"
        r"|(?:^|\n)\s*(?:fatal\s+)?error(?:\s+[A-Z]+\d+)?\s*:"
        r"|\bcannot find symbol\b|\bundefined reference\b|\bcompilation failed\b",
        re.IGNORECASE,
    )
    _CONSTRAINT_PATTERN: Final = re.compile(
        r"必须|禁止|不要|不允许|务必|不得|保留(?:全部|现有|原始|当前)?"
        r"|\bmust(?:\s+not)?\b|\bdo\s+not\b|\bdon't\b|\bnever\b"
        r"|\brequired\b|\bforbidden\b",
        re.IGNORECASE,
    )
    _FILE_REFERENCE_PATTERN: Final = re.compile(
        r"(?:\b[A-Za-z]:[\\/]|(?<!:)\B/)(?:[^\s<>:\"|?*]+[\\/])*[^\s<>:\"|?*]+"
        r"|\b(?:[\w.-]+[\\/])+[\w.-]+\.(?:py|pyi|c|h|cc|cpp|cxx|hpp|java|js|jsx|ts|tsx|json|toml|yaml|yml|sql|md|qss|ui)\b"
        r"|\b[\w.-]+\.(?:py|pyi|c|h|cc|cpp|cxx|hpp|java|js|jsx|ts|tsx|json|toml|yaml|yml|sql|qss|ui)\b",
        re.IGNORECASE,
    )

    def inspect(self, messages: Sequence[MessageMapping]) -> ProtectionPlan:
        """Return deterministic protection decisions for ``messages``."""
        reasons_by_index: dict[int, set[ProtectionReason]] = {}

        def protect(index: int, reason: ProtectionReason) -> None:
            reasons_by_index.setdefault(index, set()).add(reason)

        for index, message in enumerate(messages):
            role = message.get("role", "")
            content = message.get("content", "")
            if not content.strip():
                continue
            if role == "system":
                protect(index, ProtectionReason.SYSTEM)
            if message.get("status", "").casefold() in self._INVALID_STATUSES:
                continue
            if self._CODE_FENCE_PATTERN.search(content):
                protect(index, ProtectionReason.CODE_BLOCK)
            if self._PATCH_PATTERN.search(content):
                protect(index, ProtectionReason.PATCH)
            if self._ERROR_PATTERN.search(content):
                protect(index, ProtectionReason.ERROR_LOG)
            if self._CONSTRAINT_PATTERN.search(content):
                protect(index, ProtectionReason.EXPLICIT_CONSTRAINT)
            if self._FILE_REFERENCE_PATTERN.search(content):
                protect(index, ProtectionReason.FILE_REFERENCE)

        current_user = self._last_valid_index(messages, "user")
        if current_user is not None:
            protect(current_user, ProtectionReason.CURRENT_TASK)

        recent_assistant = self._last_valid_index(messages, "assistant")
        if recent_assistant is not None:
            protect(recent_assistant, ProtectionReason.RECENT_RESPONSE)

        protected_messages = tuple(
            ProtectedMessage(index, frozenset(reasons_by_index[index]))
            for index in sorted(reasons_by_index)
        )
        return ProtectionPlan(protected_messages)

    def _last_valid_index(
        self,
        messages: Sequence[MessageMapping],
        role: str,
    ) -> int | None:
        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if message.get("role", "") != role:
                continue
            if not message.get("content", "").strip():
                continue
            if message.get("status", "").casefold() in self._INVALID_STATUSES:
                continue
            return index
        return None

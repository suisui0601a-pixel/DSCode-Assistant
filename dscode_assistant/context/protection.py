"""Deterministic local rules for protecting critical context messages."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from ..languages import (
    DEFAULT_LANGUAGE_PROFILES,
    LanguageDetectionReport,
    LanguageDetector,
    LanguageId,
)
from .inspection import MessageLanguageDiagnostic, ProtectionInspectionResult


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
class ProtectionReasonCount:
    """A deterministic count for one protection reason."""

    reason: ProtectionReason
    count: int

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("Protection reason count must be positive.")


@dataclass(frozen=True, slots=True)
class ProtectionResult:
    """Local observability data produced by context protection."""

    protected_message_count: int = 0
    reason_counts: tuple[ProtectionReasonCount, ...] = ()
    skipped_optimization_count: int = 0

    def __post_init__(self) -> None:
        if self.protected_message_count < 0:
            raise ValueError("Protected message count cannot be negative.")
        if self.skipped_optimization_count < 0:
            raise ValueError("Skipped optimization count cannot be negative.")
        reason_order = tuple(ProtectionReason)
        actual_reasons = tuple(item.reason for item in self.reason_counts)
        expected_reasons = tuple(
            reason for reason in reason_order if reason in actual_reasons
        )
        if len(set(actual_reasons)) != len(actual_reasons):
            raise ValueError("Protection reason counts cannot contain duplicates.")
        if actual_reasons != expected_reasons:
            raise ValueError("Protection reason counts must use deterministic order.")

    def count_for(self, reason: ProtectionReason) -> int:
        """Return the number of messages protected for ``reason``."""
        for item in self.reason_counts:
            if item.reason == reason:
                return item.count
        return 0

    @property
    def total_reason_matches(self) -> int:
        """Return all reason matches, including multiple reasons per message."""
        return sum(item.count for item in self.reason_counts)


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

    @property
    def protected_message_count(self) -> int:
        """Return the number of uniquely protected original messages."""
        return len(self.protected_messages)

    @property
    def reason_counts(self) -> tuple[ProtectionReasonCount, ...]:
        """Return reason counts in ``ProtectionReason`` declaration order."""
        return tuple(
            ProtectionReasonCount(
                reason,
                sum(reason in message.reasons for message in self.protected_messages),
            )
            for reason in ProtectionReason
            if any(reason in message.reasons for message in self.protected_messages)
        )

    def to_result(self, skipped_optimization_count: int = 0) -> ProtectionResult:
        """Build immutable observability data for a completed strategy run."""
        return ProtectionResult(
            protected_message_count=self.protected_message_count,
            reason_counts=self.reason_counts,
            skipped_optimization_count=skipped_optimization_count,
        )


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
    _GENERIC_ERROR_PATTERN: Final = re.compile(
        r"Traceback \(most recent call last\):"
        r"|\b(?:[A-Za-z_][\w.]*)?(?:Error|Exception)\b"
        r"|(?:^|\n)\s*(?:fatal\s+)?error(?:\s+[A-Z]+\d+)?\s*:",
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
    _GENERIC_PATH_PATTERN: Final = re.compile(
        r"(?:\b[A-Za-z]:[\\/]|(?<!:)\B/)(?:[^\s<>:\"|?*]+[\\/])*[^\s<>:\"|?*]+"
        r"|\b(?:[\w.-]+[\\/])+[\w.-]+\b",
        re.IGNORECASE,
    )
    _FILE_TOKEN_PATTERN: Final = re.compile(
        r"(?<![\w.])(?:[\w.-]+[\\/])*[\w.-]+\.[A-Za-z0-9+]+",
        re.IGNORECASE,
    )
    _PROFILES_BY_ID: Final = {
        profile.language_id: profile for profile in DEFAULT_LANGUAGE_PROFILES
    }

    def __init__(self, language_detector: LanguageDetector | None = None) -> None:
        self._language_detector = language_detector

    def inspect(self, messages: Sequence[MessageMapping]) -> ProtectionPlan:
        """Return deterministic protection decisions for ``messages``."""
        return self._inspect_internal(messages, collect_diagnostics=False).plan

    def inspect_detailed(
        self,
        messages: Sequence[MessageMapping],
    ) -> ProtectionInspectionResult:
        """Return the protection plan with optional per-message diagnostics."""
        return self._inspect_internal(messages, collect_diagnostics=True)

    def _inspect_internal(
        self,
        messages: Sequence[MessageMapping],
        *,
        collect_diagnostics: bool,
    ) -> ProtectionInspectionResult:
        reasons_by_index: dict[int, set[ProtectionReason]] = {}
        language_diagnostics: list[MessageLanguageDiagnostic] = []

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
            if self._language_detector is None:
                if self._ERROR_PATTERN.search(content):
                    protect(index, ProtectionReason.ERROR_LOG)
                if self._FILE_REFERENCE_PATTERN.search(content):
                    protect(index, ProtectionReason.FILE_REFERENCE)
            else:
                generic_error = bool(self._GENERIC_ERROR_PATTERN.search(content))
                generic_file = bool(self._GENERIC_PATH_PATTERN.search(content))
                if collect_diagnostics:
                    (
                        language_ids,
                        language_file_reference,
                        diagnostic,
                    ) = self._detailed_language_evidence(index, content)
                    language_diagnostics.append(diagnostic)
                else:
                    language_ids, language_file_reference = self._language_evidence(
                        content
                    )
                if generic_error or self._has_language_error(content, language_ids):
                    protect(index, ProtectionReason.ERROR_LOG)
                if language_file_reference or generic_file:
                    protect(index, ProtectionReason.FILE_REFERENCE)
            if self._CONSTRAINT_PATTERN.search(content):
                protect(index, ProtectionReason.EXPLICIT_CONSTRAINT)

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
        return ProtectionInspectionResult(
            plan=ProtectionPlan(protected_messages),
            language_diagnostics=tuple(language_diagnostics),
        )

    def _language_evidence(
        self,
        content: str,
    ) -> tuple[tuple[LanguageId, ...], bool]:
        if self._language_detector is None:
            return (), False

        detected = set(self._language_detector.detect(content).candidates)
        language_file_reference = False
        for match in self._FILE_TOKEN_PATTERN.finditer(content):
            filename_detection = self._language_detector.detect(filename=match.group(0))
            if filename_detection.candidates:
                language_file_reference = True
                detected.update(filename_detection.candidates)

        return (
            tuple(language_id for language_id in LanguageId if language_id in detected),
            language_file_reference,
        )

    def _detailed_language_evidence(
        self,
        message_index: int,
        content: str,
    ) -> tuple[tuple[LanguageId, ...], bool, MessageLanguageDiagnostic]:
        if self._language_detector is None:
            raise RuntimeError("Detailed language evidence requires a detector.")

        content_report = self._language_detector.diagnose(content)
        detected = set(content_report.detection.candidates)
        file_reports: list[LanguageDetectionReport] = []
        for match in self._FILE_TOKEN_PATTERN.finditer(content):
            report = self._language_detector.diagnose(filename=match.group(0))
            if report.detection.candidates:
                file_reports.append(report)
                detected.update(report.detection.candidates)

        language_ids = tuple(
            language_id for language_id in LanguageId if language_id in detected
        )
        language_error = self._has_language_error(content, language_ids)
        language_file_reference = bool(file_reports)
        supported = tuple(
            reason
            for reason, applies in (
                (ProtectionReason.ERROR_LOG, language_error),
                (ProtectionReason.FILE_REFERENCE, language_file_reference),
            )
            if applies
        )
        added = tuple(
            reason
            for reason in supported
            if not (
                reason == ProtectionReason.ERROR_LOG
                and self._GENERIC_ERROR_PATTERN.search(content)
            )
            and not (
                reason == ProtectionReason.FILE_REFERENCE
                and self._GENERIC_PATH_PATTERN.search(content)
            )
        )
        diagnostic = MessageLanguageDiagnostic(
            message_index=message_index,
            content_report=content_report,
            file_reports=tuple(file_reports),
            language_supported_reasons=supported,
            added_protection_reasons=added,
        )
        return language_ids, language_file_reference, diagnostic

    @classmethod
    def _has_language_error(
        cls,
        content: str,
        language_ids: tuple[LanguageId, ...],
    ) -> bool:
        normalized_content = content.casefold()
        return any(
            keyword.casefold() in normalized_content
            for language_id in language_ids
            for keyword in cls._PROFILES_BY_ID[language_id].error_keywords
        )

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

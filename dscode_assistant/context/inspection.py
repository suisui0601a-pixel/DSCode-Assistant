"""Immutable results for optional, detailed context protection inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..languages import LanguageDetectionReport

if TYPE_CHECKING:
    from .protection import ProtectionPlan, ProtectionReason


@dataclass(frozen=True, slots=True)
class MessageLanguageDiagnostic:
    """Language evidence and its protection effect for one original message."""

    message_index: int
    content_report: LanguageDetectionReport
    file_reports: tuple[LanguageDetectionReport, ...] = ()
    language_supported_reasons: tuple[ProtectionReason, ...] = ()
    added_protection_reasons: tuple[ProtectionReason, ...] = ()

    def __post_init__(self) -> None:
        if self.message_index < 0:
            raise ValueError("Message diagnostic index cannot be negative.")
        if len(set(self.language_supported_reasons)) != len(
            self.language_supported_reasons
        ):
            raise ValueError("Language-supported reasons cannot contain duplicates.")
        if len(set(self.added_protection_reasons)) != len(
            self.added_protection_reasons
        ):
            raise ValueError("Added protection reasons cannot contain duplicates.")
        if not set(self.added_protection_reasons).issubset(
            self.language_supported_reasons
        ):
            raise ValueError("Added reasons must be language-supported reasons.")


@dataclass(frozen=True, slots=True)
class ProtectionInspectionResult:
    """A protection plan with optional, local-only language diagnostics."""

    plan: ProtectionPlan
    language_diagnostics: tuple[MessageLanguageDiagnostic, ...] = ()

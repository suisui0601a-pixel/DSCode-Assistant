"""Local, deterministic language detection from explicit metadata and text."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from .models import (
    DetectionSource,
    LanguageDetection,
    LanguageId,
    LanguageMatch,
    LanguageProfile,
)
from .registry import LanguageRegistry, build_default_registry


class LanguageDetector:
    """Detect language candidates without semantic inference or filesystem access."""

    _FENCE_PATTERN: Final = re.compile(
        r"^[ \t]{0,3}(?:`{3,}|~{3,})[ \t]*([^\s`~]+)?",
        re.MULTILINE,
    )
    _CONFIDENCE: Final = {
        DetectionSource.EXPLICIT: 1.0,
        DetectionSource.CODE_FENCE: 0.95,
        DetectionSource.FILE_EXTENSION: 0.9,
    }
    _SOURCE_ORDER: Final = {
        DetectionSource.EXPLICIT: 0,
        DetectionSource.CODE_FENCE: 1,
        DetectionSource.FILE_EXTENSION: 2,
    }

    def __init__(self, registry: LanguageRegistry | None = None) -> None:
        self._registry = registry or build_default_registry()

    def detect(
        self,
        text: str = "",
        *,
        filename: str | None = None,
        explicit_language: str | None = None,
    ) -> LanguageDetection:
        """Return all supported candidates found in the supplied in-memory values."""
        matches: list[LanguageMatch] = []

        if explicit_language:
            matches.extend(
                self._matches(
                    self._registry.find_by_alias(explicit_language),
                    DetectionSource.EXPLICIT,
                    explicit_language.strip(),
                )
            )

        for fence_alias in self._fence_aliases(text):
            matches.extend(
                self._matches(
                    self._registry.find_by_fence(fence_alias),
                    DetectionSource.CODE_FENCE,
                    fence_alias,
                )
            )

        if filename:
            matches.extend(
                self._matches(
                    self._registry.find_by_extension(filename),
                    DetectionSource.FILE_EXTENSION,
                    filename,
                )
            )

        unique_matches = {
            (match.language_id, match.source, match.evidence.casefold()): match
            for match in matches
        }
        ordered = tuple(
            sorted(
                unique_matches.values(),
                key=lambda match: (
                    self._SOURCE_ORDER[match.source],
                    tuple(LanguageId).index(match.language_id),
                    match.evidence.casefold(),
                ),
            )
        )
        return LanguageDetection(ordered)

    @classmethod
    def _fence_aliases(cls, text: str) -> tuple[str, ...]:
        return tuple(
            match.group(1).strip()
            for match in cls._FENCE_PATTERN.finditer(text)
            if match.group(1)
        )

    def _matches(
        self,
        profiles: Iterable[LanguageProfile],
        source: DetectionSource,
        evidence: str,
    ) -> list[LanguageMatch]:
        return [
            LanguageMatch(
                language_id=profile.language_id,
                source=source,
                confidence=self._CONFIDENCE[source],
                evidence=evidence,
            )
            for profile in profiles
        ]

"""Local, deterministic language detection from explicit metadata and text."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from .diagnostics import (
    DetectionIssue,
    DetectionIssueKind,
    DetectionObservation,
    DetectionOutcome,
    LanguageDetectionReport,
)
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

    def diagnose(
        self,
        text: str = "",
        *,
        filename: str | None = None,
        explicit_language: str | None = None,
    ) -> LanguageDetectionReport:
        """Return detailed local evidence without changing ``detect`` output."""
        detection = self.detect(
            text,
            filename=filename,
            explicit_language=explicit_language,
        )
        observations: list[DetectionObservation] = []

        if explicit_language:
            observations.append(
                self._observation(
                    DetectionSource.EXPLICIT,
                    explicit_language.strip(),
                    self._registry.find_by_alias(explicit_language),
                )
            )

        for occurrence, fence_alias in enumerate(self._fence_aliases(text), start=1):
            observations.append(
                self._observation(
                    DetectionSource.CODE_FENCE,
                    fence_alias,
                    self._registry.find_by_fence(fence_alias),
                    occurrence,
                )
            )

        if filename:
            observations.append(
                self._observation(
                    DetectionSource.FILE_EXTENSION,
                    filename,
                    self._registry.find_by_extension(filename),
                )
            )

        observation_tuple = tuple(observations)
        issues = self._diagnostic_issues(observation_tuple)
        outcome = self._diagnostic_outcome(detection, observation_tuple, issues)
        return LanguageDetectionReport(
            detection=detection,
            outcome=outcome,
            observations=observation_tuple,
            issues=issues,
        )

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

    def _observation(
        self,
        source: DetectionSource,
        evidence: str,
        profiles: Iterable[LanguageProfile],
        occurrence: int | None = None,
    ) -> DetectionObservation:
        candidates_found = {profile.language_id for profile in profiles}
        candidates = tuple(
            language_id for language_id in LanguageId if language_id in candidates_found
        )
        return DetectionObservation(
            source=source,
            evidence=evidence,
            candidates=candidates,
            confidence=self._CONFIDENCE[source] if candidates else 0.0,
            recognized=bool(candidates),
            occurrence=occurrence,
        )

    @staticmethod
    def _diagnostic_issues(
        observations: tuple[DetectionObservation, ...],
    ) -> tuple[DetectionIssue, ...]:
        issues_by_kind: dict[DetectionIssueKind, list[DetectionIssue]] = {
            kind: [] for kind in DetectionIssueKind
        }

        for index, observation in enumerate(observations):
            if (
                observation.source == DetectionSource.FILE_EXTENSION
                and len(observation.candidates) > 1
            ):
                issues_by_kind[DetectionIssueKind.SHARED_EXTENSION].append(
                    DetectionIssue(
                        DetectionIssueKind.SHARED_EXTENSION,
                        observation.candidates,
                        (index,),
                    )
                )
            if (
                observation.source
                in {DetectionSource.EXPLICIT, DetectionSource.CODE_FENCE}
                and not observation.recognized
            ):
                issues_by_kind[DetectionIssueKind.UNKNOWN_ALIAS].append(
                    DetectionIssue(
                        DetectionIssueKind.UNKNOWN_ALIAS,
                        (),
                        (index,),
                    )
                )

        fence_indexes = tuple(
            index
            for index, observation in enumerate(observations)
            if observation.source == DetectionSource.CODE_FENCE
            and observation.recognized
        )
        fence_candidates = LanguageDetector._candidate_union(
            observations[index] for index in fence_indexes
        )
        if len(fence_indexes) > 1 and len(fence_candidates) > 1:
            issues_by_kind[DetectionIssueKind.MULTIPLE_LANGUAGES].append(
                DetectionIssue(
                    DetectionIssueKind.MULTIPLE_LANGUAGES,
                    fence_candidates,
                    fence_indexes,
                )
            )

        explicit_indexes = tuple(
            index
            for index, observation in enumerate(observations)
            if observation.source == DetectionSource.EXPLICIT
            and observation.recognized
        )
        for explicit_index in explicit_indexes:
            explicit_candidates = set(observations[explicit_index].candidates)
            for fence_index in fence_indexes:
                fence_candidate_set = set(observations[fence_index].candidates)
                if explicit_candidates.isdisjoint(fence_candidate_set):
                    candidates = tuple(
                        language_id
                        for language_id in LanguageId
                        if language_id in explicit_candidates | fence_candidate_set
                    )
                    issues_by_kind[
                        DetectionIssueKind.EXPLICIT_FENCE_CONFLICT
                    ].append(
                        DetectionIssue(
                            DetectionIssueKind.EXPLICIT_FENCE_CONFLICT,
                            candidates,
                            tuple(sorted((explicit_index, fence_index))),
                        )
                    )

        return tuple(
            issue
            for kind in DetectionIssueKind
            for issue in issues_by_kind[kind]
        )

    @staticmethod
    def _candidate_union(
        observations: Iterable[DetectionObservation],
    ) -> tuple[LanguageId, ...]:
        found = {
            language_id
            for observation in observations
            for language_id in observation.candidates
        }
        return tuple(language_id for language_id in LanguageId if language_id in found)

    @staticmethod
    def _diagnostic_outcome(
        detection: LanguageDetection,
        observations: tuple[DetectionObservation, ...],
        issues: tuple[DetectionIssue, ...],
    ) -> DetectionOutcome:
        issue_kinds = {issue.kind for issue in issues}
        if DetectionIssueKind.EXPLICIT_FENCE_CONFLICT in issue_kinds:
            return DetectionOutcome.CONFLICTING
        if DetectionIssueKind.MULTIPLE_LANGUAGES in issue_kinds:
            return DetectionOutcome.MULTI_LANGUAGE
        if any(len(observation.candidates) > 1 for observation in observations):
            return DetectionOutcome.AMBIGUOUS
        if detection.ambiguous:
            return DetectionOutcome.AMBIGUOUS
        if detection.primary_language is not None:
            return DetectionOutcome.IDENTIFIED
        return DetectionOutcome.UNKNOWN

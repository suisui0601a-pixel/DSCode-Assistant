"""Immutable, local-only diagnostics for deterministic language detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import DetectionSource, LanguageDetection, LanguageId


class DetectionOutcome(str, Enum):
    """High-level interpretation of all evidence in one detection request."""

    UNKNOWN = "unknown"
    IDENTIFIED = "identified"
    AMBIGUOUS = "ambiguous"
    MULTI_LANGUAGE = "multi_language"
    CONFLICTING = "conflicting"


@dataclass(frozen=True, slots=True)
class DetectionObservation:
    """One metadata observation without retaining source-code content."""

    source: DetectionSource
    evidence: str
    candidates: tuple[LanguageId, ...]
    confidence: float
    recognized: bool
    occurrence: int | None = None

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("Detection observation evidence cannot be empty.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Detection observation confidence must be between 0 and 1.")
        if self.occurrence is not None and self.occurrence <= 0:
            raise ValueError("Detection observation occurrence must be positive.")
        if tuple(dict.fromkeys(self.candidates)) != self.candidates:
            raise ValueError("Detection observation candidates cannot contain duplicates.")
        expected = tuple(
            language_id for language_id in LanguageId if language_id in self.candidates
        )
        if self.candidates != expected:
            raise ValueError("Detection observation candidates must use deterministic order.")
        if self.recognized != bool(self.candidates):
            raise ValueError("Recognized observations must have at least one candidate.")
        if not self.recognized and self.confidence != 0.0:
            raise ValueError("Unrecognized observations must have zero confidence.")


class DetectionIssueKind(str, Enum):
    """Deterministic diagnostic conditions requiring caller interpretation."""

    SHARED_EXTENSION = "shared_extension"
    MULTIPLE_LANGUAGES = "multiple_languages"
    EXPLICIT_FENCE_CONFLICT = "explicit_fence_conflict"
    UNKNOWN_ALIAS = "unknown_alias"


@dataclass(frozen=True, slots=True)
class DetectionIssue:
    """A diagnostic issue linked to observations by stable tuple indexes."""

    kind: DetectionIssueKind
    candidates: tuple[LanguageId, ...]
    observation_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        expected_candidates = tuple(
            language_id for language_id in LanguageId if language_id in self.candidates
        )
        if self.candidates != expected_candidates:
            raise ValueError("Detection issue candidates must use deterministic order.")
        if any(index < 0 for index in self.observation_indexes):
            raise ValueError("Detection issue observation indexes cannot be negative.")
        if tuple(sorted(set(self.observation_indexes))) != self.observation_indexes:
            raise ValueError(
                "Detection issue observation indexes must be unique and sorted."
            )
        if not self.observation_indexes:
            raise ValueError("Detection issues must reference at least one observation.")


@dataclass(frozen=True, slots=True)
class LanguageDetectionReport:
    """Detailed local diagnostics alongside the backward-compatible result."""

    detection: LanguageDetection
    outcome: DetectionOutcome
    observations: tuple[DetectionObservation, ...] = ()
    issues: tuple[DetectionIssue, ...] = ()

    def __post_init__(self) -> None:
        issue_order = tuple(DetectionIssueKind)
        actual = tuple(issue.kind for issue in self.issues)
        expected = tuple(
            kind
            for kind in issue_order
            for issue in self.issues
            if issue.kind == kind
        )
        if actual != expected:
            raise ValueError("Detection issues must use deterministic kind order.")
        if any(
            index >= len(self.observations)
            for issue in self.issues
            for index in issue.observation_indexes
        ):
            raise ValueError("Detection issue references an unknown observation.")

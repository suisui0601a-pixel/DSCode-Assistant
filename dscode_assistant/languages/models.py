"""Immutable data models for local programming-language identification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LanguageId(str, Enum):
    """Stable identifiers for languages supported by the foundation layer."""

    PYTHON = "python"
    C = "c"
    CPP = "cpp"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


@dataclass(frozen=True, slots=True)
class CommentSyntax:
    """Comment delimiters recorded as metadata, without parsing source code."""

    line_prefixes: tuple[str, ...] = ()
    block_pairs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if any(not prefix for prefix in self.line_prefixes):
            raise ValueError("Comment line prefixes cannot be empty.")
        if any(not opening or not closing for opening, closing in self.block_pairs):
            raise ValueError("Comment block delimiters cannot be empty.")


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    """Static metadata used by deterministic language detection."""

    language_id: LanguageId
    display_name: str
    file_extensions: tuple[str, ...]
    fence_aliases: tuple[str, ...]
    explicit_aliases: tuple[str, ...]
    comments: CommentSyntax
    error_keywords: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("Language display name cannot be empty.")
        if any(
            not extension.startswith(".") or len(extension) == 1
            for extension in self.file_extensions
        ):
            raise ValueError("File extensions must start with a dot and contain a suffix.")
        self._ensure_unique("file extensions", self.file_extensions)
        self._ensure_unique("fence aliases", self.fence_aliases)
        self._ensure_unique("explicit aliases", self.explicit_aliases)
        self._ensure_unique("error keywords", self.error_keywords)
        if any(not alias.strip() for alias in self.fence_aliases + self.explicit_aliases):
            raise ValueError("Language aliases cannot be empty.")
        if any(not keyword.strip() for keyword in self.error_keywords):
            raise ValueError("Error keywords cannot be empty.")

    @staticmethod
    def _ensure_unique(label: str, values: tuple[str, ...]) -> None:
        normalized = tuple(value.casefold() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"Language {label} cannot contain duplicates.")


class DetectionSource(str, Enum):
    """The deterministic evidence source for one language match."""

    EXPLICIT = "explicit"
    CODE_FENCE = "code_fence"
    FILE_EXTENSION = "file_extension"


@dataclass(frozen=True, slots=True)
class LanguageMatch:
    """One language candidate supported by one piece of local evidence."""

    language_id: LanguageId
    source: DetectionSource
    confidence: float
    evidence: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Language confidence must be between 0 and 1.")
        if not self.evidence:
            raise ValueError("Language detection evidence cannot be empty.")


@dataclass(frozen=True, slots=True)
class LanguageDetection:
    """Deterministically ordered language evidence for one detection request."""

    matches: tuple[LanguageMatch, ...] = ()

    @property
    def candidates(self) -> tuple[LanguageId, ...]:
        """Return unique candidates in stable ``LanguageId`` declaration order."""
        matched = {match.language_id for match in self.matches}
        return tuple(language_id for language_id in LanguageId if language_id in matched)

    @property
    def ambiguous(self) -> bool:
        """Return whether evidence points to more than one language."""
        return len(self.candidates) > 1

    @property
    def primary_language(self) -> LanguageId | None:
        """Return the only candidate, or ``None`` for unknown/ambiguous input."""
        candidates = self.candidates
        return candidates[0] if len(candidates) == 1 else None

    @property
    def confidence(self) -> float:
        """Return the strongest confidence score, or zero when undetected."""
        return max((match.confidence for match in self.matches), default=0.0)

"""Deterministic registry for immutable language profiles."""

from __future__ import annotations

from pathlib import PurePath

from .models import LanguageId, LanguageProfile
from .profiles import DEFAULT_LANGUAGE_PROFILES


class LanguageRegistry:
    """Register and query language metadata without filesystem access."""

    def __init__(self, profiles: tuple[LanguageProfile, ...] = ()) -> None:
        self._profiles: dict[LanguageId, LanguageProfile] = {}
        self._extensions: dict[str, set[LanguageId]] = {}
        self._fence_aliases: dict[str, set[LanguageId]] = {}
        self._explicit_aliases: dict[str, set[LanguageId]] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: LanguageProfile) -> None:
        """Register one profile, allowing lookup keys shared by other languages."""
        if profile.language_id in self._profiles:
            raise ValueError(f"Language is already registered: {profile.language_id.value}")
        self._profiles[profile.language_id] = profile
        self._add_keys(self._extensions, profile.file_extensions, profile.language_id)
        self._add_keys(self._fence_aliases, profile.fence_aliases, profile.language_id)
        self._add_keys(self._explicit_aliases, profile.explicit_aliases, profile.language_id)

    def get(self, language_id: LanguageId | str) -> LanguageProfile | None:
        """Return a profile by stable ID, or ``None`` for an unknown ID."""
        try:
            normalized_id = LanguageId(language_id)
        except ValueError:
            return None
        return self._profiles.get(normalized_id)

    def find_by_extension(self, extension_or_filename: str) -> tuple[LanguageProfile, ...]:
        """Find all profiles matching a suffix without opening the referenced path."""
        extension = self._extract_extension(extension_or_filename)
        return self._profiles_for(self._extensions.get(extension, set()))

    def find_by_fence(self, alias: str) -> tuple[LanguageProfile, ...]:
        """Find all profiles matching an exact Markdown fence alias."""
        return self._profiles_for(self._fence_aliases.get(self._normalize(alias), set()))

    def find_by_alias(self, alias: str) -> tuple[LanguageProfile, ...]:
        """Find all profiles matching an exact explicit-language alias."""
        return self._profiles_for(self._explicit_aliases.get(self._normalize(alias), set()))

    def profiles(self) -> tuple[LanguageProfile, ...]:
        """Return registered profiles in stable ``LanguageId`` declaration order."""
        return self._profiles_for(set(self._profiles))

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()

    @classmethod
    def _extract_extension(cls, value: str) -> str:
        normalized = cls._normalize(value).replace("\\", "/")
        if normalized.startswith(".") and "/" not in normalized:
            return normalized
        return PurePath(normalized).suffix

    @classmethod
    def _add_keys(
        cls,
        index: dict[str, set[LanguageId]],
        keys: tuple[str, ...],
        language_id: LanguageId,
    ) -> None:
        for key in keys:
            index.setdefault(cls._normalize(key), set()).add(language_id)

    def _profiles_for(self, language_ids: set[LanguageId]) -> tuple[LanguageProfile, ...]:
        return tuple(
            self._profiles[language_id]
            for language_id in LanguageId
            if language_id in language_ids and language_id in self._profiles
        )


def build_default_registry() -> LanguageRegistry:
    """Create an independent registry containing all built-in profiles."""
    return LanguageRegistry(DEFAULT_LANGUAGE_PROFILES)

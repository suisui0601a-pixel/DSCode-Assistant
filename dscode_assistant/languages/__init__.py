"""Public interface for the independent Language Support foundation layer."""

from .detector import LanguageDetector
from .models import (
    CommentSyntax,
    DetectionSource,
    LanguageDetection,
    LanguageId,
    LanguageMatch,
    LanguageProfile,
)
from .profiles import DEFAULT_LANGUAGE_PROFILES
from .registry import LanguageRegistry, build_default_registry

__all__ = [
    "CommentSyntax",
    "DEFAULT_LANGUAGE_PROFILES",
    "DetectionSource",
    "LanguageDetection",
    "LanguageDetector",
    "LanguageId",
    "LanguageMatch",
    "LanguageProfile",
    "LanguageRegistry",
    "build_default_registry",
]

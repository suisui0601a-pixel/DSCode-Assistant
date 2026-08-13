"""Tests for the independent Language Support foundation layer."""

from __future__ import annotations

import unittest

from dscode_assistant.languages import (
    DetectionSource,
    LanguageDetector,
    LanguageId,
    build_default_registry,
)


class LanguageSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_default_registry()
        self.detector = LanguageDetector(self.registry)

    def test_all_six_language_profiles_are_registered_in_stable_order(self) -> None:
        self.assertEqual(
            tuple(profile.language_id for profile in self.registry.profiles()),
            tuple(LanguageId),
        )
        self.assertEqual(
            self.registry.get(LanguageId.PYTHON).display_name,
            "Python",
        )
        self.assertIsNone(self.registry.get("unknown"))

    def test_detects_supported_fence_aliases(self) -> None:
        cases = {
            "python": LanguageId.PYTHON,
            "c": LanguageId.C,
            "cpp": LanguageId.CPP,
            "java": LanguageId.JAVA,
            "javascript": LanguageId.JAVASCRIPT,
            "typescript": LanguageId.TYPESCRIPT,
        }
        for alias, expected in cases.items():
            with self.subTest(alias=alias):
                detection = self.detector.detect(f"```{alias}\ncode\n```")
                self.assertEqual(detection.primary_language, expected)
                self.assertEqual(detection.matches[0].source, DetectionSource.CODE_FENCE)

    def test_detects_language_from_filename_extension_without_file_access(self) -> None:
        detection = self.detector.detect(filename=r"C:\missing\project\service.TSX")

        self.assertEqual(detection.primary_language, LanguageId.TYPESCRIPT)
        self.assertFalse(detection.ambiguous)
        self.assertEqual(detection.matches[0].source, DetectionSource.FILE_EXTENSION)

    def test_detects_exact_explicit_alias(self) -> None:
        detection = self.detector.detect(explicit_language="  C++  ")

        self.assertEqual(detection.primary_language, LanguageId.CPP)
        self.assertEqual(detection.confidence, 1.0)
        self.assertEqual(detection.matches[0].source, DetectionSource.EXPLICIT)

    def test_java_does_not_match_javascript_or_javascript_match_java(self) -> None:
        java = self.detector.detect(explicit_language="java")
        javascript = self.detector.detect(explicit_language="javascript")

        self.assertEqual(java.candidates, (LanguageId.JAVA,))
        self.assertEqual(javascript.candidates, (LanguageId.JAVASCRIPT,))

    def test_h_extension_is_explicitly_ambiguous_between_c_and_cpp(self) -> None:
        detection = self.detector.detect(filename="include/library.h")

        self.assertTrue(detection.ambiguous)
        self.assertIsNone(detection.primary_language)
        self.assertEqual(detection.candidates, (LanguageId.C, LanguageId.CPP))

    def test_unknown_language_returns_empty_detection(self) -> None:
        detection = self.detector.detect(
            "```brainlang\nthink()\n```",
            filename="notes.unknown",
            explicit_language="brainlang",
        )

        self.assertEqual(detection.matches, ())
        self.assertEqual(detection.candidates, ())
        self.assertIsNone(detection.primary_language)
        self.assertFalse(detection.ambiguous)
        self.assertEqual(detection.confidence, 0.0)

    def test_multiple_language_code_blocks_return_stable_candidates(self) -> None:
        text = """```typescript
const answer: number = 42;
```

```python
print(42)
```

```typescript
console.log(answer)
```"""
        first = self.detector.detect(text)
        second = self.detector.detect(text)

        self.assertEqual(first, second)
        self.assertTrue(first.ambiguous)
        self.assertIsNone(first.primary_language)
        self.assertEqual(
            first.candidates,
            (LanguageId.PYTHON, LanguageId.TYPESCRIPT),
        )
        self.assertEqual(len(first.matches), 2)


if __name__ == "__main__":
    unittest.main()

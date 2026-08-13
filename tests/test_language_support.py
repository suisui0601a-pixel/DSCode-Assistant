"""Tests for the independent Language Support foundation layer."""

from __future__ import annotations

import unittest

from dscode_assistant.languages import (
    DetectionIssueKind,
    DetectionOutcome,
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

    def test_diagnose_preserves_unknown_fence_as_local_observation(self) -> None:
        report = self.detector.diagnose("```brainlang\nthink()\n```")

        self.assertEqual(report.outcome, DetectionOutcome.UNKNOWN)
        self.assertEqual(report.detection.matches, ())
        self.assertEqual(len(report.observations), 1)
        self.assertEqual(report.observations[0].evidence, "brainlang")
        self.assertFalse(report.observations[0].recognized)
        self.assertEqual(report.observations[0].candidates, ())
        self.assertEqual(report.observations[0].confidence, 0.0)
        self.assertEqual(report.observations[0].occurrence, 1)
        self.assertEqual(report.issues[0].kind, DetectionIssueKind.UNKNOWN_ALIAS)
        self.assertEqual(report.issues[0].observation_indexes, (0,))

    def test_diagnose_h_extension_reports_shared_extension_ambiguity(self) -> None:
        report = self.detector.diagnose(filename="include/library.h")

        self.assertEqual(report.outcome, DetectionOutcome.AMBIGUOUS)
        self.assertEqual(report.detection.candidates, (LanguageId.C, LanguageId.CPP))
        self.assertEqual(report.observations[0].candidates, (LanguageId.C, LanguageId.CPP))
        self.assertEqual(report.issues[0].kind, DetectionIssueKind.SHARED_EXTENSION)

    def test_diagnose_keeps_java_and_javascript_distinct(self) -> None:
        java = self.detector.diagnose("```java\nclass Main {}\n```")
        javascript = self.detector.diagnose("```javascript\nconst x = 1;\n```")

        self.assertEqual(java.outcome, DetectionOutcome.IDENTIFIED)
        self.assertEqual(java.detection.candidates, (LanguageId.JAVA,))
        self.assertEqual(javascript.outcome, DetectionOutcome.IDENTIFIED)
        self.assertEqual(javascript.detection.candidates, (LanguageId.JAVASCRIPT,))
        self.assertEqual(java.issues, ())
        self.assertEqual(javascript.issues, ())

    def test_diagnose_multi_language_code_blocks_is_not_a_conflict(self) -> None:
        report = self.detector.diagnose(
            "```python\nprint('ok')\n```\n```typescript\nconst ok = true;\n```"
        )

        self.assertEqual(report.outcome, DetectionOutcome.MULTI_LANGUAGE)
        self.assertEqual(
            report.detection.candidates,
            (LanguageId.PYTHON, LanguageId.TYPESCRIPT),
        )
        self.assertEqual(
            tuple(observation.occurrence for observation in report.observations),
            (1, 2),
        )
        self.assertEqual(report.issues[0].kind, DetectionIssueKind.MULTIPLE_LANGUAGES)
        self.assertEqual(report.issues[0].observation_indexes, (0, 1))

    def test_diagnose_explicit_and_fence_disagreement_is_conflicting(self) -> None:
        report = self.detector.diagnose(
            "```javascript\nconst x = 1;\n```",
            explicit_language="java",
        )

        self.assertEqual(report.outcome, DetectionOutcome.CONFLICTING)
        self.assertEqual(
            report.detection.candidates,
            (LanguageId.JAVA, LanguageId.JAVASCRIPT),
        )
        self.assertEqual(
            report.issues[0].kind,
            DetectionIssueKind.EXPLICIT_FENCE_CONFLICT,
        )
        self.assertEqual(report.issues[0].observation_indexes, (0, 1))

    def test_diagnose_unique_language_is_identified(self) -> None:
        report = self.detector.diagnose(
            "```python\nprint('ok')\n```",
            filename="script.py",
            explicit_language="python",
        )

        self.assertEqual(report.outcome, DetectionOutcome.IDENTIFIED)
        self.assertEqual(report.detection.primary_language, LanguageId.PYTHON)
        self.assertEqual(report.issues, ())
        self.assertEqual(len(report.observations), 3)
        self.assertEqual(
            report.detection,
            self.detector.detect(
                "```python\nprint('ok')\n```",
                filename="script.py",
                explicit_language="python",
            ),
        )

    def test_diagnose_is_deterministic_across_repeated_runs(self) -> None:
        inputs = {
            "text": "```unknown\nx\n```\n```cpp\nint main() {}\n```",
            "filename": "include/value.h",
            "explicit_language": "c++",
        }

        first = self.detector.diagnose(**inputs)
        second = self.detector.diagnose(**inputs)

        self.assertEqual(first, second)
        self.assertEqual(first.observations, second.observations)
        self.assertEqual(first.issues, second.issues)


if __name__ == "__main__":
    unittest.main()

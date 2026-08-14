"""Product-layer dependency assembly tests."""

from __future__ import annotations

import unittest

from dscode_assistant.app import _build_context_optimizer
from dscode_assistant.context import (
    ContextOptimizer,
    ContextProtector,
    OptimizationLevel,
    ProtectionReason,
)


class ProductIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.messages = [
            {"role": "system", "content": "Keep the API contract stable."},
            {"role": "user", "content": "Review this short note."},
            {"role": "user", "content": "Review this short note."},
            {"role": "assistant", "content": "The previous review is complete."},
            {
                "role": "user",
                "content": "```typescript\nvalue is not assignable to type Result\n```",
            },
        ]

    def test_default_optimizer_matches_explicit_detector_free_pipeline(self) -> None:
        default_optimizer = ContextOptimizer()
        detector_free_optimizer = ContextOptimizer(protector=ContextProtector())

        for level in (OptimizationLevel.RAW, OptimizationLevel.LIGHT):
            default_result = default_optimizer.prepare(self.messages, level)
            explicit_result = detector_free_optimizer.prepare(self.messages, level)

            self.assertEqual(default_result, explicit_result)

    def test_application_pipeline_enables_language_protection(self) -> None:
        legacy_result = ContextOptimizer().prepare(
            self.messages,
            OptimizationLevel.LIGHT,
        )
        integrated_result = _build_context_optimizer().prepare(
            self.messages,
            OptimizationLevel.LIGHT,
        )

        self.assertEqual(
            legacy_result.protection.count_for(ProtectionReason.ERROR_LOG),
            0,
        )
        self.assertEqual(
            integrated_result.protection.count_for(ProtectionReason.ERROR_LOG),
            1,
        )

    def test_language_aware_raw_keeps_messages_unchanged(self) -> None:
        result = _build_context_optimizer().prepare(
            self.messages,
            OptimizationLevel.RAW,
        )

        self.assertEqual(result.messages, self.messages)
        self.assertTrue(
            all(set(message) == {"role", "content"} for message in result.messages)
        )

    def test_language_aware_light_keeps_strategy_behavior(self) -> None:
        legacy_result = ContextOptimizer().prepare(
            self.messages,
            OptimizationLevel.LIGHT,
        )
        integrated_result = _build_context_optimizer().prepare(
            self.messages,
            OptimizationLevel.LIGHT,
        )

        self.assertEqual(integrated_result.messages, legacy_result.messages)
        self.assertLess(len(integrated_result.messages), len(self.messages))


if __name__ == "__main__":
    unittest.main()

"""Tests for the first deterministic context optimization layer."""

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from dscode_assistant.context import (
    ContextBudget,
    ContextOptimizer,
    LightweightTokenEstimator,
    OptimizationLevel,
)
from dscode_assistant.settings import (
    CONTEXT_OPTIMIZATION_LIGHT,
    CONTEXT_OPTIMIZATION_RAW,
    SettingsManager,
    get_context_optimization_mode,
)


class ContextOptimizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.optimizer = ContextOptimizer()

    def test_raw_result_matches_current_request_messages_exactly(self) -> None:
        messages = [
            {"role": "system", "content": "Keep exact spacing."},
            {"role": "user", "content": "  Do not trim me.  "},
            {"role": "assistant", "content": "First answer"},
            {"role": "assistant", "content": "First answer"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.RAW)

        self.assertEqual(result.messages, messages)
        self.assertIsNot(result.messages, messages)
        self.assertTrue(
            all(actual is not original for actual, original in zip(result.messages, messages))
        )
        self.assertEqual(result.estimated_tokens_before, result.estimated_tokens_after)

    def test_light_removes_consecutive_exact_duplicates(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "A" * 300},
            {"role": "user", "content": "A" * 300},
            {"role": "assistant", "content": "B" * 300},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(
            result.messages,
            [messages[0], messages[1], messages[3]],
        )

    def test_light_removes_empty_messages(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "  \n\t"},
            {"role": "user", "content": "Keep this"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(
            result.messages,
            [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Keep this"},
            ],
        )

    def test_light_merges_consecutive_short_messages_without_rewriting(self) -> None:
        messages = [
            {"role": "user", "content": "First requirement"},
            {"role": "user", "content": "Second requirement"},
            {"role": "assistant", "content": "Acknowledged"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(
            result.messages[0],
            {
                "role": "user",
                "content": "First requirement\n\nSecond requirement",
            },
        )

    def test_light_preserves_code_block_content_and_boundaries(self) -> None:
        code_message = "Before\n```python\nprint('exact')\n```\nAfter"
        messages = [
            {"role": "user", "content": code_message},
            {"role": "user", "content": "Do not merge into the code message"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(result.messages[0]["content"], code_message)
        self.assertEqual(len(result.messages), 2)

    def test_light_removes_failed_placeholder_messages(self) -> None:
        messages = [
            {"role": "user", "content": "Question", "status": "completed"},
            {"role": "assistant", "content": "Partial error", "status": "failed"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(result.messages, [{"role": "user", "content": "Question"}])

    def test_token_estimator_is_local_deterministic_and_counts_overhead(self) -> None:
        estimator = LightweightTokenEstimator(message_overhead=4)
        messages = [{"role": "user", "content": "abcdefgh"}]

        first = estimator.estimate_messages(messages)
        second = estimator.estimate_messages(messages)

        self.assertEqual(first, second)
        self.assertEqual(estimator.estimate_text("abcdefgh"), 2)
        self.assertEqual(first, 7)
        self.assertGreater(first, estimator.estimate_text("abcdefgh"))
        self.assertGreater(estimator.estimate_text("中文内容"), 0)

    def test_budget_validation_and_future_levels_fail_explicitly(self) -> None:
        budget = ContextBudget(
            max_input_tokens=1000,
            reserved_output_tokens=200,
            target_input_tokens=700,
        )
        self.assertEqual(budget.usable_input_tokens, 800)

        with self.assertRaises(NotImplementedError):
            self.optimizer.prepare([], OptimizationLevel.BALANCED, budget)

    def test_legacy_settings_without_context_mode_default_to_raw(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            (data_dir / "settings.json").write_text(
                json.dumps({"model": "legacy-model"}),
                encoding="utf-8",
            )
            loaded = SettingsManager(data_dir).load()

        self.assertEqual(
            get_context_optimization_mode(loaded),
            CONTEXT_OPTIMIZATION_RAW,
        )

    def test_context_mode_saves_and_loads_as_ordinary_setting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = SettingsManager(Path(temporary_directory))
            settings.save({"context_optimization_mode": CONTEXT_OPTIMIZATION_LIGHT})
            loaded = settings.load()
            saved_text = (Path(temporary_directory) / "settings.json").read_text(
                encoding="utf-8"
            )

        self.assertEqual(
            get_context_optimization_mode(loaded),
            CONTEXT_OPTIMIZATION_LIGHT,
        )
        self.assertIn('"context_optimization_mode": "light"', saved_text)


if __name__ == "__main__":
    unittest.main()

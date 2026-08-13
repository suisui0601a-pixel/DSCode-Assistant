"""Tests for the first deterministic context optimization layer."""

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from dscode_assistant.context import (
    ContextBudget,
    ContextOptimizer,
    ContextProtector,
    LightweightTokenEstimator,
    OptimizationLevel,
    ProtectionReason,
    ProtectionResult,
)
from dscode_assistant.languages import LanguageDetector
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
            {"role": "assistant", "content": "Earlier response"},
            {"role": "user", "content": "Current task"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(
            result.messages,
            [messages[0], messages[1], messages[3], messages[4]],
        )

    def test_light_removes_short_unprotected_duplicates(self) -> None:
        messages = [
            {"role": "user", "content": "Ordinary duplicate"},
            {"role": "user", "content": "Ordinary duplicate"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(result.messages.count(messages[0]), 1)

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
            {"role": "user", "content": "Current task"},
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

    def test_system_message_is_protected_from_deduplication(self) -> None:
        messages = [
            {"role": "system", "content": "Same system instruction"},
            {"role": "system", "content": "Same system instruction"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertTrue(plan.protects(0))
        self.assertTrue(plan.protects(1))
        self.assertIn(ProtectionReason.SYSTEM, plan.reasons_for(0))
        self.assertEqual(result.messages, messages)

    def test_current_user_and_recent_assistant_are_protected(self) -> None:
        messages = [
            {"role": "assistant", "content": "Older response"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Earlier task"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(
            plan.reasons_for(1),
            frozenset({ProtectionReason.RECENT_RESPONSE}),
        )
        self.assertEqual(
            plan.reasons_for(3),
            frozenset({ProtectionReason.CURRENT_TASK}),
        )
        self.assertEqual(result.messages[-2:], messages[-2:])

    def test_identical_code_blocks_are_both_preserved(self) -> None:
        code = "```python\nprint('keep exact')\n```"
        messages = [
            {"role": "user", "content": code},
            {"role": "user", "content": code},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertIn(ProtectionReason.CODE_BLOCK, plan.reasons_for(0))
        self.assertEqual(result.messages[:2], messages[:2])

    def test_diff_patch_is_preserved_exactly(self) -> None:
        patch = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new"
        messages = [
            {"role": "user", "content": patch},
            {"role": "user", "content": patch},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertIn(ProtectionReason.PATCH, plan.reasons_for(0))
        self.assertEqual(result.messages[:2], messages[:2])

    def test_traceback_and_compiler_error_are_protected(self) -> None:
        traceback = "Traceback (most recent call last):\n  File \"app.py\", line 1\nValueError: bad"
        compiler = "main.cpp:12: error: cannot find symbol"
        messages = [
            {"role": "user", "content": traceback},
            {"role": "user", "content": compiler},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(0))
        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(1))
        self.assertEqual(result.messages[:2], messages[:2])

    def test_default_protector_keeps_legacy_behavior_without_detector(self) -> None:
        messages = [
            {"role": "user", "content": "main.cpp:12: undefined reference"},
            {"role": "user", "content": "Review module.mts"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)

        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(0))
        self.assertNotIn(ProtectionReason.FILE_REFERENCE, plan.reasons_for(1))

    def test_injected_detector_enhances_language_file_protection(self) -> None:
        messages = [
            {"role": "user", "content": "Review module.mts"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector(LanguageDetector()).inspect(messages)

        self.assertIn(ProtectionReason.FILE_REFERENCE, plan.reasons_for(0))

    def test_injected_detector_protects_python_error(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "```python\nTraceback (most recent call last):\nModuleNotFoundError\n```",
            },
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector(LanguageDetector()).inspect(messages)

        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(0))

    def test_injected_detector_protects_java_profile_error(self) -> None:
        messages = [
            {"role": "user", "content": "```java\nMain.java: cannot find symbol\n```"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector(LanguageDetector()).inspect(messages)

        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(0))
        self.assertIn(ProtectionReason.FILE_REFERENCE, plan.reasons_for(0))

    def test_injected_detector_protects_c_and_cpp_profile_errors(self) -> None:
        messages = [
            {"role": "user", "content": "```c\nsegmentation fault\n```"},
            {"role": "user", "content": "```cpp\ntemplate instantiation failed\n```"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector(LanguageDetector()).inspect(messages)

        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(0))
        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(1))

    def test_injected_detector_handles_multi_language_message(self) -> None:
        messages = [
            {
                "role": "user",
                "content": (
                    "```python\nprint('ok')\n```\n"
                    "```java\nMain.java: cannot find symbol\n```"
                ),
            },
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector(LanguageDetector()).inspect(messages)

        self.assertIn(ProtectionReason.CODE_BLOCK, plan.reasons_for(0))
        self.assertIn(ProtectionReason.ERROR_LOG, plan.reasons_for(0))
        self.assertIn(ProtectionReason.FILE_REFERENCE, plan.reasons_for(0))

    def test_raw_messages_do_not_change_with_injected_detector(self) -> None:
        messages = [
            {"role": "system", "content": "Keep exact spacing."},
            {"role": "user", "content": "```cpp\ntemplate instantiation\n```"},
        ]
        optimizer = ContextOptimizer(
            protector=ContextProtector(LanguageDetector()),
        )

        result = optimizer.prepare(messages, OptimizationLevel.RAW)

        self.assertEqual(result.messages, messages)

    def test_file_paths_are_protected(self) -> None:
        messages = [
            {"role": "user", "content": r"Update D:\project\src\app.py"},
            {"role": "user", "content": "Review src/service.ts"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertIn(ProtectionReason.FILE_REFERENCE, plan.reasons_for(0))
        self.assertIn(ProtectionReason.FILE_REFERENCE, plan.reasons_for(1))
        self.assertEqual(result.messages[:2], messages[:2])

    def test_explicit_constraints_in_chinese_and_english_are_protected(self) -> None:
        messages = [
            {"role": "user", "content": "禁止修改数据库结构"},
            {"role": "user", "content": "Do not change the API contract"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        plan = ContextProtector().inspect(messages)
        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertIn(ProtectionReason.EXPLICIT_CONSTRAINT, plan.reasons_for(0))
        self.assertIn(ProtectionReason.EXPLICIT_CONSTRAINT, plan.reasons_for(1))
        self.assertEqual(result.messages[:2], messages[:2])

    def test_light_is_idempotent(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "First short message"},
            {"role": "user", "content": "Second short message"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        first = self.optimizer.prepare(messages, OptimizationLevel.LIGHT).messages
        second = self.optimizer.prepare(first, OptimizationLevel.LIGHT).messages

        self.assertEqual(second, first)

    def test_protection_statistics_count_unique_messages_and_reasons(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "```python\nprint('x')\n```"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(result.protection.protected_message_count, 4)
        self.assertEqual(result.protection.count_for(ProtectionReason.SYSTEM), 1)
        self.assertEqual(result.protection.count_for(ProtectionReason.CODE_BLOCK), 1)
        self.assertEqual(result.protection.count_for(ProtectionReason.RECENT_RESPONSE), 1)
        self.assertEqual(result.protection.count_for(ProtectionReason.CURRENT_TASK), 1)
        self.assertEqual(result.protection.total_reason_matches, 4)
        self.assertEqual(
            tuple(item.reason for item in result.protection.reason_counts),
            (
                ProtectionReason.SYSTEM,
                ProtectionReason.CURRENT_TASK,
                ProtectionReason.RECENT_RESPONSE,
                ProtectionReason.CODE_BLOCK,
            ),
        )

    def test_multi_reason_message_counts_once_but_each_reason_is_recorded(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "Do not change app.py\n```python\nprint('x')\n```",
            }
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(result.protection.protected_message_count, 1)
        self.assertEqual(result.protection.count_for(ProtectionReason.CURRENT_TASK), 1)
        self.assertEqual(result.protection.count_for(ProtectionReason.CODE_BLOCK), 1)
        self.assertEqual(
            result.protection.count_for(ProtectionReason.EXPLICIT_CONSTRAINT),
            1,
        )
        self.assertEqual(result.protection.count_for(ProtectionReason.FILE_REFERENCE), 1)
        self.assertEqual(result.protection.total_reason_matches, 4)

    def test_raw_reports_protection_but_skips_no_optimization(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Current task"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.RAW)

        self.assertEqual(result.messages, messages)
        self.assertEqual(result.protection.protected_message_count, 2)
        self.assertEqual(result.protection.skipped_optimization_count, 0)

    def test_light_counts_messages_bypassed_due_to_protection(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Ordinary duplicate"},
            {"role": "user", "content": "Ordinary duplicate"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Current task"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(result.protection.protected_message_count, 3)
        self.assertEqual(result.protection.skipped_optimization_count, 3)
        self.assertEqual(result.messages.count(messages[1]), 1)

    def test_empty_input_has_empty_observability(self) -> None:
        for level in (OptimizationLevel.RAW, OptimizationLevel.LIGHT):
            with self.subTest(level=level):
                result = self.optimizer.prepare([], level)
                self.assertEqual(result.messages, [])
                self.assertEqual(result.protection, ProtectionResult())

    def test_repeated_original_input_has_identical_observability(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Review app.py"},
            {"role": "assistant", "content": "Recent response"},
            {"role": "user", "content": "Do not change the API"},
        ]

        first = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)
        second = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertEqual(first.messages, second.messages)
        self.assertEqual(first.protection, second.protection)
        self.assertEqual(first.estimated_tokens_before, second.estimated_tokens_before)
        self.assertEqual(first.estimated_tokens_after, second.estimated_tokens_after)

    def test_api_message_format_does_not_include_observability_fields(self) -> None:
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Current task"},
        ]

        result = self.optimizer.prepare(messages, OptimizationLevel.LIGHT)

        self.assertTrue(result.protection.protected_message_count)
        self.assertTrue(
            all(set(message) == {"role", "content"} for message in result.messages)
        )

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

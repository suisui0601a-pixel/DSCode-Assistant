"""Offscreen smoke tests for the DSCode Assistant desktop UI."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
)

import dscode_assistant.chat_widget as chat_widget_module
from dscode_assistant.context import ContextResult, OptimizationLevel
from dscode_assistant.database import Database
from dscode_assistant.diagnostics import (
    configure_exception_logging,
    record_exception,
    shutdown_exception_logging,
)
from dscode_assistant.main_window import MainWindow
from dscode_assistant.markdown_renderer import MarkdownRenderer
from dscode_assistant.models import ChatMessage, MessageRole
from dscode_assistant.settings_dialog import SettingsDialog
from dscode_assistant.about_dialog import AboutDialog
from dscode_assistant import __version__
from dscode_assistant.ui_components import (
    ChatInputEdit,
    CodeBlockWidget,
    MessageBubble,
    WelcomeWidget,
)


class FakeSettings:
    def __init__(self, data_dir: Path, context_mode: str | None = None) -> None:
        self._data_dir = data_dir
        self._context_mode = context_mode

    def get_data_dir(self) -> Path:
        return self._data_dir

    def load(self) -> dict[str, str | int | float]:
        settings: dict[str, str | int | float] = {
            "model": "deepseek-v4-flash",
            "temperature": 0.7,
            "max_tokens": 256,
            "request_timeout": 10.0,
            "theme": "system",
        }
        if self._context_mode is not None:
            settings["context_optimization_mode"] = self._context_mode
        return settings

    def save(self, _values: object) -> None:
        return

    def get_api_key(self) -> str:
        return "test-key"

    def has_api_key(self) -> bool:
        return True

    def set_api_key(self, _value: str) -> None:
        return

    def delete_api_key(self) -> None:
        return


class FakeWorker(QObject):
    chunk_received = Signal(str)
    completed = Signal()
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()
    last_instance: "FakeWorker | None" = None

    def __init__(self, _client: object, messages: list[dict[str, str]], _options: object):
        super().__init__()
        self.messages = messages
        self.running = False
        FakeWorker.last_instance = self

    def start(self) -> None:
        self.running = True

    def isRunning(self) -> bool:
        return self.running

    def cancel(self) -> None:
        self.running = False
        self.cancelled.emit()
        self.finished.emit()

    def wait(self, _timeout: int) -> bool:
        return True


class CaptureContextOptimizer:
    def __init__(self, before: int = 1, after: int = 1) -> None:
        self.messages: list[dict[str, str]] | None = None
        self.level: OptimizationLevel | None = None
        self.before = before
        self.after = after

    def prepare(
        self,
        messages: list[dict[str, str]],
        level: OptimizationLevel,
    ) -> ContextResult:
        self.messages = [dict(message) for message in messages]
        self.level = level
        return ContextResult(
            messages=[dict(message) for message in messages],
            level=level,
            estimated_tokens_before=self.before,
            estimated_tokens_after=self.after,
        )


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.settings = FakeSettings(Path(self.temporary_directory.name))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_main_window_starts_on_welcome_and_closes(self) -> None:
        window = MainWindow(Database(self.settings), self.settings)
        window.show()
        self.application.processEvents()

        stack = window.findChild(QStackedWidget)
        self.assertTrue(window.isVisible())
        self.assertIsInstance(stack.currentWidget(), WelcomeWidget)
        self.assertEqual(window.chat_widget._input.height(), 68)

        window.close()
        self.application.processEvents()
        self.assertFalse(window.isVisible())

    def test_main_window_passes_injected_context_optimizer_to_chat(self) -> None:
        optimizer = CaptureContextOptimizer()
        window = MainWindow(
            Database(self.settings),
            self.settings,
            context_optimizer=optimizer,
        )

        self.assertIs(window.chat_widget._context_optimizer, optimizer)

        window.close()
        self.application.processEvents()

    def test_send_button_starts_chat_worker(self) -> None:
        original_worker = chat_widget_module.ChatWorker
        chat_widget_module.ChatWorker = FakeWorker
        try:
            database = Database(self.settings)
            window = MainWindow(database, self.settings)
            window.new_chat()
            self.application.processEvents()

            window.chat_widget._input.setPlainText("Explain a Python generator")
            window.chat_widget._send_button.click()
            self.application.processEvents()

            worker = FakeWorker.last_instance
            self.assertIsNotNone(worker)
            self.assertTrue(worker.running)
            self.assertEqual(
                worker.messages[-1],
                {"role": "user", "content": "Explain a Python generator"},
            )

            window.close()
            self.application.processEvents()
        finally:
            chat_widget_module.ChatWorker = original_worker

    def test_send_prepares_raw_context_before_starting_worker(self) -> None:
        original_worker = chat_widget_module.ChatWorker
        chat_widget_module.ChatWorker = FakeWorker
        try:
            database = Database(self.settings)
            window = MainWindow(database, self.settings)
            window.new_chat()
            optimizer = CaptureContextOptimizer()
            window.chat_widget._context_optimizer = optimizer

            window.chat_widget.set_draft_text("Keep the current request flow")
            window.chat_widget.send_message()
            self.application.processEvents()

            worker = FakeWorker.last_instance
            self.assertIsNotNone(worker)
            self.assertEqual(optimizer.level, OptimizationLevel.RAW)
            self.assertEqual(worker.messages, optimizer.messages)
            self.assertEqual(
                optimizer.messages[-1],
                {"role": "user", "content": "Keep the current request flow"},
            )

            window.close()
            self.application.processEvents()
        finally:
            chat_widget_module.ChatWorker = original_worker

    def test_light_setting_optimizes_request_and_displays_token_statistics(self) -> None:
        original_worker = chat_widget_module.ChatWorker
        chat_widget_module.ChatWorker = FakeWorker
        try:
            settings = FakeSettings(
                Path(self.temporary_directory.name),
                context_mode="light",
            )
            database = Database(settings)
            window = MainWindow(database, settings)
            window.new_chat()
            session_id = window.chat_widget.active_session_id
            self.assertIsNotNone(session_id)
            database.add_message(session_id, MessageRole.USER, "First detail")
            database.add_message(session_id, MessageRole.USER, "Second detail")
            session = next(
                item for item in database.list_sessions() if item.id == session_id
            )
            window.chat_widget.set_session(session)

            window.chat_widget.set_draft_text("Third detail")
            window.chat_widget.send_message()
            self.application.processEvents()

            worker = FakeWorker.last_instance
            self.assertIsNotNone(worker)
            self.assertEqual(
                worker.messages[-2:],
                [
                {
                    "role": "user",
                    "content": "First detail\n\nSecond detail",
                },
                {"role": "user", "content": "Third detail"},
                ],
            )
            stats = window.chat_widget._context_stats_label.text()
            self.assertIn("优化前估算 Token：", stats)
            self.assertIn("优化后估算 Token：", stats)
            self.assertIn("减少比例：", stats)
            window.close()
            self.application.processEvents()
        finally:
            chat_widget_module.ChatWorker = original_worker

    def test_context_statistics_use_optimizer_result(self) -> None:
        original_worker = chat_widget_module.ChatWorker
        chat_widget_module.ChatWorker = FakeWorker
        try:
            database = Database(self.settings)
            window = MainWindow(database, self.settings)
            window.new_chat()
            optimizer = CaptureContextOptimizer(before=100, after=75)
            window.chat_widget._context_optimizer = optimizer
            window.chat_widget.set_draft_text("Measure this request")
            window.chat_widget.send_message()
            self.application.processEvents()

            self.assertEqual(
                window.chat_widget._context_stats_label.text(),
                "优化前估算 Token：100　优化后估算 Token：75　减少比例：25.0%",
            )
            window.close()
            self.application.processEvents()
        finally:
            chat_widget_module.ChatWorker = original_worker

    def test_auto_setting_is_reserved_and_currently_uses_raw(self) -> None:
        self.assertEqual(
            chat_widget_module.ChatWidget._context_level_from_settings(
                {"context_optimization_mode": "auto"}
            ),
            OptimizationLevel.RAW,
        )

    def test_chat_input_enter_and_shift_enter(self) -> None:
        editor = ChatInputEdit()
        send_count = 0

        def record_send() -> None:
            nonlocal send_count
            send_count += 1

        editor.send_requested.connect(record_send)
        editor.show()
        editor.setFocus()
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.assertEqual(send_count, 1)
        self.assertEqual(editor.toPlainText(), "")

        QTest.keyClick(
            editor,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        self.assertEqual(send_count, 1)
        self.assertEqual(editor.toPlainText(), "\n")
        editor.close()

    def test_message_copy_controls_and_language_label(self) -> None:
        message = ChatMessage(
            session_id=1,
            role=MessageRole.ASSISTANT,
            content="Example:\n```python\nprint('ok')\n```",
        )
        bubble = MessageBubble(message, MarkdownRenderer())
        bubble.show()
        self.application.processEvents()

        code_block = bubble.findChild(CodeBlockWidget)
        self.assertIsNotNone(code_block)
        self.assertTrue(
            any(label.text() == "python" for label in bubble.findChildren(QLabel))
        )
        code_copy = next(
            button
            for button in code_block.findChildren(QPushButton)
            if button.text() == "复制代码"
        )
        code_copy.click()
        self.assertEqual(QApplication.clipboard().text(), "print('ok')")

        copy_full = next(
            button
            for button in bubble.findChildren(QPushButton)
            if button.text() == "复制全文"
        )
        copy_full.click()
        self.assertEqual(QApplication.clipboard().text(), message.content)
        bubble.close()

    def test_stream_render_preserves_manual_scroll_position(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Scroll test", "deepseek-v4-flash")
        for index in range(18):
            database.add_message(
                session.id,
                MessageRole.ASSISTANT,
                f"Message {index}\n\nAdditional content for scrolling.",
            )

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(session.id)
            self.application.processEvents()
            bar = window.chat_widget._message_scroll.verticalScrollBar()
            self.assertGreater(bar.maximum(), 0)

            bar.setValue(0)
            window.chat_widget._messages.append(
                ChatMessage(
                    session_id=session.id,
                    role=MessageRole.ASSISTANT,
                    content="New streamed content",
                )
            )
            window.chat_widget._render_messages()
            self.application.processEvents()
            self.assertEqual(bar.value(), 0)
        finally:
            window.close()
            self.application.processEvents()

    def test_repeated_full_render_keeps_message_bubble_count_stable(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Render lifecycle", "deepseek-v4-flash")
        for index in range(4):
            database.add_message(
                session.id,
                MessageRole.USER if index % 2 == 0 else MessageRole.ASSISTANT,
                f"Message {index}",
            )

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(session.id)
            self.application.processEvents()
            self.assertEqual(
                len(window.chat_widget._message_canvas.findChildren(MessageBubble)),
                4,
            )

            for _ in range(10):
                window.chat_widget._render_messages()
                self.application.processEvents()
                self.assertEqual(
                    len(window.chat_widget._message_canvas.findChildren(MessageBubble)),
                    4,
                )
        finally:
            window.close()
            self.application.processEvents()

    def test_streaming_chunks_reuse_current_assistant_bubble(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Streaming lifecycle", "deepseek-v4-flash")
        database.add_message(session.id, MessageRole.USER, "Write code")
        assistant = database.add_message(
            session.id,
            MessageRole.ASSISTANT,
            "",
            chat_widget_module.MessageStatus.STREAMING,
        )

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(session.id)
            widget = window.chat_widget
            widget._assistant_message = assistant
            widget._messages[-1] = assistant
            widget._render_messages()
            self.application.processEvents()
            assistant_bubble = widget._assistant_bubble
            self.assertIsNotNone(assistant_bubble)

            for _ in range(100):
                widget._on_chunk_received("x")
                self.application.processEvents()
                self.assertEqual(
                    len(widget._message_canvas.findChildren(MessageBubble)),
                    2,
                )
                self.assertIs(widget._assistant_bubble, assistant_bubble)
        finally:
            window.close()
            self.application.processEvents()

    def test_streaming_does_not_create_detached_top_level_widgets(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Top-level lifecycle", "deepseek-v4-flash")
        database.add_message(session.id, MessageRole.USER, "Explain code")
        assistant = database.add_message(
            session.id,
            MessageRole.ASSISTANT,
            "",
            chat_widget_module.MessageStatus.STREAMING,
        )

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(session.id)
            widget = window.chat_widget
            widget._assistant_message = assistant
            widget._messages[-1] = assistant
            widget._render_messages()
            self.application.processEvents()
            baseline = set(QApplication.topLevelWidgets())

            for _ in range(100):
                widget._on_chunk_received("streamed content ")
                self.application.processEvents()
                self.assertEqual(set(QApplication.topLevelWidgets()), baseline)
        finally:
            window.close()
            self.application.processEvents()

    def test_plain_text_stream_reuses_text_browser_for_100_chunks(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Plain stream", "deepseek-v4-flash")
        database.add_message(session.id, MessageRole.USER, "Explain text")
        assistant = database.add_message(
            session.id,
            MessageRole.ASSISTANT,
            "",
            chat_widget_module.MessageStatus.STREAMING,
        )

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(session.id)
            widget = window.chat_widget
            widget._assistant_message = assistant
            widget._messages[-1] = assistant
            widget._render_messages()
            self.application.processEvents()
            text_view = widget._assistant_bubble.findChild(QTextBrowser)
            self.assertIsNotNone(text_view)

            for _ in range(100):
                widget._on_chunk_received("plain streamed text ")
                self.application.processEvents()
                views = widget._assistant_bubble.findChildren(QTextBrowser)
                self.assertEqual(len(views), 1)
                self.assertIs(views[0], text_view)
        finally:
            window.close()
            self.application.processEvents()

    def test_streamed_markdown_blocks_are_ordered_and_do_not_overlap(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Markdown layout", "deepseek-v4-flash")
        database.add_message(session.id, MessageRole.USER, "Write code")
        assistant = database.add_message(
            session.id,
            MessageRole.ASSISTANT,
            "",
            chat_widget_module.MessageStatus.STREAMING,
        )

        window = MainWindow(database, self.settings)
        try:
            window.resize(1000, 760)
            window.show()
            window.refresh_history(session.id)
            widget = window.chat_widget
            widget._assistant_message = assistant
            widget._messages[-1] = assistant
            widget._render_messages()
            self.application.processEvents()

            fence = chr(96) * 3
            widget._on_chunk_received(
                "正文第一段\n\n"
                + fence
                + "python\nprint('stable')\n"
                + fence
                + "\n\n后续正文"
            )
            self.application.processEvents()
            bubble = widget._assistant_bubble
            code_block = bubble.findChild(CodeBlockWidget)
            self.assertIsNotNone(code_block)

            for _ in range(50):
                widget._on_chunk_received(" 后续文本")
                self.application.processEvents()
                self.assertIs(bubble.findChild(CodeBlockWidget), code_block)

            content_widgets = bubble._content_widgets
            self.assertEqual(len(content_widgets), 3)
            self.assertIsInstance(content_widgets[0], QTextBrowser)
            self.assertIsInstance(content_widgets[1], CodeBlockWidget)
            self.assertIsInstance(content_widgets[2], QTextBrowser)
            for first, second in zip(content_widgets, content_widgets[1:]):
                self.assertLess(first.geometry().bottom(), second.geometry().top())
                self.assertFalse(first.geometry().intersects(second.geometry()))
            for text_view in bubble.findChildren(QTextBrowser):
                self.assertGreaterEqual(
                    text_view.height(),
                    int(text_view.document().size().height()),
                )
        finally:
            window.close()
            self.application.processEvents()

    def test_thousand_character_text_expands_without_inner_scroll(self) -> None:
        message = ChatMessage(
            session_id=1,
            role=MessageRole.ASSISTANT,
            content="长文本内容" * 250,
        )
        bubble = MessageBubble(message, MarkdownRenderer())
        try:
            bubble.resize(700, 100)
            bubble.show()
            self.application.processEvents()
            text_view = bubble.findChild(QTextBrowser)
            self.assertIsNotNone(text_view)
            self.assertEqual(text_view.verticalScrollBar().maximum(), 0)
            self.assertGreaterEqual(
                text_view.height(),
                int(text_view.document().size().height()),
            )
            self.assertGreater(bubble.height(), text_view.height())
        finally:
            bubble.close()

    def test_long_code_block_expands_all_lines_without_vertical_scroll(self) -> None:
        fence = chr(96) * 3
        code = "\n".join(f"value_{index} = {index}" for index in range(200))
        message = ChatMessage(
            session_id=1,
            role=MessageRole.ASSISTANT,
            content="代码如下：\n" + fence + "python\n" + code + "\n" + fence + "\n完成。",
        )
        bubble = MessageBubble(message, MarkdownRenderer())
        try:
            bubble.resize(700, 100)
            bubble.show()
            self.application.processEvents()
            code_view = bubble.findChild(QPlainTextEdit, "codeView")
            self.assertIsNotNone(code_view)
            self.assertEqual(code_view.document().blockCount(), 200)
            self.assertEqual(code_view.verticalScrollBar().maximum(), 0)
            minimum_full_height = (
                code_view.document().blockCount()
                * code_view.fontMetrics().lineSpacing()
            )
            self.assertGreaterEqual(code_view.height(), minimum_full_height)
            parts = bubble._content_widgets
            for first, second in zip(parts, parts[1:]):
                self.assertFalse(first.geometry().intersects(second.geometry()))
        finally:
            bubble.close()

    def test_streamed_text_dynamically_grows_bubble_height(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Growing bubble", "deepseek-v4-flash")
        database.add_message(session.id, MessageRole.USER, "Generate long text")
        assistant = database.add_message(
            session.id,
            MessageRole.ASSISTANT,
            "short",
            chat_widget_module.MessageStatus.STREAMING,
        )
        window = MainWindow(database, self.settings)
        try:
            window.resize(1000, 760)
            window.show()
            window.refresh_history(session.id)
            widget = window.chat_widget
            widget._assistant_message = assistant
            widget._messages[-1] = assistant
            widget._render_messages()
            self.application.processEvents()
            bubble = widget._assistant_bubble
            initial_height = bubble.height()

            for _ in range(100):
                widget._on_chunk_received("持续增长的流式正文内容。")
                self.application.processEvents()

            self.assertGreater(bubble.height(), initial_height)
            text_view = bubble.findChild(QTextBrowser)
            self.assertEqual(text_view.verticalScrollBar().maximum(), 0)
        finally:
            window.close()
            self.application.processEvents()

    def test_bubble_reflows_on_width_change_without_text_clipping(self) -> None:
        message = ChatMessage(
            session_id=1,
            role=MessageRole.ASSISTANT,
            content="窗口缩放后的正文需要重新换行并完整显示。" * 80,
        )
        bubble = MessageBubble(message, MarkdownRenderer())
        try:
            bubble.resize(780, 100)
            bubble.show()
            self.application.processEvents()
            text_view = bubble.findChild(QTextBrowser)
            wide_height = text_view.height()

            bubble.resize(560, bubble.height())
            self.application.processEvents()
            narrow_height = text_view.height()
            self.assertGreater(narrow_height, wide_height)
            self.assertEqual(text_view.verticalScrollBar().maximum(), 0)
            self.assertGreaterEqual(
                text_view.height(),
                int(text_view.document().size().height()),
            )
        finally:
            bubble.close()

    def test_switching_to_empty_session_removes_old_message_widgets(self) -> None:
        database = Database(self.settings)
        database.initialize()
        populated = database.create_session("Populated", "deepseek-v4-flash")
        for index in range(4):
            database.add_message(populated.id, MessageRole.ASSISTANT, f"Message {index}")
        empty = database.create_session("Empty", "deepseek-v4-flash")

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.chat_widget.set_session(populated)
            self.application.processEvents()
            self.assertEqual(
                len(window.chat_widget._message_canvas.findChildren(MessageBubble)),
                4,
            )

            window.chat_widget.set_session(empty)
            self.application.processEvents()
            self.assertEqual(
                len(window.chat_widget._message_canvas.findChildren(MessageBubble)),
                0,
            )
        finally:
            window.close()
            self.application.processEvents()

    def test_long_streamed_code_reply_keeps_single_code_block(self) -> None:
        database = Database(self.settings)
        database.initialize()
        session = database.create_session("Code lifecycle", "deepseek-v4-flash")
        database.add_message(session.id, MessageRole.USER, "Write long code")
        assistant = database.add_message(
            session.id,
            MessageRole.ASSISTANT,
            "",
            chat_widget_module.MessageStatus.STREAMING,
        )
        payload = "正文\n```python\n" + "\n".join(
            f"value_{index} = {index}" for index in range(120)
        ) + "\n```"
        chunk_size = max(1, len(payload) // 100)
        chunks = [payload[index:index + chunk_size] for index in range(0, len(payload), chunk_size)]

        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(session.id)
            widget = window.chat_widget
            widget._assistant_message = assistant
            widget._messages[-1] = assistant
            widget._render_messages()
            self.application.processEvents()

            for chunk in chunks:
                widget._on_chunk_received(chunk)
                self.application.processEvents()
                self.assertEqual(
                    len(widget._message_canvas.findChildren(MessageBubble)),
                    2,
                )

            self.assertEqual(
                len(widget._assistant_bubble.findChildren(CodeBlockWidget)),
                1,
            )
            copy_buttons = [
                button.text()
                for button in widget._assistant_bubble.findChildren(QPushButton)
            ]
            self.assertEqual(copy_buttons.count("复制全文"), 1)
            self.assertEqual(copy_buttons.count("复制代码"), 1)
        finally:
            window.close()
            self.application.processEvents()

    def test_conversation_search_and_rename(self) -> None:
        database = Database(self.settings)
        database.initialize()
        first = database.create_session("Python helpers", "deepseek-v4-flash")
        database.create_session("SQL query", "deepseek-v4-flash")
        window = MainWindow(database, self.settings)
        try:
            window.show()
            window.refresh_history(first.id)
            window._search_input.setText("python")
            self.application.processEvents()
            visible_items = [
                window._history_list.item(index)
                for index in range(window._history_list.count())
                if not window._history_list.item(index).isHidden()
            ]
            self.assertEqual(len(visible_items), 1)

            target = visible_items[0]
            with patch(
                "dscode_assistant.main_window.QInputDialog.getText",
                return_value=("Renamed session", True),
            ):
                window.rename_chat(target)
            self.assertEqual(
                next(item for item in database.list_sessions() if item.id == first.id).title,
                "Renamed session",
            )
        finally:
            window.close()
            self.application.processEvents()

    def test_first_completed_message_generates_local_title(self) -> None:
        original_worker = chat_widget_module.ChatWorker
        chat_widget_module.ChatWorker = FakeWorker
        try:
            database = Database(self.settings)
            window = MainWindow(database, self.settings)
            window.new_chat()
            self.application.processEvents()
            session_id = window.chat_widget.active_session_id
            window.chat_widget._input.setPlainText(
                "Explain how Python context managers work"
            )
            window.chat_widget._send_button.click()
            worker = FakeWorker.last_instance
            worker.chunk_received.emit("A context manager controls resource scope.")
            worker.completed.emit()
            worker.running = False
            worker.finished.emit()
            self.application.processEvents()
            title = next(
                item.title for item in database.list_sessions() if item.id == session_id
            )
            self.assertTrue(title.startswith("Explain how Python context"))
            self.assertLessEqual(len(title), 30)
            window.close()
            self.application.processEvents()
        finally:
            chat_widget_module.ChatWorker = original_worker

    def test_settings_clear_history_and_connection_feedback(self) -> None:
        database = Database(self.settings)
        database.initialize()
        database.create_session("Temporary history", "deepseek-v4-flash")
        dialog = SettingsDialog(self.settings, database)
        history_signal_count = 0

        def record_clear() -> None:
            nonlocal history_signal_count
            history_signal_count += 1

        dialog.history_cleared.connect(record_clear)
        clear_button = next(
            button
            for button in dialog.findChildren(QPushButton)
            if button.text() == "清理历史记录"
        )
        with (
            patch(
                "dscode_assistant.settings_dialog.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch("dscode_assistant.settings_dialog.QMessageBox.information"),
        ):
            clear_button.click()
        self.assertEqual(database.list_sessions(), [])
        self.assertEqual(history_signal_count, 1)

        dialog._connection_succeeded()
        self.assertEqual(dialog._connection_status.text(), "连接成功")
        dialog.close()
        database.close()

    def test_about_dialog_displays_current_version(self) -> None:
        dialog = AboutDialog()
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        self.assertIn(f"版本 {__version__}", labels)
        dialog.close()

    def test_exception_log_excludes_exception_message(self) -> None:
        log_path = configure_exception_logging(Path(self.temporary_directory.name))
        try:
            try:
                raise RuntimeError("SECRET CHAT CONTENT")
            except RuntimeError as error:
                record_exception(type(error), error.__traceback__)
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("RuntimeError", log_text)
            self.assertNotIn("SECRET CHAT CONTENT", log_text)
        finally:
            shutdown_exception_logging()

    def test_settings_dialog_refuses_close_during_connection_test(self) -> None:
        class RunningWorker:
            running = True

            def isRunning(self) -> bool:
                return self.running

        dialog = SettingsDialog(self.settings)
        worker = RunningWorker()
        dialog._test_worker = worker
        dialog.show()
        self.application.processEvents()
        dialog.reject()
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog._connection_status.text(), "请等待测试完成")
        worker.running = False
        dialog.reject()
        self.application.processEvents()
        self.assertFalse(dialog.isVisible())


if __name__ == "__main__":
    unittest.main()

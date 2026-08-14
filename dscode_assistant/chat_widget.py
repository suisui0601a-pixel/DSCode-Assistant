"""Chat interface for DSCode Assistant."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import delete as delete_qt_object

from .api_client import ChatWorker, DeepSeekClient
from .context import ContextOptimizer, ContextResult, OptimizationLevel
from .database import Database
from .markdown_renderer import MarkdownRenderer
from .model_providers import DeepSeekProvider, OpenAICompatibleProvider
from .models import (
    ChatMessage,
    ChatOptions,
    ChatSession,
    MessageRole,
    MessageStatus,
)
from .prompts import PROMPT_TEMPLATES
from .settings import (
    CONTEXT_OPTIMIZATION_AUTO,
    CONTEXT_OPTIMIZATION_LIGHT,
    OPENAI_COMPATIBLE_PROVIDER_ID,
    SettingsManager,
    get_active_model,
    get_context_optimization_mode,
    get_provider_id,
    is_provider_configured,
)
from .ui_components import ChatInputWidget, MessageBubble, StatusBadge


class ChatWidget(QWidget):
    """Display a conversation and coordinate its streaming API request."""

    history_changed = Signal(int)

    def __init__(
        self,
        database: Database,
        settings_manager: SettingsManager,
        context_optimizer: ContextOptimizer | None = None,
    ) -> None:
        super().__init__()
        self._database = database
        self._settings_manager = settings_manager
        self._renderer = MarkdownRenderer()
        self._context_optimizer = (
            context_optimizer
            if context_optimizer is not None
            else ContextOptimizer()
        )
        self._session: ChatSession | None = None
        self._messages: list[ChatMessage] = []
        self._worker: ChatWorker | None = None
        self._assistant_message: ChatMessage | None = None
        self._assistant_bubble: MessageBubble | None = None
        self._shutting_down = False

        self._title_label = QLabel("新对话")
        self._title_label.setObjectName("chatTitle")
        self._model_label = QLabel("未选择模型")
        self._model_label.setObjectName("modelLabel")
        self._context_stats_label = QLabel("上下文：尚未估算")
        self._context_stats_label.setObjectName("contextStatsLabel")
        self._status_badge = StatusBadge("就绪", "ready")

        self._message_canvas = QWidget()
        self._message_canvas.setObjectName("messageCanvas")
        self._message_layout = QVBoxLayout(self._message_canvas)
        self._message_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self._message_layout.setContentsMargins(34, 24, 34, 24)
        self._message_layout.setSpacing(16)
        self._message_layout.addStretch(1)

        self._message_scroll = QScrollArea()
        self._message_scroll.setObjectName("messageScroll")
        self._message_scroll.setWidgetResizable(True)
        self._message_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._message_scroll.setWidget(self._message_canvas)

        self._composer = ChatInputWidget()
        self._composer.send_requested.connect(self.send_message)
        self._composer.stop_requested.connect(self.stop_generation)

        # Compatibility aliases retained for existing tests and behavior.
        self._input = self._composer.editor
        self._prompt_combo = self._composer.prompt_combo
        self._send_button = self._composer.send_button
        self._stop_button = self._composer.stop_button

        self._build_ui()

    def _build_ui(self) -> None:
        header = QFrame()
        header.setObjectName("chatHeader")
        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        title_column.addWidget(self._title_label)
        title_column.addWidget(self._model_label)
        title_column.addWidget(self._context_stats_label)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 14, 24, 14)
        header_layout.addLayout(title_column)
        header_layout.addStretch(1)
        header_layout.addWidget(self._status_badge)

        composer_container = QWidget()
        composer_layout = QHBoxLayout(composer_container)
        composer_layout.setContentsMargins(28, 12, 28, 20)
        composer_layout.addWidget(self._composer)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._message_scroll, 1)
        layout.addWidget(composer_container)

    def current_prompt_id(self) -> str:
        """Return the selected built-in prompt identifier."""
        prompt_id = self._prompt_combo.currentData()
        return str(prompt_id or "python")

    @property
    def is_generating(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @property
    def active_session_id(self) -> int | None:
        return self._session.id if self._session is not None else None

    def set_draft_text(self, text: str) -> None:
        """Place locally supplied text in the composer without sending it."""
        self._input.setPlainText(text)
        self._input.setFocus()

    def set_session(self, session: ChatSession) -> None:
        """Load a local session into the chat view."""
        if self._worker is not None and self._worker.isRunning():
            self.stop_generation()

        self._session = session
        self._messages = self._database.get_messages(session.id or 0)
        self._assistant_message = None
        self._title_label.setText(session.title)
        self._model_label.setText(session.model)
        self._status_badge.set_status("就绪", "ready")

        prompt_index = self._prompt_combo.findData(session.prompt_id)
        if prompt_index >= 0:
            self._prompt_combo.setCurrentIndex(prompt_index)

        self._render_messages(reset_scroll=True)

    def send_message(self) -> None:
        """Save the user message and start a background streaming request."""
        if self._worker is not None and self._worker.isRunning():
            return
        if self._session is None or self._session.id is None:
            QMessageBox.warning(self, "无法发送", "请先创建一个会话。")
            return
        settings = self._settings_manager.load()
        if not is_provider_configured(self._settings_manager):
            QMessageBox.warning(self, "模型未配置", "请先在设置中完成模型提供商配置。")
            return

        user_text = self._input.toPlainText().strip()
        if not user_text:
            return

        user_message = self._database.add_message(
            self._session.id,
            MessageRole.USER,
            user_text,
        )
        self._messages.append(user_message)
        self._input.clear()

        raw_request_messages = self._build_request_messages()
        context_result = self._context_optimizer.prepare(
            raw_request_messages,
            self._context_level_from_settings(settings),
        )
        self._show_context_statistics(context_result)
        request_messages = context_result.messages
        assistant_message = self._database.add_message(
            self._session.id,
            MessageRole.ASSISTANT,
            "",
            MessageStatus.STREAMING,
        )
        self._assistant_message = assistant_message
        self._messages.append(assistant_message)
        self._render_messages()

        options = ChatOptions(
            model=get_active_model(settings),
            temperature=float(settings["temperature"]),
            max_tokens=int(settings["max_tokens"]),
            request_timeout=float(settings["request_timeout"]),
        )
        provider_id = get_provider_id(settings)
        if provider_id == OPENAI_COMPATIBLE_PROVIDER_ID:
            client = OpenAICompatibleProvider(
                str(settings["openai_compatible_base_url"]),
                api_key=lambda: self._settings_manager.get_provider_api_key(
                    OPENAI_COMPATIBLE_PROVIDER_ID
                ),
            )
        else:
            client = DeepSeekProvider(DeepSeekClient(self._settings_manager))
        worker = ChatWorker(client, request_messages, options)
        worker.chunk_received.connect(self._on_chunk_received)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._set_generating(True)
        worker.start()

    @staticmethod
    def _context_level_from_settings(
        settings: dict[str, str | int | float],
    ) -> OptimizationLevel:
        mode = get_context_optimization_mode(settings)
        if mode == CONTEXT_OPTIMIZATION_LIGHT:
            return OptimizationLevel.LIGHT
        # Auto is configuration-only in this phase and intentionally behaves as Raw.
        if mode == CONTEXT_OPTIMIZATION_AUTO:
            return OptimizationLevel.RAW
        return OptimizationLevel.RAW

    def _show_context_statistics(self, result: ContextResult) -> None:
        before = result.estimated_tokens_before
        after = result.estimated_tokens_after
        reduction = result.estimated_reduction_percent
        self._context_stats_label.setText(
            f"优化前估算 Token：{before}　"
            f"优化后估算 Token：{after}　"
            f"减少比例：{reduction:.1f}%"
        )

    def _build_request_messages(self) -> list[dict[str, str]]:
        prompt = PROMPT_TEMPLATES[self.current_prompt_id()]
        request_messages = [
            {
                "role": MessageRole.SYSTEM.value,
                "content": prompt["system_prompt"],
            }
        ]
        request_messages.extend(
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in self._messages
            if message.content
            and message.status
            in {MessageStatus.COMPLETED, MessageStatus.CANCELLED}
        )
        return request_messages

    def _on_chunk_received(self, chunk: str) -> None:
        if self._shutting_down or self._assistant_message is None:
            return
        self._assistant_message.content += chunk
        self._update_streaming_message()

    def _on_completed(self) -> None:
        if not self._shutting_down:
            self._finish_assistant_message(MessageStatus.COMPLETED)

    def _on_failed(self, message: str) -> None:
        if self._shutting_down:
            return
        self._finish_assistant_message(MessageStatus.FAILED)
        QMessageBox.warning(self, "请求失败", message)

    def _on_cancelled(self) -> None:
        if not self._shutting_down:
            self._finish_assistant_message(MessageStatus.CANCELLED)

    def _finish_assistant_message(self, status: MessageStatus) -> None:
        updated: ChatMessage | None = None
        if self._assistant_message is not None and self._assistant_message.id is not None:
            updated = self._database.update_message(
                self._assistant_message.id,
                self._assistant_message.content,
                status,
            )
            self._messages[-1] = updated
        if updated is not None and self._assistant_bubble is not None:
            self._assistant_bubble.update_message(updated)
        self._assistant_message = None
        self._assistant_bubble = None
        self._worker = None
        self._set_generating(False)

        if self._session is not None and self._session.id is not None:
            self._rename_new_session()
            self.history_changed.emit(self._session.id)

    def _rename_new_session(self) -> None:
        if self._session is None or self._session.id is None:
            return
        if self._session.title != "新对话":
            return

        first_user_message = next(
            (
                message.content
                for message in self._messages
                if message.role == MessageRole.USER and message.content
            ),
            "",
        )
        if first_user_message:
            title = first_user_message.replace("\n", " ").strip()[:30]
            self._database.rename_session(self._session.id, title)
            self._session.title = title
            self._title_label.setText(title)

    def stop_generation(self) -> None:
        """Request cancellation of the active background request."""
        if self._worker is not None and self._worker.isRunning():
            self._stop_button.setEnabled(False)
            self._status_badge.set_status("正在停止…", "generating")
            self._worker.cancel()

    def shutdown(self) -> bool:
        """Cancel active work and report whether the worker has stopped."""
        if self._worker is not None and self._worker.isRunning():
            self._shutting_down = True
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._shutting_down = False
                return False

            if self._assistant_message is not None and self._assistant_message.id is not None:
                self._database.update_message(
                    self._assistant_message.id,
                    self._assistant_message.content,
                    MessageStatus.CANCELLED,
                )
            self._assistant_message = None
            self._worker = None
        return True

    def _set_generating(self, generating: bool) -> None:
        self._composer.set_generating(generating)
        if generating:
            self._status_badge.set_status("正在生成…", "generating")
        else:
            self._status_badge.set_status("就绪", "ready")

    def _clear_message_area(self) -> None:
        """Recursively release every widget and nested layout in the message canvas."""
        while self._message_layout.count():
            item = self._message_layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)
                child_layout.deleteLater()
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                delete_qt_object(widget)

    def _clear_layout(self, layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)
                child_layout.deleteLater()
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                delete_qt_object(widget)

    def _add_message_bubble(self, message: ChatMessage) -> MessageBubble:
        bubble = MessageBubble(message, self._renderer)
        row = QHBoxLayout()
        if message.role == MessageRole.USER:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        self._message_layout.addLayout(row)
        return bubble

    def _update_streaming_message(self) -> None:
        if self._assistant_message is None or self._assistant_bubble is None:
            return
        scroll_bar = self._message_scroll.verticalScrollBar()
        should_follow_output = scroll_bar.maximum() - scroll_bar.value() <= 48
        self._assistant_bubble.update_message(self._assistant_message)
        if should_follow_output:
            QTimer.singleShot(
                0,
                lambda: self._message_scroll.verticalScrollBar().setValue(
                    self._message_scroll.verticalScrollBar().maximum()
                ),
            )

    def _render_messages(self, reset_scroll: bool = False) -> None:
        scroll_bar = self._message_scroll.verticalScrollBar()
        previous_value = scroll_bar.value()
        should_follow_output = scroll_bar.maximum() - previous_value <= 48

        self._assistant_bubble = None
        self._clear_message_area()

        for message in self._messages:
            bubble = self._add_message_bubble(message)
            if message is self._assistant_message:
                self._assistant_bubble = bubble

        self._message_layout.addStretch(1)

        def restore_scroll_position() -> None:
            current_bar = self._message_scroll.verticalScrollBar()
            current_bar.setValue(
                current_bar.maximum()
                if reset_scroll or should_follow_output
                else previous_value
            )

        QTimer.singleShot(0, restore_scroll_position)

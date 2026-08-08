"""Reusable PySide6 presentation components for DSCode Assistant."""

from __future__ import annotations

import re
from math import ceil

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontDatabase, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import delete as delete_qt_object

from .markdown_renderer import MarkdownRenderer
from .models import ChatMessage, MessageRole, MessageStatus
from .prompts import PROMPT_TEMPLATES
from . import __version__


class StatusBadge(QLabel):
    """Compact semantic status label styled through QSS properties."""

    def __init__(self, text: str = "就绪", status: str = "ready") -> None:
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(text, status)

    def set_status(self, text: str, status: str) -> None:
        self.setText(text)
        self.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)


class ConversationItem(QWidget):
    """Two-line history item with an elided title and update time."""

    def __init__(self, title: str, updated_at: str) -> None:
        super().__init__()
        self.setObjectName("conversationItem")
        self._title = QLabel(title)
        self._title.setObjectName("conversationTitle")
        self._title.setToolTip(title)
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        timestamp = QLabel(updated_at)
        timestamp.setObjectName("conversationTime")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        layout.addWidget(self._title)
        layout.addWidget(timestamp)

    @property
    def title(self) -> str:
        return self._title.text()


class WelcomeWidget(QWidget):
    """Empty-state page shown before a conversation is selected."""

    new_chat_requested = Signal()
    recent_chat_requested = Signal()
    settings_requested = Signal()

    def __init__(self, has_api_key: bool) -> None:
        super().__init__()
        self.setObjectName("welcomePage")

        mark = QLabel("DS")
        mark.setObjectName("welcomeMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(64, 64)

        title = QLabel("DSCode Assistant")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel("一个本地运行、数据不上传的 DeepSeek 编程助手")
        description.setObjectName("welcomeDescription")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        new_button = QPushButton("新建对话")
        new_button.setObjectName("primaryButton")
        new_button.clicked.connect(self.new_chat_requested)

        recent_button = QPushButton("打开最近会话")
        recent_button.clicked.connect(self.recent_chat_requested)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(new_button)
        actions.addWidget(recent_button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addStretch(2)
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(18)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(description)
        version = QLabel(f"版本 {__version__} · 本地优先 · 无遥测")
        version.setObjectName("modelLabel")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(version)
        layout.addSpacing(24)
        layout.addLayout(actions)

        if not has_api_key:
            api_notice = QFrame()
            api_notice.setObjectName("apiNotice")
            notice_layout = QHBoxLayout(api_notice)
            notice_layout.setContentsMargins(14, 10, 14, 10)
            notice_layout.addWidget(QLabel("尚未配置 API Key，请先完成本地设置。"))
            configure_button = QPushButton("打开设置")
            configure_button.setObjectName("linkButton")
            configure_button.clicked.connect(self.settings_requested)
            notice_layout.addWidget(configure_button)
            layout.addSpacing(20)
            layout.addWidget(api_notice, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(3)


class ChatInputEdit(QPlainTextEdit):
    """Growing multi-line editor where Enter sends and Shift+Enter inserts a line."""

    send_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("chatInput")
        self.setPlaceholderText("输入编程问题，Enter 发送，Shift+Enter 换行…")
        self.setMinimumHeight(68)
        self.setMaximumHeight(180)
        self.setFixedHeight(68)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.textChanged.connect(self._adjust_height)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        document_height = int(self.document().size().height()) + 28
        self.setFixedHeight(max(68, min(180, document_height)))


class ChatInputWidget(QFrame):
    """Composed message editor and its compact action toolbar."""

    send_requested = Signal()
    stop_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("composerCard")

        self.editor = ChatInputEdit()
        self.editor.send_requested.connect(self.send_requested)

        self.prompt_combo = QComboBox()
        self.prompt_combo.setObjectName("promptCombo")
        for prompt_id, prompt in PROMPT_TEMPLATES.items():
            self.prompt_combo.addItem(prompt["name"], prompt_id)

        clear_button = QPushButton("清空")
        clear_button.setObjectName("subtleButton")
        clear_button.clicked.connect(self.editor.clear)

        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_requested)

        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("primaryButton")
        self.send_button.clicked.connect(self.send_requested)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("编程模板"))
        toolbar.addWidget(self.prompt_combo)
        toolbar.addStretch(1)
        toolbar.addWidget(clear_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(self.editor)
        layout.addLayout(toolbar)

    def set_generating(self, generating: bool) -> None:
        self.send_button.setEnabled(not generating)
        self.stop_button.setVisible(generating)
        self.stop_button.setEnabled(generating)
        self.editor.setEnabled(not generating)
        self.prompt_combo.setEnabled(not generating)


class CodeBlockWidget(QFrame):
    """Local, non-WebEngine code block with language and copy controls."""

    def __init__(self, code: str, language: str) -> None:
        super().__init__()
        self.setObjectName("codeBlock")
        self._code = ""

        self._language_label = QLabel(language or "text")
        self._language_label.setObjectName("codeLanguage")
        copy_button = QPushButton("复制代码")
        copy_button.setObjectName("codeCopyButton")
        copy_button.clicked.connect(self._copy_code)

        header = QHBoxLayout()
        header.addWidget(self._language_label)
        header.addStretch(1)
        header.addWidget(copy_button)

        self._code_view = QPlainTextEdit()
        self._code_view.setObjectName("codeView")
        self._code_view.setReadOnly(True)
        self._code_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._code_view.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self._code_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._code_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._code_view.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        self._code_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 10)
        layout.setSpacing(5)
        layout.addLayout(header)
        layout.addWidget(self._code_view)
        self.update_code(code, language)

    def update_code(self, code: str, language: str) -> None:
        """Update code and language without replacing the code block widget."""
        normalized_code = code.rstrip("\n")
        normalized_language = language or "text"
        if self._code != normalized_code:
            self._code = normalized_code
            self._code_view.setPlainText(self._code)
        if self._language_label.text() != normalized_language:
            self._language_label.setText(normalized_language)

        visible_lines = max(2, self._code_view.document().blockCount())
        line_height = self._code_view.fontMetrics().lineSpacing()
        document_margin = ceil(self._code_view.document().documentMargin() * 2)
        frame_height = self._code_view.frameWidth() * 2
        content_padding = 10
        horizontal_scroll_height = self._code_view.horizontalScrollBar().sizeHint().height()
        full_height = (
            visible_lines * line_height
            + document_margin
            + frame_height
            + content_padding
            + horizontal_scroll_height
        )
        self._code_view.setMinimumHeight(full_height)
        self._code_view.setMaximumHeight(full_height)
        self._code_view.updateGeometry()
        if self.layout() is not None:
            self.layout().invalidate()
            self.layout().activate()
        self.updateGeometry()

    def _copy_code(self) -> None:
        QApplication.clipboard().setText(self._code)


class MessageBubble(QFrame):
    """A constrained Markdown message card for user or assistant content."""

    def __init__(self, message: ChatMessage, renderer: MarkdownRenderer) -> None:
        super().__init__()
        self._message = message
        self._renderer = renderer
        self._role = message.role
        self._content_widgets: list[QWidget] = []
        self._content_signature: tuple[str, ...] = ()
        role_name = "user" if message.role == MessageRole.USER else "assistant"
        self.setObjectName("messageBubble")
        self.setProperty("role", role_name)
        self.setMaximumWidth(780)
        self.setMinimumWidth(400 if message.role == MessageRole.USER else 560)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        label = "你" if message.role == MessageRole.USER else "DSCode Assistant"
        status_text = {
            MessageStatus.STREAMING: "正在生成…",
            MessageStatus.CANCELLED: "已停止生成",
            MessageStatus.FAILED: "请求失败",
        }.get(message.status, "")

        name_label = QLabel(label)
        name_label.setObjectName("messageAuthor")
        time_label = QLabel(message.created_at.astimezone().strftime("%H:%M"))
        time_label.setObjectName("messageTime")
        header = QHBoxLayout()
        header.addWidget(name_label)
        header.addWidget(time_label)
        self._state_label = QLabel(status_text)
        self._state_label.setObjectName("messageState")
        self._state_label.setProperty("status", message.status.value)
        self._state_label.setVisible(bool(status_text))
        header.addWidget(self._state_label)
        header.addStretch(1)

        copy_message_button = QPushButton("复制全文")
        copy_message_button.setObjectName("codeCopyButton")
        copy_message_button.clicked.connect(self._copy_message)
        header.addWidget(copy_message_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        layout.addLayout(header)
        self._content_container = QWidget()
        self._content_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        layout.addWidget(self._content_container)
        self._set_content(message.content, message.status == MessageStatus.STREAMING)

    def update_message(self, message: ChatMessage) -> None:
        """Update this bubble without replacing the bubble or its header controls."""
        self._message = message
        status_text = {
            MessageStatus.STREAMING: "正在生成…",
            MessageStatus.CANCELLED: "已停止生成",
            MessageStatus.FAILED: "请求失败",
        }.get(message.status, "")
        self._state_label.setText(status_text)
        self._state_label.setProperty("status", message.status.value)
        self._state_label.setVisible(bool(status_text))
        self._state_label.style().unpolish(self._state_label)
        self._state_label.style().polish(self._state_label)

        self._set_content(message.content, message.status == MessageStatus.STREAMING)

    def _copy_message(self) -> None:
        QApplication.clipboard().setText(self._message.content)

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        """Recursively detach and schedule every item owned by a layout for deletion."""
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                MessageBubble._clear_layout(child_layout)
                child_layout.deleteLater()
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                delete_qt_object(widget)

    @staticmethod
    def _content_parts(markdown_text: str) -> list[tuple[str, str, str]]:
        """Split only fully closed fenced blocks so streaming structure stays stable."""
        pattern = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
        parts: list[tuple[str, str, str]] = []
        position = 0
        for match in pattern.finditer(markdown_text):
            before = markdown_text[position : match.start()]
            if before.strip():
                parts.append(("text", before, ""))
            parts.append(("code", match.group(2), match.group(1).strip()))
            position = match.end()

        remainder = markdown_text[position:]
        if remainder.strip() or not markdown_text:
            parts.append(("text", remainder or " ", ""))
        return parts

    def _set_content(self, markdown_text: str, streaming: bool) -> None:
        parts = self._content_parts(markdown_text)
        signature = tuple(kind for kind, _content, _language in parts)
        if signature != self._content_signature:
            self._clear_layout(self._content_layout)
            self._content_widgets.clear()
            for kind, content, language in parts:
                if kind == "code":
                    widget: QWidget = CodeBlockWidget(content, language)
                else:
                    widget = self._markdown_view()
                self._content_layout.addWidget(widget)
                self._content_widgets.append(widget)
            self._content_signature = signature

        for widget, (kind, content, language) in zip(self._content_widgets, parts):
            if kind == "code" and isinstance(widget, CodeBlockWidget):
                widget.update_code(content, language)
            elif kind == "text" and isinstance(widget, QTextBrowser):
                self._update_text_view(widget, content, streaming)

        self._refresh_content_geometry()

    def _markdown_view(self) -> QTextBrowser:
        content = QTextBrowser()
        content.setObjectName("messageContent")
        content.setOpenExternalLinks(False)
        content.setOpenLinks(False)
        content.setFrameShape(QFrame.Shape.NoFrame)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        content.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.document().setDefaultStyleSheet(
            "h1,h2,h3 { color:#2f3240; margin-top:8px; margin-bottom:5px; } "
            "p { margin:3px 0; } ul,ol { margin:4px 0 4px 18px; } "
            "code { color:#5c568d; background:#eeedf6; font-family:Consolas,monospace; } "
            "blockquote { color:#5f6472; border-left:3px solid #aaa4d8; "
            "margin-left:4px; padding-left:12px; }"
        )
        content.setMinimumHeight(30)
        return content

    def _update_text_view(
        self,
        content: QTextBrowser,
        markdown_text: str,
        streaming: bool,
    ) -> None:
        if streaming:
            if content.toPlainText() != markdown_text:
                content.setPlainText(markdown_text)
        else:
            rendered = self._renderer.render(markdown_text)
            if content.toHtml() != rendered:
                content.setHtml(rendered)

    def _refresh_content_geometry(self) -> None:
        available_width = self._content_container.contentsRect().width()
        if available_width <= 0:
            available_width = 360 if self._role == MessageRole.USER else 520

        for widget in self._content_widgets:
            if isinstance(widget, QTextBrowser):
                widget.document().setTextWidth(max(120, available_width))
                document_height = ceil(widget.document().size().height())
                frame_height = widget.frameWidth() * 2
                full_height = max(34, document_height + frame_height + 4)
                widget.setMinimumHeight(full_height)
                widget.setMaximumHeight(full_height)
                widget.updateGeometry()
            else:
                widget.updateGeometry()

        self._content_layout.invalidate()
        self._content_layout.activate()
        self._content_container.updateGeometry()
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.invalidate()
            root_layout.activate()
        self.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:
        width_changed = event.size().width() != event.oldSize().width()
        super().resizeEvent(event)
        if width_changed:
            self._refresh_content_geometry()

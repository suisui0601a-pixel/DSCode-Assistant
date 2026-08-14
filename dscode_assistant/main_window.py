"""Main application window for DSCode Assistant."""

from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .chat_widget import ChatWidget
from .about_dialog import AboutDialog
from .automation import AutomationRequest
from .context import ContextOptimizer
from .database import Database
from .settings import (
    OPENAI_COMPATIBLE_PROVIDER_ID,
    SettingsManager,
    get_active_model,
    get_provider_id,
    is_provider_configured,
)
from .settings_dialog import SettingsDialog
from .ui_components import ConversationItem, StatusBadge, WelcomeWidget


def _asset_path(filename: str) -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    root = Path(frozen_root) if frozen_root else Path(__file__).resolve().parent.parent
    return root / "assets" / filename


class MainWindow(QMainWindow):
    """Display local chat history and the active conversation."""

    def __init__(
        self,
        database: Database | None = None,
        settings_manager: SettingsManager | None = None,
        context_optimizer: ContextOptimizer | None = None,
    ) -> None:
        super().__init__()
        self._settings_manager = settings_manager or SettingsManager()
        self._database = database or Database(self._settings_manager)
        self._database.initialize()
        self._automation_project_path: Path | None = None
        self._automation_task: dict[str, object] | None = None

        self.setObjectName("appRoot")
        self.setWindowTitle("DSCode Assistant")
        self.resize(1180, 780)
        self.setMinimumSize(900, 620)

        self._history_list = QListWidget()
        self._history_list.setSpacing(2)
        self._history_list.currentItemChanged.connect(self._load_selected_session)
        self._history_list.itemDoubleClicked.connect(self.rename_chat)
        self._history_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._history_list.customContextMenuRequested.connect(
            self._show_history_context_menu
        )

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索会话")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._filter_history)

        self._empty_history = QLabel("暂无历史会话")
        self._empty_history.setObjectName("sectionLabel")
        self._empty_history.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._api_badge = StatusBadge()
        self._update_api_status()

        self._chat_widget = ChatWidget(
            self._database,
            self._settings_manager,
            context_optimizer=context_optimizer,
        )
        self._chat_widget.history_changed.connect(self.refresh_history)

        self._welcome_widget = WelcomeWidget(
            is_provider_configured(self._settings_manager)
        )
        self._welcome_widget.new_chat_requested.connect(self.new_chat)
        self._welcome_widget.recent_chat_requested.connect(self.open_recent_chat)
        self._welcome_widget.settings_requested.connect(self.open_settings)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._welcome_widget)
        self._content_stack.addWidget(self._chat_widget)

        self._build_ui()
        self.refresh_history()
        self._show_welcome()

    def _build_ui(self) -> None:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(320)

        icon = QLabel()
        pixmap = QPixmap(str(_asset_path("app.png")))
        if not pixmap.isNull():
            icon.setPixmap(
                pixmap.scaled(
                    38,
                    38,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        icon.setFixedSize(40, 40)

        brand = QLabel("DSCode Assistant")
        brand.setObjectName("brandName")
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(icon)
        brand_row.addWidget(brand)
        brand_row.addStretch(1)

        new_chat_button = QPushButton("＋  新建对话")
        new_chat_button.setObjectName("primaryButton")
        new_chat_button.clicked.connect(self.new_chat)

        history_label = QLabel("历史会话")
        history_label.setObjectName("sectionLabel")

        delete_button = QPushButton("删除")
        delete_button.setObjectName("subtleButton")
        delete_button.clicked.connect(self.delete_chat)

        settings_button = QPushButton("设置")
        settings_button.clicked.connect(self.open_settings)
        about_button = QPushButton("关于")
        about_button.setObjectName("subtleButton")
        about_button.clicked.connect(self.open_about)

        footer = QHBoxLayout()
        footer.addWidget(settings_button)
        footer.addWidget(about_button)
        footer.addWidget(delete_button)
        footer.addStretch(1)
        footer.addWidget(self._api_badge)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 18, 16, 14)
        sidebar_layout.setSpacing(10)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(6)
        sidebar_layout.addWidget(new_chat_button)
        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(self._search_input)
        sidebar_layout.addWidget(history_label)
        sidebar_layout.addWidget(self._history_list, 1)
        sidebar_layout.addWidget(self._empty_history)
        sidebar_layout.addLayout(footer)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.addWidget(sidebar)
        splitter.addWidget(self._content_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])
        self.setCentralWidget(splitter)

    def _update_api_status(self) -> None:
        settings = self._settings_manager.load()
        if is_provider_configured(self._settings_manager):
            if get_provider_id(settings) == OPENAI_COMPATIBLE_PROVIDER_ID:
                self._api_badge.set_status("兼容 API 已配置", "connected")
            else:
                self._api_badge.set_status("API 已配置", "connected")
        else:
            self._api_badge.set_status("模型未配置", "offline")

    def _show_welcome(self) -> None:
        self._history_list.clearSelection()
        self._content_stack.setCurrentWidget(self._welcome_widget)

    def new_chat(self) -> None:
        """Create and select a new local chat session."""
        if self._chat_widget.is_generating:
            self.statusBar().showMessage("请先停止当前回复，再新建会话。", 3000)
            return
        settings = self._settings_manager.load()
        session = self._database.create_session(
            title="新对话",
            model=get_active_model(settings),
            prompt_id=self._chat_widget.current_prompt_id(),
        )
        self.refresh_history(session.id)

    def open_recent_chat(self) -> None:
        if self._history_list.count() > 0:
            self._history_list.setCurrentRow(0)
        else:
            self.new_chat()

    def refresh_history(self, selected_session_id: int | None = None) -> None:
        """Refresh the local session list while preserving the selection."""
        if selected_session_id is None:
            current_item = self._history_list.currentItem()
            if current_item is not None:
                selected_session_id = current_item.data(Qt.ItemDataRole.UserRole)

        self._history_list.blockSignals(True)
        self._history_list.clear()
        selected_row = -1

        for row_index, session in enumerate(self._database.list_sessions()):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, session.title.casefold())
            item.setToolTip(session.title)
            item.setSizeHint(QSize(0, 58))
            self._history_list.addItem(item)
            self._history_list.setItemWidget(
                item,
                ConversationItem(
                    session.title,
                    session.updated_at.astimezone().strftime("%m-%d  %H:%M"),
                ),
            )
            if session.id == selected_session_id:
                selected_row = row_index

        self._history_list.blockSignals(False)
        self._empty_history.setVisible(self._history_list.count() == 0)
        self._filter_history(self._search_input.text())

        if selected_row >= 0:
            self._history_list.setCurrentRow(selected_row)
            self._load_selected_session(self._history_list.currentItem(), None)

    def _filter_history(self, query: str) -> None:
        normalized = query.strip().casefold()
        visible_count = 0
        for row in range(self._history_list.count()):
            item = self._history_list.item(row)
            title = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
            hidden = bool(normalized and normalized not in title)
            item.setHidden(hidden)
            visible_count += int(not hidden)
        if self._history_list.count() == 0:
            self._empty_history.setText("暂无历史会话")
        elif visible_count == 0:
            self._empty_history.setText("未找到匹配会话")
        self._empty_history.setVisible(visible_count == 0)

    def _load_selected_session(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return

        session_id = current.data(Qt.ItemDataRole.UserRole)
        if (
            self._chat_widget.is_generating
            and session_id != self._chat_widget.active_session_id
        ):
            self.statusBar().showMessage("生成过程中不能切换会话。", 3000)
            self._restore_active_history_selection()
            return
        session = next(
            (item for item in self._database.list_sessions() if item.id == session_id),
            None,
        )
        if session is not None:
            self._chat_widget.set_session(session)
            self._content_stack.setCurrentWidget(self._chat_widget)

    def _restore_active_history_selection(self) -> None:
        active_id = self._chat_widget.active_session_id
        if active_id is None:
            return
        self._history_list.blockSignals(True)
        for row in range(self._history_list.count()):
            item = self._history_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == active_id:
                self._history_list.setCurrentRow(row)
                break
        self._history_list.blockSignals(False)

    def _show_history_context_menu(self, position: QPoint) -> None:
        item = self._history_list.itemAt(position)
        if item is None:
            return
        self._history_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        selected_action = menu.exec(self._history_list.mapToGlobal(position))
        if selected_action is rename_action:
            self.rename_chat(item)
        elif selected_action is delete_action:
            self.delete_chat()

    def rename_chat(self, item: QListWidgetItem | None = None) -> None:
        """Rename an existing session using its current title field."""
        target = item or self._history_list.currentItem()
        if target is None:
            return
        widget = self._history_list.itemWidget(target)
        current_title = widget.title if isinstance(widget, ConversationItem) else ""
        title, accepted = QInputDialog.getText(
            self,
            "重命名会话",
            "会话标题",
            QLineEdit.EchoMode.Normal,
            current_title,
        )
        normalized_title = " ".join(title.split())[:80]
        if not accepted or not normalized_title or normalized_title == current_title:
            return
        session_id = target.data(Qt.ItemDataRole.UserRole)
        self._database.rename_session(session_id, normalized_title)
        if session_id == self._chat_widget.active_session_id:
            self._chat_widget.set_session(
                next(
                    session
                    for session in self._database.list_sessions()
                    if session.id == session_id
                )
            )
        self.refresh_history(session_id)

    def delete_chat(self) -> None:
        """Delete the selected local session after confirmation."""
        item = self._history_list.currentItem()
        if item is None:
            return
        if self._chat_widget.is_generating:
            self.statusBar().showMessage("请先停止当前回复，再删除会话。", 3000)
            return

        answer = QMessageBox.question(
            self,
            "删除会话",
            "确定删除当前会话及其全部消息吗？此操作无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._chat_widget.stop_generation()
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self._database.delete_session(session_id)
        self.refresh_history()
        self._show_welcome()

    def open_settings(self) -> None:
        """Open the local application settings dialog."""
        dialog = SettingsDialog(self._settings_manager, self._database, self)
        dialog.history_cleared.connect(self._history_was_cleared)
        if dialog.exec():
            self._update_api_status()
            self.statusBar().showMessage("设置已保存。", 3000)

    def _history_was_cleared(self) -> None:
        self.refresh_history()
        self._show_welcome()
        self.statusBar().showMessage("本地历史记录已清理。", 3000)

    def open_about(self) -> None:
        AboutDialog(self).exec()

    def handle_automation_request(self, request: AutomationRequest) -> None:
        """Handle a localhost automation command on the Qt GUI thread."""
        try:
            if request.action == "status":
                request.finish(HTTPStatus.OK, self._automation_status())
            elif request.action == "activate":
                self._activate_from_automation()
                request.finish(HTTPStatus.OK, self._automation_status())
            elif request.action == "open_project":
                self._automation_open_project(request)
            elif request.action == "create_task":
                self._automation_create_task(request)
            else:
                request.finish(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": "Unknown automation action."},
                )
        except Exception:
            request.finish(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": "Automation command failed."},
            )

    def _automation_status(self) -> dict[str, object]:
        return {
            "ok": True,
            "application": "DSCode Assistant",
            "state": "generating" if self._chat_widget.is_generating else "ready",
            "active_project": (
                str(self._automation_project_path)
                if self._automation_project_path is not None
                else None
            ),
            "active_session_id": self._chat_widget.active_session_id,
            "current_task": self._automation_task,
        }

    def _activate_from_automation(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _automation_open_project(self, request: AutomationRequest) -> None:
        raw_path = request.payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            request.finish(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "A non-empty project path is required."},
            )
            return
        project_path = Path(raw_path).expanduser()
        try:
            project_path = project_path.resolve(strict=True)
        except OSError:
            request.finish(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "Project directory does not exist."},
            )
            return
        if not project_path.is_dir():
            request.finish(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Project path must be a directory."},
            )
            return

        self._automation_project_path = project_path
        self.setWindowTitle(f"DSCode Assistant — {project_path.name}")
        self.statusBar().showMessage(f"当前自动化项目：{project_path}", 5000)
        self._activate_from_automation()
        request.finish(HTTPStatus.OK, self._automation_status())

    def _automation_create_task(self, request: AutomationRequest) -> None:
        if self._chat_widget.is_generating:
            request.finish(
                HTTPStatus.CONFLICT,
                {"ok": False, "error": "A response is currently being generated."},
            )
            return
        instruction = request.payload.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            request.finish(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "A non-empty task instruction is required."},
            )
            return
        title_value = request.payload.get("title", "自动化编程任务")
        if not isinstance(title_value, str):
            request.finish(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Task title must be a string."},
            )
            return
        title = " ".join(title_value.split())[:80] or "自动化编程任务"

        project_value = request.payload.get("project_path")
        if project_value is not None:
            project_request = AutomationRequest("open_project", {"path": project_value})
            self._automation_open_project(project_request)
            if project_request.status_code != HTTPStatus.OK:
                request.finish(project_request.status_code, project_request.response)
                return

        settings = self._settings_manager.load()
        session = self._database.create_session(
            title=title,
            model=get_active_model(settings),
            prompt_id=self._chat_widget.current_prompt_id(),
        )
        self.refresh_history(session.id)

        task_text = instruction.strip()
        if self._automation_project_path is not None:
            task_text = f"项目路径：{self._automation_project_path}\n\n任务：{task_text}"
        self._chat_widget.set_draft_text(task_text)
        self._automation_task = {
            "title": title,
            "status": "drafted",
            "session_id": session.id,
        }
        self._activate_from_automation()
        request.finish(HTTPStatus.CREATED, self._automation_status())

    @property
    def chat_widget(self) -> ChatWidget:
        return self._chat_widget

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop active work and close the local database."""
        if not self._chat_widget.shutdown():
            QMessageBox.information(
                self,
                "正在停止请求",
                "后台请求仍在结束，请稍后再次关闭窗口。",
            )
            event.ignore()
            return
        self._database.close()
        super().closeEvent(event)

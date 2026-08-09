"""Local settings dialog for DSCode Assistant."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .api_client import API_BASE_URL, DeepSeekClient
from .automation import AUTOMATION_HOST, AUTOMATION_PORT
from .database import DATABASE_FILENAME, Database
from .model_providers import (
    DeepSeekProvider,
    ModelProvider,
    OpenAICompatibleProvider,
)
from .settings import (
    DEFAULT_SETTINGS,
    DEEPSEEK_PROVIDER_ID,
    OPENAI_COMPATIBLE_PROVIDER_ID,
    SettingsManager,
    get_active_model,
    get_provider_id,
)
from .ui_components import StatusBadge


class _APIKeyOverrideSettings:
    """Expose an unsaved key to DeepSeekClient during a connection test."""

    def __init__(self, settings_manager: SettingsManager, api_key: str) -> None:
        self._settings_manager = settings_manager
        self._api_key = api_key

    def load(self) -> dict[str, str | int | float]:
        return self._settings_manager.load()

    def get_api_key(self) -> str:
        return self._api_key


class _ConnectionTestWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, provider: ModelProvider) -> None:
        super().__init__()
        self._provider = provider

    def run(self) -> None:
        try:
            self._provider.test_connection()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit()


class SettingsDialog(QDialog):
    """Edit local model-provider settings and keyring-backed credentials."""

    history_cleared = Signal()

    def __init__(
        self,
        settings_manager: SettingsManager,
        database: Database | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_manager = settings_manager
        self._database = database
        self._test_worker: _ConnectionTestWorker | None = None
        self._testing_provider_id = DEEPSEEK_PROVIDER_ID
        settings = settings_manager.load()

        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(660, 720)
        self.setMinimumSize(580, 620)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem("DeepSeek 官方 API", DEEPSEEK_PROVIDER_ID)
        self._provider_combo.addItem(
            "OpenAI Compatible",
            OPENAI_COMPATIBLE_PROVIDER_ID,
        )
        provider_index = self._provider_combo.findData(get_provider_id(settings))
        self._provider_combo.setCurrentIndex(max(0, provider_index))

        self._current_model = QLabel()
        self._current_model.setObjectName("modelLabel")

        self._provider_stack = QStackedWidget()
        self._provider_stack.addWidget(self._build_deepseek_page(settings))
        self._provider_stack.addWidget(self._build_openai_page(settings))

        provider_form = QFormLayout()
        provider_form.addRow("模型提供商", self._provider_combo)
        provider_form.addRow("当前模型", self._current_model)
        provider_group = QGroupBox("提供商设置")
        provider_layout = QVBoxLayout(provider_group)
        provider_layout.addLayout(provider_form)
        provider_layout.addWidget(self._provider_stack)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setDecimals(1)
        self._temperature.setValue(float(settings["temperature"]))

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(1, 384000)
        self._max_tokens.setValue(int(settings["max_tokens"]))

        model_form = QFormLayout()
        model_form.addRow("Temperature", self._temperature)
        model_form.addRow("Max Tokens", self._max_tokens)
        model_group = QGroupBox("生成参数")
        model_group.setLayout(model_form)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 14)
        content_layout.setSpacing(12)
        content_layout.addWidget(provider_group)
        content_layout.addWidget(model_group)
        content_layout.addWidget(self._build_appearance_group())
        content_layout.addWidget(self._build_data_group())
        content_layout.addWidget(self._build_advanced_group())
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 12)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)

        self._provider_combo.currentIndexChanged.connect(self._provider_changed)
        self._model_combo.currentTextChanged.connect(self._update_current_model)
        self._openai_model_input.textChanged.connect(self._update_current_model)
        self._provider_changed()

    def _build_deepseek_page(self, settings: dict[str, Any]) -> QWidget:
        page = QWidget()
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self._settings_manager.has_api_key():
            self._api_key_input.setPlaceholderText("API Key 已安全保存；留空表示不修改")
            self._key_status = StatusBadge("已安全保存", "connected")
        else:
            self._api_key_input.setPlaceholderText("输入 DeepSeek API Key")
            self._key_status = StatusBadge("尚未配置", "offline")

        api_address = QLineEdit(API_BASE_URL)
        api_address.setReadOnly(True)
        api_address.setToolTip("DSCode Assistant 直接连接 DeepSeek 官方 API")

        self._model_combo = QComboBox()
        supported_models = ["deepseek-v4-flash", "deepseek-v4-pro"]
        current_model = str(settings["model"])
        if current_model not in supported_models:
            supported_models.insert(0, current_model)
        self._model_combo.addItems(supported_models)
        self._model_combo.setCurrentText(current_model)

        self._connection_status = StatusBadge("尚未测试", "ready")
        self._test_button = QPushButton("测试连接")
        self._test_button.clicked.connect(self._test_connection)
        delete_button = QPushButton("删除 API Key")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._delete_api_key)

        form = QFormLayout()
        form.addRow("API 地址", api_address)
        form.addRow("API Key", self._api_key_input)
        form.addRow("Model Name", self._model_combo)
        form.addRow("密钥状态", self._key_status)
        form.addRow("连接状态", self._connection_status)
        actions = QHBoxLayout()
        actions.addWidget(self._test_button)
        actions.addWidget(delete_button)
        actions.addStretch(1)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addLayout(form)
        layout.addLayout(actions)
        return page

    def _build_openai_page(self, settings: dict[str, Any]) -> QWidget:
        page = QWidget()
        self._openai_base_url = QLineEdit(
            str(
                settings.get(
                    "openai_compatible_base_url",
                    DEFAULT_SETTINGS["openai_compatible_base_url"],
                )
            )
        )
        self._openai_base_url.setPlaceholderText("例如 https://example.com/v1")
        self._openai_api_key_input = QLineEdit()
        self._openai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self._has_provider_key(OPENAI_COMPATIBLE_PROVIDER_ID):
            self._openai_api_key_input.setPlaceholderText(
                "API Key 已安全保存；留空表示不修改"
            )
            self._openai_key_status = StatusBadge("已安全保存", "connected")
        else:
            self._openai_api_key_input.setPlaceholderText("本地接口可留空")
            self._openai_key_status = StatusBadge("未保存（可选）", "ready")

        self._openai_model_input = QLineEdit(
            str(
                settings.get(
                    "openai_compatible_model",
                    DEFAULT_SETTINGS["openai_compatible_model"],
                )
            )
        )
        self._openai_model_input.setPlaceholderText("例如 gpt-4o-mini 或本地模型名")
        self._openai_connection_status = StatusBadge("尚未测试", "ready")
        self._openai_test_button = QPushButton("测试连接")
        self._openai_test_button.clicked.connect(self._test_openai_connection)
        delete_button = QPushButton("删除 API Key")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._delete_openai_api_key)

        form = QFormLayout()
        form.addRow("Base URL", self._openai_base_url)
        form.addRow("API Key", self._openai_api_key_input)
        form.addRow("Model Name", self._openai_model_input)
        form.addRow("密钥状态", self._openai_key_status)
        form.addRow("连接状态", self._openai_connection_status)
        note = QLabel("Base URL 应包含兼容接口版本路径；本机服务可不配置 API Key。")
        note.setWordWrap(True)
        actions = QHBoxLayout()
        actions.addWidget(self._openai_test_button)
        actions.addWidget(delete_button)
        actions.addStretch(1)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addLayout(actions)
        return page

    def _build_appearance_group(self) -> QGroupBox:
        theme_value = QLineEdit("浅色主题")
        theme_value.setReadOnly(True)
        font_size = QSpinBox()
        font_size.setRange(11, 20)
        font_size.setValue(14)
        font_size.setEnabled(False)
        code_font_size = QSpinBox()
        code_font_size.setRange(11, 20)
        code_font_size.setValue(13)
        code_font_size.setEnabled(False)
        form = QFormLayout()
        form.addRow("主题", theme_value)
        form.addRow("界面字体大小", font_size)
        form.addRow("代码块字体大小", code_font_size)
        group = QGroupBox("外观设置")
        group.setLayout(form)
        return group

    def _build_data_group(self) -> QGroupBox:
        database_path = QLineEdit(
            str(self._settings_manager.get_data_dir() / DATABASE_FILENAME)
        )
        database_path.setReadOnly(True)
        security_note = QLabel(
            "所有 API Key 均由操作系统凭据库保存，不会写入设置文件或聊天数据库。"
        )
        security_note.setWordWrap(True)
        clear_button = QPushButton("清理历史记录")
        clear_button.setObjectName("dangerButton")
        clear_button.setEnabled(self._database is not None)
        clear_button.clicked.connect(self._clear_history)
        form = QFormLayout()
        form.addRow("本地数据库", database_path)
        form.addRow("安全说明", security_note)
        form.addRow("", clear_button)
        group = QGroupBox("数据与安全")
        group.setLayout(form)
        return group

    @staticmethod
    def _build_advanced_group() -> QGroupBox:
        automation_address = QLineEdit(
            f"http://{AUTOMATION_HOST}:{AUTOMATION_PORT}"
        )
        automation_address.setReadOnly(True)
        automation_note = QLabel("仅监听 localhost，随应用启动，不接受局域网连接。")
        automation_note.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Automation", automation_address)
        form.addRow("安全范围", automation_note)
        group = QGroupBox("高级选项")
        group.setLayout(form)
        return group

    def _provider_changed(self) -> None:
        provider_id = str(self._provider_combo.currentData())
        index = 1 if provider_id == OPENAI_COMPATIBLE_PROVIDER_ID else 0
        self._provider_stack.setCurrentIndex(index)
        self._update_current_model()

    def _update_current_model(self) -> None:
        if self._provider_combo.currentData() == OPENAI_COMPATIBLE_PROVIDER_ID:
            model = self._openai_model_input.text().strip() or "未设置"
        else:
            model = self._model_combo.currentText().strip() or "未设置"
        self._current_model.setText(model)

    def _save(self) -> None:
        provider_id = str(self._provider_combo.currentData())
        deepseek_key = self._api_key_input.text().strip()
        compatible_key = self._openai_api_key_input.text().strip()
        base_url = self._openai_base_url.text().strip()
        compatible_model = self._openai_model_input.text().strip()
        try:
            if provider_id == OPENAI_COMPATIBLE_PROVIDER_ID:
                if not compatible_model:
                    raise ValueError("请填写 OpenAI Compatible Model Name。")
                OpenAICompatibleProvider(base_url)
            if deepseek_key:
                self._settings_manager.set_api_key(deepseek_key)
            if compatible_key:
                self._set_provider_key(
                    OPENAI_COMPATIBLE_PROVIDER_ID,
                    compatible_key,
                )
            self._settings_manager.save(
                {
                    "provider": provider_id,
                    "model": self._model_combo.currentText(),
                    "openai_compatible_base_url": base_url,
                    "openai_compatible_model": compatible_model,
                    "temperature": self._temperature.value(),
                    "max_tokens": self._max_tokens.value(),
                }
            )
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return

        self._api_key_input.clear()
        self._openai_api_key_input.clear()
        self.accept()

    def _test_connection(self) -> None:
        api_key = self._api_key_input.text().strip()
        if not api_key and not self._settings_manager.has_api_key():
            QMessageBox.information(
                self,
                "需要 API Key",
                "请输入或先保存 DeepSeek API Key，再测试连接。",
            )
            return
        settings_source: Any = self._settings_manager
        if api_key:
            settings_source = _APIKeyOverrideSettings(self._settings_manager, api_key)
        provider = DeepSeekProvider(DeepSeekClient(settings_source))
        self._start_connection_test(provider, DEEPSEEK_PROVIDER_ID)

    def _test_openai_connection(self) -> None:
        api_key = self._openai_api_key_input.text().strip()
        if not api_key:
            api_key = self._get_provider_key(OPENAI_COMPATIBLE_PROVIDER_ID) or ""
        try:
            provider = OpenAICompatibleProvider(
                self._openai_base_url.text().strip(),
                api_key=api_key or None,
            )
        except ValueError as error:
            QMessageBox.warning(self, "配置无效", str(error))
            return
        self._start_connection_test(provider, OPENAI_COMPATIBLE_PROVIDER_ID)

    def _start_connection_test(
        self,
        provider: ModelProvider,
        provider_id: str,
    ) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            return
        self._testing_provider_id = provider_id
        status = self._status_for_provider(provider_id)
        status.set_status("正在连接…", "generating")
        self._set_test_buttons_enabled(False)
        worker = _ConnectionTestWorker(provider)
        worker.succeeded.connect(self._connection_succeeded)
        worker.failed.connect(self._connection_failed)
        worker.finished.connect(self._connection_test_finished)
        worker.finished.connect(worker.deleteLater)
        self._test_worker = worker
        worker.start()

    def _connection_succeeded(self) -> None:
        status = self._status_for_provider(self._testing_provider_id)
        status.set_status("连接成功", "connected")
        status.setToolTip("模型提供商连接测试成功")

    def _connection_failed(self, message: str) -> None:
        status = self._status_for_provider(self._testing_provider_id)
        status.set_status("连接失败", "failed")
        status.setToolTip(message)
        QMessageBox.warning(self, "连接失败", message)

    def _connection_test_finished(self) -> None:
        self._test_worker = None
        self._set_test_buttons_enabled(True)

    def _status_for_provider(self, provider_id: str) -> StatusBadge:
        if provider_id == OPENAI_COMPATIBLE_PROVIDER_ID:
            return self._openai_connection_status
        return self._connection_status

    def _set_test_buttons_enabled(self, enabled: bool) -> None:
        self._test_button.setEnabled(enabled)
        self._openai_test_button.setEnabled(enabled)
        self._test_button.setText("测试连接" if enabled else "测试中…")
        self._openai_test_button.setText("测试连接" if enabled else "测试中…")

    def _delete_api_key(self) -> None:
        if not self._confirm_key_deletion():
            return
        try:
            self._settings_manager.delete_api_key()
        except Exception as error:
            QMessageBox.warning(self, "删除失败", str(error))
            return
        self._api_key_input.clear()
        self._key_status.set_status("尚未配置", "offline")

    def _delete_openai_api_key(self) -> None:
        if not self._confirm_key_deletion():
            return
        try:
            self._delete_provider_key(OPENAI_COMPATIBLE_PROVIDER_ID)
        except Exception as error:
            QMessageBox.warning(self, "删除失败", str(error))
            return
        self._openai_api_key_input.clear()
        self._openai_key_status.set_status("未保存（可选）", "ready")

    def _confirm_key_deletion(self) -> bool:
        answer = QMessageBox.question(
            self,
            "删除 API Key",
            "确定从系统凭据库删除当前提供商的 API Key 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _has_provider_key(self, provider_id: str) -> bool:
        method = getattr(self._settings_manager, "has_provider_api_key", None)
        return bool(method(provider_id)) if callable(method) else False

    def _get_provider_key(self, provider_id: str) -> str | None:
        method = getattr(self._settings_manager, "get_provider_api_key", None)
        return method(provider_id) if callable(method) else None

    def _set_provider_key(self, provider_id: str, api_key: str) -> None:
        method = getattr(self._settings_manager, "set_provider_api_key", None)
        if not callable(method):
            raise RuntimeError("当前设置管理器不支持提供商凭据。")
        method(provider_id, api_key)

    def _delete_provider_key(self, provider_id: str) -> None:
        method = getattr(self._settings_manager, "delete_provider_api_key", None)
        if not callable(method):
            raise RuntimeError("当前设置管理器不支持提供商凭据。")
        method(provider_id)

    def _clear_history(self) -> None:
        if self._database is None:
            return
        answer = QMessageBox.question(
            self,
            "清理历史记录",
            "确定删除全部本地会话和消息吗？此操作无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._database.clear_history()
        self.history_cleared.emit()
        QMessageBox.information(self, "清理完成", "本地历史记录已清理。")

    def reject(self) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            self._status_for_provider(self._testing_provider_id).set_status(
                "请等待测试完成",
                "generating",
            )
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            self._status_for_provider(self._testing_provider_id).set_status(
                "请等待测试完成",
                "generating",
            )
            event.ignore()
            return
        super().closeEvent(event)

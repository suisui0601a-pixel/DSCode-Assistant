"""Local settings dialog for DSCode Assistant."""

from __future__ import annotations

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .api_client import API_BASE_URL, DeepSeekClient
from .database import DATABASE_FILENAME, Database
from .settings import SettingsManager
from .ui_components import StatusBadge


class _ConnectionTestWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self._settings_manager = settings_manager

    def run(self) -> None:
        try:
            DeepSeekClient(self._settings_manager).test_connection()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit()


class SettingsDialog(QDialog):
    """Edit ordinary settings and the keyring-backed DeepSeek API key."""

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
        settings = settings_manager.load()

        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(620, 660)
        self.setMinimumWidth(560)

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if settings_manager.has_api_key():
            self._api_key_input.setPlaceholderText("API Key 已安全保存；留空表示不修改")
        else:
            self._api_key_input.setPlaceholderText("输入 DeepSeek API Key")

        api_address = QLineEdit(API_BASE_URL)
        api_address.setReadOnly(True)
        api_address.setToolTip("DSCode Assistant 仅连接 DeepSeek 官方 API")

        if settings_manager.has_api_key():
            self._key_status = StatusBadge("已安全保存", "connected")
        else:
            self._key_status = StatusBadge("尚未配置", "offline")
        self._connection_status = StatusBadge("尚未测试", "ready")

        self._test_button = QPushButton("测试连接")
        self._test_button.clicked.connect(self._test_connection)
        delete_key_button = QPushButton("删除 API Key")
        delete_key_button.setObjectName("dangerButton")
        delete_key_button.clicked.connect(self._delete_api_key)

        api_form = QFormLayout()
        api_form.addRow("API Key", self._api_key_input)
        api_form.addRow("API 地址", api_address)
        api_form.addRow("密钥状态", self._key_status)
        api_form.addRow("连接状态", self._connection_status)
        api_actions = QHBoxLayout()
        api_actions.addWidget(self._test_button)
        api_actions.addWidget(delete_key_button)
        api_actions.addStretch(1)
        api_group = QGroupBox("API 设置")
        api_layout = QVBoxLayout(api_group)
        api_layout.addLayout(api_form)
        api_layout.addLayout(api_actions)

        self._model_combo = QComboBox()
        supported_models = ["deepseek-v4-flash", "deepseek-v4-pro"]
        current_model = str(settings["model"])
        if current_model not in supported_models:
            supported_models.insert(0, current_model)
        self._model_combo.addItems(supported_models)
        self._model_combo.setCurrentText(current_model)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setDecimals(1)
        self._temperature.setValue(float(settings["temperature"]))

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(1, 384000)
        self._max_tokens.setValue(int(settings["max_tokens"]))

        model_form = QFormLayout()
        model_form.addRow("模型名称", self._model_combo)
        model_form.addRow("Temperature", self._temperature)
        model_form.addRow("Max Tokens", self._max_tokens)
        model_group = QGroupBox("模型设置")
        model_group.setLayout(model_form)

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
        appearance_form = QFormLayout()
        appearance_form.addRow("主题", theme_value)
        appearance_form.addRow("界面字体大小", font_size)
        appearance_form.addRow("代码块字体大小", code_font_size)
        appearance_group = QGroupBox("外观设置")
        appearance_group.setLayout(appearance_form)

        database_path = QLineEdit(
            str(settings_manager.get_data_dir() / DATABASE_FILENAME)
        )
        database_path.setReadOnly(True)
        security_note = QLabel(
            "API Key 由操作系统凭据库保存，不会写入设置文件或聊天数据库。"
        )
        security_note.setWordWrap(True)
        clear_history_button = QPushButton("清理历史记录")
        clear_history_button.setObjectName("dangerButton")
        clear_history_button.setEnabled(database is not None)
        clear_history_button.clicked.connect(self._clear_history)
        data_form = QFormLayout()
        data_form.addRow("本地数据库", database_path)
        data_form.addRow("安全说明", security_note)
        data_form.addRow("", clear_history_button)
        data_group = QGroupBox("数据与安全")
        data_group.setLayout(data_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(api_group)
        layout.addWidget(model_group)
        layout.addWidget(appearance_group)
        layout.addWidget(data_group)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def _save(self) -> None:
        api_key = self._api_key_input.text().strip()
        try:
            if api_key:
                self._settings_manager.set_api_key(api_key)
            self._settings_manager.save(
                {
                    "model": self._model_combo.currentText(),
                    "temperature": self._temperature.value(),
                    "max_tokens": self._max_tokens.value(),
                }
            )
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return

        self._api_key_input.clear()
        self.accept()

    def _delete_api_key(self) -> None:
        answer = QMessageBox.question(
            self,
            "删除 API Key",
            "确定从系统凭据库删除 API Key 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self._settings_manager.delete_api_key()
        except Exception as error:
            QMessageBox.warning(self, "删除失败", str(error))
            return

        self._api_key_input.clear()
        self._key_status.set_status("尚未配置", "offline")

    def _test_connection(self) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            return
        if not self._settings_manager.has_api_key():
            QMessageBox.information(
                self,
                "需要 API Key",
                "请先保存 API Key，再测试连接。",
            )
            return

        self._test_button.setEnabled(False)
        self._test_button.setText("测试中…")
        self._connection_status.set_status("正在连接…", "generating")
        worker = _ConnectionTestWorker(self._settings_manager)
        worker.succeeded.connect(self._connection_succeeded)
        worker.failed.connect(self._connection_failed)
        worker.finished.connect(self._connection_test_finished)
        worker.finished.connect(worker.deleteLater)
        self._test_worker = worker
        worker.start()

    def _connection_succeeded(self) -> None:
        self._connection_status.set_status("连接成功", "connected")
        self._connection_status.setToolTip("已连接 DeepSeek 官方 API")

    def _connection_failed(self, message: str) -> None:
        self._connection_status.set_status("连接失败", "failed")
        self._connection_status.setToolTip(message)
        QMessageBox.warning(self, "连接失败", message)

    def _connection_test_finished(self) -> None:
        self._test_worker = None
        self._test_button.setEnabled(True)
        self._test_button.setText("测试连接")

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
            self._connection_status.set_status("请等待测试完成", "generating")
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            self._connection_status.set_status("请等待测试完成", "generating")
            event.ignore()
            return
        super().closeEvent(event)

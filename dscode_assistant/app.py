"""Application bootstrap for DSCode Assistant."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import TracebackType

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .automation import AUTOMATION_PORT, AutomationBridge, AutomationServer
from .database import Database
from .diagnostics import (
    configure_exception_logging,
    record_exception,
    shutdown_exception_logging,
)
from .main_window import MainWindow
from .settings import SettingsManager


def _resource_path(*parts: str) -> Path:
    """Resolve bundled resources in source and PyInstaller environments."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    base_path = Path(frozen_root) if frozen_root else Path(__file__).resolve().parent.parent
    return base_path.joinpath(*parts)


def _show_unhandled_exception(
    exception_type: type[BaseException],
    _exception: BaseException,
    traceback_value: TracebackType | None,
) -> None:
    """Record a privacy-safe diagnostic and show a generic GUI error."""
    record_exception(exception_type, traceback_value)
    try:
        QMessageBox.critical(
            None,
            "DSCode Assistant 错误",
            "应用遇到未处理的错误。诊断信息已保存在本地数据目录。",
        )
    except Exception:
        pass


def main() -> int:
    """Initialize and run the DSCode Assistant desktop application."""
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("DSCode Assistant")
    application.setOrganizationName("DSCode Assistant")
    application.setApplicationVersion(__version__)
    application.setWindowIcon(QIcon(str(_resource_path("assets", "icon.ico"))))
    stylesheet_path = _resource_path("assets", "light.qss")
    if stylesheet_path.exists():
        application.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))

    settings_manager = SettingsManager()
    try:
        configure_exception_logging(settings_manager.get_data_dir())
    except OSError:
        pass
    sys.excepthook = _show_unhandled_exception

    database = Database(settings_manager)
    try:
        database.initialize()
        window = MainWindow(database, settings_manager)
    except (OSError, sqlite3.Error) as error:
        record_exception(type(error), error.__traceback__)
        database.close()
        QMessageBox.critical(
            None,
            "本地数据库错误",
            "无法初始化本地聊天历史，请检查数据目录权限。",
        )
        return 1

    automation_bridge = AutomationBridge()
    automation_bridge.command_received.connect(window.handle_automation_request)
    automation_server = AutomationServer(automation_bridge.dispatch)
    try:
        automation_server.start()
    except OSError:
        window.statusBar().showMessage(
            f"本地自动化接口未启动：端口 {AUTOMATION_PORT} 不可用。",
            5000,
        )

    cleaned_up = False

    def release_resources() -> None:
        nonlocal cleaned_up
        if cleaned_up:
            return
        automation_server.stop()
        window.chat_widget.shutdown()
        database.close()
        shutdown_exception_logging()
        cleaned_up = True

    application.aboutToQuit.connect(release_resources)
    window.show()
    exit_code = application.exec()
    release_resources()
    return exit_code

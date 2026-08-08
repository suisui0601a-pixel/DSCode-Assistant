"""About dialog for DSCode Assistant."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from . import __version__


def _icon_path() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    root = Path(frozen_root) if frozen_root else Path(__file__).resolve().parent.parent
    return root / "assets" / "app.png"


class AboutDialog(QDialog):
    """Display local version, purpose, and privacy information."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于 DSCode Assistant")
        self.setFixedWidth(440)

        icon = QLabel()
        pixmap = QPixmap(str(_icon_path()))
        if not pixmap.isNull():
            icon.setPixmap(
                pixmap.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("DSCode Assistant")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version = QLabel(f"版本 {__version__}")
        version.setObjectName("modelLabel")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "一个开源、免费、本地优先的 DeepSeek API 编程助手。\n\n"
            "不提供开发者服务器，不收集遥测数据；聊天内容仅在用户主动发送时"
            "直达 DeepSeek 官方 API。API Key 由操作系统凭据库保存。"
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 22)
        layout.setSpacing(10)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addSpacing(8)
        layout.addWidget(description)
        layout.addSpacing(12)
        layout.addWidget(buttons)

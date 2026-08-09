"""Provider settings compatibility and UI integration tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QGroupBox, QLineEdit

import dscode_assistant.chat_widget as chat_widget_module
from dscode_assistant.database import Database
from dscode_assistant.main_window import MainWindow
from dscode_assistant.model_providers import (
    DeepSeekProvider,
    OpenAICompatibleProvider,
)
from dscode_assistant.settings import (
    DEEPSEEK_PROVIDER_ID,
    KEYRING_SERVICE_NAME,
    OPENAI_COMPATIBLE_KEYRING_ACCOUNT_NAME,
    OPENAI_COMPATIBLE_PROVIDER_ID,
    SettingsManager,
    get_active_model,
    get_provider_id,
)
from dscode_assistant.settings_dialog import SettingsDialog


class ProviderFakeSettings:
    def __init__(self, data_dir: Path, values: dict[str, object] | None = None) -> None:
        self._data_dir = data_dir
        self.values: dict[str, object] = {
            "provider": DEEPSEEK_PROVIDER_ID,
            "model": "deepseek-v4-flash",
            "openai_compatible_base_url": "http://127.0.0.1:11434/v1",
            "openai_compatible_model": "local-coder",
            "temperature": 0.7,
            "max_tokens": 256,
            "request_timeout": 10.0,
            "theme": "system",
        }
        if values:
            self.values.update(values)
        self.keys = {
            DEEPSEEK_PROVIDER_ID: "deepseek-test-key",
        }

    def get_data_dir(self) -> Path:
        return self._data_dir

    def load(self) -> dict[str, object]:
        return self.values.copy()

    def save(self, values: dict[str, object]) -> None:
        self.values.update(values)

    def get_api_key(self) -> str | None:
        return self.keys.get(DEEPSEEK_PROVIDER_ID)

    def has_api_key(self) -> bool:
        return bool(self.get_api_key())

    def set_api_key(self, value: str) -> None:
        self.keys[DEEPSEEK_PROVIDER_ID] = value

    def delete_api_key(self) -> None:
        self.keys.pop(DEEPSEEK_PROVIDER_ID, None)

    def get_provider_api_key(self, provider_id: str) -> str | None:
        return self.keys.get(provider_id)

    def has_provider_api_key(self, provider_id: str) -> bool:
        return bool(self.get_provider_api_key(provider_id))

    def set_provider_api_key(self, provider_id: str, value: str) -> None:
        self.keys[provider_id] = value

    def delete_provider_api_key(self, provider_id: str) -> None:
        self.keys.pop(provider_id, None)


class CaptureWorker(QObject):
    chunk_received = Signal(str)
    completed = Signal()
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()
    last_instance: "CaptureWorker | None" = None

    def __init__(self, client: object, _messages: object, options: object) -> None:
        super().__init__()
        self.client = client
        self.options = options
        self.running = False
        CaptureWorker.last_instance = self

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

    def deleteLater(self) -> None:
        return


class ProviderSettingsTests(unittest.TestCase):
    def test_legacy_settings_default_to_deepseek_and_keep_original_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            (data_dir / "settings.json").write_text(
                json.dumps({"model": "legacy-deepseek-model"}),
                encoding="utf-8",
            )
            settings = SettingsManager(data_dir)
            loaded = settings.load()

        self.assertEqual(get_provider_id(loaded), DEEPSEEK_PROVIDER_ID)
        self.assertEqual(get_active_model(loaded), "legacy-deepseek-model")

    def test_compatible_key_uses_keyring_and_never_enters_settings_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            settings = SettingsManager(data_dir)
            with patch("dscode_assistant.settings.keyring.set_password") as set_password:
                settings.set_provider_api_key(
                    OPENAI_COMPATIBLE_PROVIDER_ID,
                    "compatible-secret",
                )
            settings.save(
                {
                    "provider": OPENAI_COMPATIBLE_PROVIDER_ID,
                    "openai_compatible_base_url": "https://models.example/v1",
                    "openai_compatible_model": "coder-model",
                    "api_key": "must-not-be-saved",
                }
            )
            saved_text = (data_dir / "settings.json").read_text(encoding="utf-8")

        set_password.assert_called_once_with(
            KEYRING_SERVICE_NAME,
            OPENAI_COMPATIBLE_KEYRING_ACCOUNT_NAME,
            "compatible-secret",
        )
        self.assertNotIn("compatible-secret", saved_text)
        self.assertNotIn("must-not-be-saved", saved_text)


class ProviderSettingsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_settings_page_switches_and_saves_compatible_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = ProviderFakeSettings(Path(temporary_directory))
            dialog = SettingsDialog(settings)
            try:
                index = dialog._provider_combo.findData(
                    OPENAI_COMPATIBLE_PROVIDER_ID
                )
                dialog._provider_combo.setCurrentIndex(index)
                dialog._openai_base_url.setText("https://models.example/v1")
                dialog._openai_api_key_input.setText("new-compatible-key")
                dialog._openai_model_input.setText("coder-model")
                self.application.processEvents()

                self.assertEqual(dialog._provider_stack.currentIndex(), 1)
                self.assertEqual(dialog._current_model.text(), "coder-model")
                self.assertEqual(
                    dialog._openai_api_key_input.echoMode(),
                    QLineEdit.EchoMode.Password,
                )
                self.assertIn(
                    "高级选项",
                    [group.title() for group in dialog.findChildren(QGroupBox)],
                )

                dialog._save()
                self.assertEqual(
                    settings.values["provider"],
                    OPENAI_COMPATIBLE_PROVIDER_ID,
                )
                self.assertEqual(
                    settings.values["openai_compatible_base_url"],
                    "https://models.example/v1",
                )
                self.assertEqual(settings.keys[OPENAI_COMPATIBLE_PROVIDER_ID], "new-compatible-key")
            finally:
                dialog.close()

    def test_chat_selects_provider_without_changing_worker_signals(self) -> None:
        original_worker = chat_widget_module.ChatWorker
        chat_widget_module.ChatWorker = CaptureWorker
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                for provider_id, expected_type in (
                    (DEEPSEEK_PROVIDER_ID, DeepSeekProvider),
                    (OPENAI_COMPATIBLE_PROVIDER_ID, OpenAICompatibleProvider),
                ):
                    settings = ProviderFakeSettings(root / provider_id, {
                        "provider": provider_id,
                    })
                    database = Database(settings)
                    window = MainWindow(database, settings)
                    try:
                        window.new_chat()
                        window.chat_widget.set_draft_text("provider routing test")
                        window.chat_widget.send_message()
                        worker = CaptureWorker.last_instance
                        self.assertIsNotNone(worker)
                        self.assertIsInstance(worker.client, expected_type)
                        self.assertEqual(
                            worker.options.model,
                            "local-coder"
                            if provider_id == OPENAI_COMPATIBLE_PROVIDER_ID
                            else "deepseek-v4-flash",
                        )
                    finally:
                        window.close()
                        self.application.processEvents()
        finally:
            chat_widget_module.ChatWorker = original_worker


if __name__ == "__main__":
    unittest.main()

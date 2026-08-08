"""Local application settings and API credential storage."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import keyring
from keyring.errors import PasswordDeleteError


APP_DIRECTORY_NAME: Final = "DSCodeAssistant"
KEYRING_SERVICE_NAME: Final = "DSCode Assistant"
KEYRING_ACCOUNT_NAME: Final = "deepseek-api-key"

DEFAULT_SETTINGS: Final[dict[str, str | int | float]] = {
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 4096,
    "request_timeout": 60.0,
    "theme": "system",
}


class SettingsManager:
    """Manage non-secret local settings and the API key credential."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or self._default_data_dir()
        self._settings_path = self._data_dir / "settings.json"

    @staticmethod
    def _default_data_dir() -> Path:
        if sys.platform == "win32":
            base_dir = Path(
                os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
            )
        elif sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

        return base_dir / APP_DIRECTORY_NAME

    def get_data_dir(self) -> Path:
        """Return the directory used for local DSCode Assistant data."""
        return self._data_dir

    def load(self) -> dict[str, str | int | float]:
        """Load ordinary settings, falling back to defaults when unavailable."""
        settings = DEFAULT_SETTINGS.copy()

        if not self._settings_path.exists():
            return settings

        try:
            stored_value = json.loads(self._settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return settings

        if not isinstance(stored_value, dict):
            return settings

        for name, default_value in DEFAULT_SETTINGS.items():
            value = stored_value.get(name)
            if self._matches_expected_type(value, default_value):
                settings[name] = value

        return settings

    def save(self, settings: Mapping[str, Any]) -> None:
        """Save approved non-secret settings to settings.json."""
        safe_settings = self.load()

        for name, default_value in DEFAULT_SETTINGS.items():
            value = settings.get(name)
            if self._matches_expected_type(value, default_value):
                safe_settings[name] = value

        self._data_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self._settings_path.with_suffix(".json.tmp")
        serialized = json.dumps(safe_settings, ensure_ascii=False, indent=2)
        temporary_path.write_text(f"{serialized}\n", encoding="utf-8")
        temporary_path.replace(self._settings_path)

    @staticmethod
    def _matches_expected_type(value: Any, default_value: str | int | float) -> bool:
        if isinstance(default_value, float):
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if isinstance(default_value, int):
            return isinstance(value, int) and not isinstance(value, bool)
        return isinstance(value, type(default_value))

    def get_api_key(self) -> str | None:
        """Read the DeepSeek API key from the operating system credential store."""
        try:
            return keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME)
        except Exception:
            return None

    def set_api_key(self, api_key: str) -> None:
        """Save the DeepSeek API key in the operating system credential store."""
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("API key cannot be empty.")
        try:
            keyring.set_password(
                KEYRING_SERVICE_NAME,
                KEYRING_ACCOUNT_NAME,
                normalized_key,
            )
        except Exception as error:
            raise RuntimeError("系统凭据库不可用，API Key 未保存。") from error

    def delete_api_key(self) -> None:
        """Delete the DeepSeek API key from the operating system credential store."""
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME)
        except PasswordDeleteError:
            return
        except Exception as error:
            raise RuntimeError("系统凭据库不可用，无法删除 API Key。") from error

    def has_api_key(self) -> bool:
        """Return whether a non-empty API key exists in the credential store."""
        api_key = self.get_api_key()
        return bool(api_key and api_key.strip())

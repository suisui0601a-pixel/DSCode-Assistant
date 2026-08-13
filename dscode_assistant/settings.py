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
DEEPSEEK_PROVIDER_ID: Final = "deepseek"
OPENAI_COMPATIBLE_PROVIDER_ID: Final = "openai-compatible"
OPENAI_COMPATIBLE_KEYRING_ACCOUNT_NAME: Final = "openai-compatible-api-key"
SUPPORTED_PROVIDER_IDS: Final = {
    DEEPSEEK_PROVIDER_ID,
    OPENAI_COMPATIBLE_PROVIDER_ID,
}
CONTEXT_OPTIMIZATION_RAW: Final = "raw"
CONTEXT_OPTIMIZATION_LIGHT: Final = "light"
CONTEXT_OPTIMIZATION_AUTO: Final = "auto"
SUPPORTED_CONTEXT_OPTIMIZATION_MODES: Final = {
    CONTEXT_OPTIMIZATION_RAW,
    CONTEXT_OPTIMIZATION_LIGHT,
    CONTEXT_OPTIMIZATION_AUTO,
}

DEFAULT_SETTINGS: Final[dict[str, str | int | float]] = {
    "provider": DEEPSEEK_PROVIDER_ID,
    "model": "deepseek-chat",
    "openai_compatible_base_url": "http://127.0.0.1:11434/v1",
    "openai_compatible_model": "",
    "temperature": 0.7,
    "max_tokens": 4096,
    "request_timeout": 60.0,
    "theme": "system",
    "context_optimization_mode": CONTEXT_OPTIMIZATION_RAW,
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
        return self.get_provider_api_key(DEEPSEEK_PROVIDER_ID)

    def get_provider_api_key(self, provider_id: str) -> str | None:
        """Read a provider API key from the operating system credential store."""
        try:
            return keyring.get_password(
                KEYRING_SERVICE_NAME,
                self._provider_keyring_account(provider_id),
            )
        except Exception:
            return None

    def set_api_key(self, api_key: str) -> None:
        """Save the DeepSeek API key in the operating system credential store."""
        self.set_provider_api_key(DEEPSEEK_PROVIDER_ID, api_key)

    def set_provider_api_key(self, provider_id: str, api_key: str) -> None:
        """Save a provider API key in the operating system credential store."""
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("API key cannot be empty.")
        try:
            keyring.set_password(
                KEYRING_SERVICE_NAME,
                self._provider_keyring_account(provider_id),
                normalized_key,
            )
        except Exception as error:
            raise RuntimeError("系统凭据库不可用，API Key 未保存。") from error

    def delete_api_key(self) -> None:
        """Delete the DeepSeek API key from the operating system credential store."""
        self.delete_provider_api_key(DEEPSEEK_PROVIDER_ID)

    def delete_provider_api_key(self, provider_id: str) -> None:
        """Delete a provider API key from the operating system credential store."""
        try:
            keyring.delete_password(
                KEYRING_SERVICE_NAME,
                self._provider_keyring_account(provider_id),
            )
        except PasswordDeleteError:
            return
        except Exception as error:
            raise RuntimeError("系统凭据库不可用，无法删除 API Key。") from error

    def has_api_key(self) -> bool:
        """Return whether a non-empty API key exists in the credential store."""
        api_key = self.get_api_key()
        return bool(api_key and api_key.strip())

    def has_provider_api_key(self, provider_id: str) -> bool:
        """Return whether a provider has a non-empty stored API key."""
        api_key = self.get_provider_api_key(provider_id)
        return bool(api_key and api_key.strip())

    @staticmethod
    def _provider_keyring_account(provider_id: str) -> str:
        if provider_id == DEEPSEEK_PROVIDER_ID:
            return KEYRING_ACCOUNT_NAME
        if provider_id == OPENAI_COMPATIBLE_PROVIDER_ID:
            return OPENAI_COMPATIBLE_KEYRING_ACCOUNT_NAME
        raise ValueError(f"Unsupported model provider: {provider_id}")


def get_provider_id(settings: Mapping[str, Any]) -> str:
    """Return a supported provider ID, preserving DeepSeek as the legacy default."""
    provider_id = settings.get("provider", DEEPSEEK_PROVIDER_ID)
    if provider_id in SUPPORTED_PROVIDER_IDS:
        return str(provider_id)
    return DEEPSEEK_PROVIDER_ID


def get_context_optimization_mode(settings: Mapping[str, Any]) -> str:
    """Return a supported context mode, preserving Raw for legacy settings."""
    mode = settings.get(
        "context_optimization_mode",
        CONTEXT_OPTIMIZATION_RAW,
    )
    if mode in SUPPORTED_CONTEXT_OPTIMIZATION_MODES:
        return str(mode)
    return CONTEXT_OPTIMIZATION_RAW


def get_active_model(settings: Mapping[str, Any]) -> str:
    """Return the model name selected for the active provider."""
    if get_provider_id(settings) == OPENAI_COMPATIBLE_PROVIDER_ID:
        compatible_model = settings.get("openai_compatible_model", "")
        if isinstance(compatible_model, str) and compatible_model.strip():
            return compatible_model.strip()
    model = settings.get("model", DEFAULT_SETTINGS["model"])
    return str(model).strip() or str(DEFAULT_SETTINGS["model"])


def is_provider_configured(settings_manager: SettingsManager) -> bool:
    """Return whether the active provider has the minimum local configuration."""
    settings = settings_manager.load()
    if get_provider_id(settings) == OPENAI_COMPATIBLE_PROVIDER_ID:
        base_url = settings.get("openai_compatible_base_url")
        model = settings.get("openai_compatible_model")
        return bool(
            isinstance(base_url, str)
            and base_url.strip()
            and isinstance(model, str)
            and model.strip()
        )
    return settings_manager.has_api_key()

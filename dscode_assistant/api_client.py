"""DeepSeek API communication and its Qt background worker."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from threading import Event
from typing import Any, Final

import httpx
from PySide6.QtCore import QThread, Signal

from .models import ChatOptions
from .settings import SettingsManager


API_BASE_URL: Final = "https://api.deepseek.com"
CHAT_COMPLETIONS_URL: Final = f"{API_BASE_URL}/chat/completions"
MODELS_URL: Final = f"{API_BASE_URL}/models"


class DeepSeekClient:
    """Call the official DeepSeek API directly with httpx."""

    def __init__(
        self,
        settings_manager: SettingsManager,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings_manager = settings_manager
        self._http_client = http_client

    def test_connection(self) -> bool:
        """Verify the stored API key by requesting the official model list."""
        api_key = self._require_api_key()
        timeout = float(self._settings_manager.load()["request_timeout"])

        try:
            if self._http_client is not None:
                response = self._http_client.get(
                    MODELS_URL,
                    headers=self._headers(api_key),
                    timeout=timeout,
                )
            else:
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(
                        MODELS_URL,
                        headers=self._headers(api_key),
                    )

            self._raise_for_status(response)
            payload = response.json()
        except json.JSONDecodeError as error:
            raise RuntimeError("DeepSeek API 返回了无法解析的响应。") from error
        except httpx.TimeoutException as error:
            raise RuntimeError("连接 DeepSeek API 超时，请检查网络设置。") from error
        except httpx.RequestError as error:
            raise RuntimeError("无法连接 DeepSeek 官方 API，请检查网络连接。") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError("DeepSeek API 返回了意外的响应格式。")
        return True

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        options: ChatOptions,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        """Yield text chunks from an official streaming chat completion."""
        api_key = self._require_api_key()
        payload: dict[str, Any] = {
            "model": options.model,
            "messages": [dict(message) for message in messages],
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": True,
        }
        timeout = httpx.Timeout(options.request_timeout)
        cancel_check = is_cancelled or (lambda: False)

        try:
            if self._http_client is not None:
                yield from self._read_stream(
                    self._http_client,
                    payload,
                    api_key,
                    timeout,
                    cancel_check,
                )
            else:
                with httpx.Client(timeout=timeout) as client:
                    yield from self._read_stream(
                        client,
                        payload,
                        api_key,
                        timeout,
                        cancel_check,
                    )
        except httpx.TimeoutException as error:
            raise RuntimeError("DeepSeek API 请求超时，请稍后重试。") from error
        except httpx.RequestError as error:
            raise RuntimeError("无法连接 DeepSeek 官方 API，请检查网络连接。") from error

    def _read_stream(
        self,
        client: httpx.Client,
        payload: Mapping[str, Any],
        api_key: str,
        timeout: httpx.Timeout,
        is_cancelled: Callable[[], bool],
    ) -> Iterator[str]:
        received_done_marker = False

        with client.stream(
            "POST",
            CHAT_COMPLETIONS_URL,
            headers=self._headers(api_key),
            json=payload,
            timeout=timeout,
        ) as response:
            self._raise_for_status(response)

            for line in response.iter_lines():
                if is_cancelled():
                    return
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue

                data = line[5:].strip()
                if data == "[DONE]":
                    received_done_marker = True
                    break

                try:
                    event = json.loads(data)
                    choices = event.get("choices", [])
                    if not choices:
                        continue
                    content = choices[0].get("delta", {}).get("content")
                except (json.JSONDecodeError, AttributeError, IndexError, TypeError) as error:
                    raise RuntimeError("DeepSeek API 返回了无法解析的流式响应。") from error

                if isinstance(content, str) and content:
                    yield content

        if not received_done_marker and not is_cancelled():
            raise RuntimeError("DeepSeek API 流式响应意外中断。")

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _require_api_key(self) -> str:
        api_key = self._settings_manager.get_api_key()
        if api_key is None or not api_key.strip():
            raise RuntimeError("请先在设置中保存 DeepSeek API Key。")
        return api_key.strip()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return

        messages = {
            400: "请求格式错误，请检查聊天参数。",
            401: "API Key 无效，请检查后重试。",
            402: "DeepSeek API 账户余额不足或不可用。",
            404: "DeepSeek API 地址或模型不存在。",
            422: "请求参数无效，请检查模型设置。",
            429: "请求过于频繁，请稍后重试。",
            500: "DeepSeek 服务暂时出现故障，请稍后重试。",
            503: "DeepSeek 服务繁忙，请稍后重试。",
        }
        message = messages.get(
            response.status_code,
            f"DeepSeek API 请求失败（HTTP {response.status_code}）。",
        )
        raise RuntimeError(message)


class ChatWorker(QThread):
    """Run a streaming DeepSeek request without blocking the GUI thread."""

    chunk_received = Signal(str)
    completed = Signal()
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        client: DeepSeekClient,
        messages: Sequence[Mapping[str, str]],
        options: ChatOptions,
    ) -> None:
        super().__init__()
        self._client = client
        self._messages = [dict(message) for message in messages]
        self._options = options
        self._cancel_event = Event()

    def run(self) -> None:
        """Execute the streaming request and emit its result through Qt signals."""
        try:
            for chunk in self._client.stream_chat(
                self._messages,
                self._options,
                self._cancel_event.is_set,
            ):
                if self._cancel_event.is_set():
                    self.cancelled.emit()
                    return
                self.chunk_received.emit(chunk)

            if self._cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.completed.emit()
        except Exception as error:
            if self._cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(str(error))

    def cancel(self) -> None:
        """Request cancellation of the active streaming request."""
        self._cancel_event.set()
        self.requestInterruption()

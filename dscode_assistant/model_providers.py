"""Extensible model provider contracts and basic adapters."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

import httpx

from .api_client import DeepSeekClient
from .models import ChatOptions


DEFAULT_PROVIDER_ID: Final = "deepseek"
CredentialSource = str | Callable[[], str | None] | None


class ModelProvider(ABC):
    """Common contract for remote or local chat-completion providers."""

    provider_id: str
    display_name: str

    @abstractmethod
    def test_connection(self) -> bool:
        """Validate that the configured provider endpoint is reachable."""

    @abstractmethod
    def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        options: ChatOptions,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        """Yield text chunks for one streaming chat completion."""


class DeepSeekProvider(ModelProvider):
    """Expose the existing DeepSeekClient through the provider contract."""

    provider_id = DEFAULT_PROVIDER_ID
    display_name = "DeepSeek"

    def __init__(self, client: DeepSeekClient) -> None:
        self._client = client

    def test_connection(self) -> bool:
        return self._client.test_connection()

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        options: ChatOptions,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        yield from self._client.stream_chat(messages, options, is_cancelled)


class OpenAICompatibleProvider(ModelProvider):
    """Call an OpenAI-compatible models and chat-completions API."""

    provider_id = "openai-compatible"
    display_name = "OpenAI Compatible"

    def __init__(
        self,
        base_url: str,
        api_key: CredentialSource = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = self._normalize_base_url(base_url)
        self._credential_source = api_key
        self._http_client = http_client

    @property
    def base_url(self) -> str:
        return self._base_url

    def test_connection(self) -> bool:
        """Validate the endpoint using the standard compatible models route."""
        try:
            if self._http_client is not None:
                response = self._http_client.get(
                    self._endpoint("models"),
                    headers=self._headers(),
                    timeout=30.0,
                )
            else:
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(
                        self._endpoint("models"),
                        headers=self._headers(),
                    )
            self._raise_for_status(response)
            payload = response.json()
        except json.JSONDecodeError as error:
            raise RuntimeError("模型提供商返回了无法解析的响应。") from error
        except httpx.TimeoutException as error:
            raise RuntimeError("连接模型提供商超时，请检查接口设置。") from error
        except httpx.RequestError as error:
            raise RuntimeError("无法连接模型提供商，请检查接口地址和网络。") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError("模型提供商返回了意外的模型列表格式。")
        return True

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        options: ChatOptions,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        """Yield chunks from an OpenAI-compatible SSE chat completion."""
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
                    timeout,
                    cancel_check,
                )
            else:
                with httpx.Client(timeout=timeout) as client:
                    yield from self._read_stream(
                        client,
                        payload,
                        timeout,
                        cancel_check,
                    )
        except httpx.TimeoutException as error:
            raise RuntimeError("模型提供商请求超时，请稍后重试。") from error
        except httpx.RequestError as error:
            raise RuntimeError("无法连接模型提供商，请检查接口地址和网络。") from error

    def _read_stream(
        self,
        client: httpx.Client,
        payload: Mapping[str, Any],
        timeout: httpx.Timeout,
        is_cancelled: Callable[[], bool],
    ) -> Iterator[str]:
        received_done_marker = False
        with client.stream(
            "POST",
            self._endpoint("chat/completions"),
            headers=self._headers(),
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
                    raise RuntimeError(
                        "模型提供商返回了无法解析的流式响应。"
                    ) from error
                if isinstance(content, str) and content:
                    yield content

        if not received_done_marker and not is_cancelled():
            raise RuntimeError("模型提供商流式响应意外中断。")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        api_key = self._resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _resolve_api_key(self) -> str | None:
        value = (
            self._credential_source()
            if callable(self._credential_source)
            else self._credential_source
        )
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _endpoint(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("接口地址必须是有效的 HTTP 或 HTTPS URL。")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("接口地址中不能包含用户名或密码。")
        if parsed.query or parsed.fragment:
            raise ValueError("接口地址中不能包含查询参数或片段。")
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        messages = {
            400: "请求格式错误，请检查模型和聊天参数。",
            401: "API Key 无效或缺少，请检查提供商配置。",
            403: "模型提供商拒绝了当前请求。",
            404: "接口地址或模型不存在。",
            422: "请求参数不受模型提供商支持。",
            429: "请求过于频繁，请稍后重试。",
        }
        message = messages.get(
            response.status_code,
            f"模型提供商请求失败（HTTP {response.status_code}）。",
        )
        raise RuntimeError(message)


class ProviderRegistry:
    """Small in-process registry for provider instances."""

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ValueError("Provider ID cannot be empty.")
        if provider_id in self._providers:
            raise ValueError(f"Provider '{provider_id}' is already registered.")
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> ModelProvider:
        try:
            return self._providers[provider_id]
        except KeyError as error:
            raise KeyError(f"Unknown model provider: {provider_id}") from error

    def list_provider_ids(self) -> tuple[str, ...]:
        return tuple(self._providers)

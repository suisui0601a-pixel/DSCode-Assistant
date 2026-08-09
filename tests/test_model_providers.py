"""Tests for extensible model provider contracts and adapters."""

from __future__ import annotations

import json
import unittest
from collections.abc import Callable, Iterator, Mapping, Sequence

import httpx

from dscode_assistant.model_providers import (
    DeepSeekProvider,
    ModelProvider,
    OpenAICompatibleProvider,
    ProviderRegistry,
)
from dscode_assistant.models import ChatOptions


class StubDeepSeekClient:
    def __init__(self) -> None:
        self.connection_tests = 0
        self.calls: list[tuple[Sequence[Mapping[str, str]], ChatOptions]] = []

    def test_connection(self) -> bool:
        self.connection_tests += 1
        return True

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        options: ChatOptions,
        _is_cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        self.calls.append((messages, options))
        yield "existing"
        yield " client"


class MinimalProvider(ModelProvider):
    provider_id = "minimal"
    display_name = "Minimal"

    def test_connection(self) -> bool:
        return True

    def stream_chat(
        self,
        _messages: Sequence[Mapping[str, str]],
        _options: ChatOptions,
        _is_cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[str]:
        yield "ok"


class ModelProviderTests(unittest.TestCase):
    def test_deepseek_adapter_delegates_without_changing_existing_client(self) -> None:
        client = StubDeepSeekClient()
        provider = DeepSeekProvider(client)
        messages = [{"role": "user", "content": "hello"}]
        options = ChatOptions(model="deepseek-chat")

        self.assertTrue(provider.test_connection())
        self.assertEqual(list(provider.stream_chat(messages, options)), ["existing", " client"])
        self.assertEqual(client.connection_tests, 1)
        self.assertEqual(client.calls, [(messages, options)])

    def test_openai_compatible_connection_and_stream_payload(self) -> None:
        requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "local-model"}]})
            body = (
                'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(
                200,
                content=body.encode("utf-8"),
                headers={"Content-Type": "text/event-stream"},
            )

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            provider = OpenAICompatibleProvider(
                "https://models.example/v1/",
                api_key=lambda: " compatible-key ",
                http_client=client,
            )
            self.assertTrue(provider.test_connection())
            chunks = list(
                provider.stream_chat(
                    [{"role": "user", "content": "hello"}],
                    ChatOptions(model="local-model", max_tokens=123),
                )
            )

        self.assertEqual(chunks, ["Hello", " world"])
        self.assertEqual([request.url.path for request in requests], [
            "/v1/models",
            "/v1/chat/completions",
        ])
        self.assertTrue(all(
            request.headers["Authorization"] == "Bearer compatible-key"
            for request in requests
        ))
        payload = json.loads(requests[1].content)
        self.assertEqual(payload["model"], "local-model")
        self.assertEqual(payload["max_tokens"], 123)
        self.assertTrue(payload["stream"])

    def test_openai_compatible_local_endpoint_does_not_require_key(self) -> None:
        captured_headers: dict[str, str] = {}

        def handle(request: httpx.Request) -> httpx.Response:
            captured_headers.update(request.headers)
            return httpx.Response(200, json={"data": []})

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            provider = OpenAICompatibleProvider(
                "http://127.0.0.1:11434/v1",
                http_client=client,
            )
            self.assertTrue(provider.test_connection())

        self.assertNotIn("authorization", captured_headers)
        self.assertEqual(provider.base_url, "http://127.0.0.1:11434/v1")

    def test_openai_compatible_rejects_credentials_in_url(self) -> None:
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider("https://user:password@example.com/v1")

    def test_openai_compatible_reports_http_error_without_response_body(self) -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(401))
        with httpx.Client(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                "https://models.example/v1",
                api_key="invalid",
                http_client=client,
            )
            with self.assertRaisesRegex(RuntimeError, "API Key"):
                provider.test_connection()

    def test_registry_rejects_duplicates_and_unknown_ids(self) -> None:
        registry = ProviderRegistry()
        provider = MinimalProvider()
        registry.register(provider)

        self.assertEqual(registry.list_provider_ids(), ("minimal",))
        self.assertIs(registry.get("minimal"), provider)
        with self.assertRaises(ValueError):
            registry.register(MinimalProvider())
        with self.assertRaises(KeyError):
            registry.get("missing")


if __name__ == "__main__":
    unittest.main()

"""Localhost-only automation control surface for DSCode Assistant."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Final
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Signal


AUTOMATION_HOST: Final = "127.0.0.1"
AUTOMATION_PORT: Final = 18765
MAX_REQUEST_BYTES: Final = 64 * 1024


@dataclass(slots=True)
class AutomationRequest:
    """A command handed from an HTTP worker thread to the Qt GUI thread."""

    action: str
    payload: dict[str, Any]
    completed: threading.Event = field(default_factory=threading.Event)
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    response: dict[str, Any] = field(default_factory=dict)

    def finish(self, status_code: int, response: dict[str, Any]) -> None:
        self.status_code = status_code
        self.response = response
        self.completed.set()


class AutomationBridge(QObject):
    """Queue automation commands safely onto the Qt application thread."""

    command_received = Signal(object)

    def dispatch(
        self,
        action: str,
        payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request = AutomationRequest(action, payload)
        self.command_received.emit(request)
        if not request.completed.wait(timeout=5.0):
            return HTTPStatus.GATEWAY_TIMEOUT, {
                "ok": False,
                "error": "GUI did not respond in time.",
            }
        return request.status_code, request.response


AutomationDispatcher = Callable[[str, dict[str, Any]], tuple[int, dict[str, Any]]]


class _LocalAutomationHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class AutomationServer:
    """Expose a small JSON API bound exclusively to the IPv4 loopback address."""

    def __init__(
        self,
        dispatcher: AutomationDispatcher,
        port: int = AUTOMATION_PORT,
    ) -> None:
        self._dispatcher = dispatcher
        self._requested_port = port
        self._server: _LocalAutomationHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._server is None:
            return self._requested_port
        return int(self._server.server_address[1])

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the loopback HTTP server without blocking the Qt event loop."""
        if self.is_running:
            return

        dispatcher = self._dispatcher

        class RequestHandler(BaseHTTPRequestHandler):
            server_version = "DSCodeAutomation/1.0"

            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                path = urlsplit(self.path).path
                if path == "/v1/status":
                    self._dispatch("status", {})
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                path = urlsplit(self.path).path
                actions = {
                    "/v1/app/activate": "activate",
                    "/v1/projects/open": "open_project",
                    "/v1/tasks": "create_task",
                }
                action = actions.get(path)
                if action is None:
                    self._send_json(
                        HTTPStatus.NOT_FOUND,
                        {"ok": False, "error": "Not found."},
                    )
                    return
                payload = self._read_payload()
                if payload is not None:
                    self._dispatch(action, payload)

            def _read_payload(self) -> dict[str, Any] | None:
                if self.headers.get_content_type() != "application/json":
                    self._send_json(
                        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                        {"ok": False, "error": "Content-Type must be application/json."},
                    )
                    return None
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    content_length = -1
                if content_length < 0 or content_length > MAX_REQUEST_BYTES:
                    self._send_json(
                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        {"ok": False, "error": "Request body is too large."},
                    )
                    return None
                try:
                    payload = json.loads(self.rfile.read(content_length) or b"{}")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "Invalid JSON body."},
                    )
                    return None
                if not isinstance(payload, dict):
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "JSON body must be an object."},
                    )
                    return None
                return payload

            def _dispatch(self, action: str, payload: dict[str, Any]) -> None:
                try:
                    status_code, response = dispatcher(action, payload)
                except Exception:
                    status_code, response = HTTPStatus.INTERNAL_SERVER_ERROR, {
                        "ok": False,
                        "error": "Automation request failed.",
                    }
                self._send_json(status_code, response)

            def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(int(status_code))
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                # Never record task text, project paths, or other user content.
                return

        self._server = _LocalAutomationHTTPServer(
            (AUTOMATION_HOST, self._requested_port),
            RequestHandler,
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="dscode-local-automation",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop accepting commands and release the loopback port."""
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

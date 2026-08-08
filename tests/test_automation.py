"""Tests for the localhost-only DSCode Assistant automation surface."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from dscode_assistant.automation import (
    AUTOMATION_HOST,
    AutomationBridge,
    AutomationRequest,
    AutomationServer,
)
from dscode_assistant.database import Database
from dscode_assistant.main_window import MainWindow


class FakeSettings:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def get_data_dir(self) -> Path:
        return self._data_dir

    def load(self) -> dict[str, str | int | float]:
        return {
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 256,
            "request_timeout": 10.0,
            "theme": "system",
        }

    def get_api_key(self) -> None:
        return None

    def has_api_key(self) -> bool:
        return False


class AutomationServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

        def dispatch(
            action: str,
            payload: dict[str, object],
        ) -> tuple[int, dict[str, object]]:
            self.calls.append((action, payload))
            if action == "create_task":
                return HTTPStatus.CREATED, {"ok": True, "state": "ready"}
            return HTTPStatus.OK, {"ok": True, "state": "ready"}

        self.server = AutomationServer(dispatch, port=0)
        self.server.start()
        self.base_url = f"http://{AUTOMATION_HOST}:{self.server.port}"

    def tearDown(self) -> None:
        self.server.stop()

    def _request(
        self,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, object]]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        with urlopen(request, timeout=2.0) as response:
            return response.status, json.loads(response.read())

    def test_status_and_task_routes_dispatch_expected_actions(self) -> None:
        status_code, status = self._request("/v1/status")
        self.assertEqual(status_code, HTTPStatus.OK)
        self.assertTrue(status["ok"])

        status_code, task = self._request(
            "/v1/tasks",
            {"title": "Inspect", "instruction": "Review this project"},
        )
        self.assertEqual(status_code, HTTPStatus.CREATED)
        self.assertTrue(task["ok"])
        self.assertEqual(
            self.calls,
            [
                ("status", {}),
                (
                    "create_task",
                    {"title": "Inspect", "instruction": "Review this project"},
                ),
            ],
        )

    def test_server_binds_only_to_ipv4_loopback_and_stops(self) -> None:
        self.assertEqual(self.server._server.server_address[0], AUTOMATION_HOST)
        self.assertTrue(self.server.is_running)
        self.server.stop()
        self.assertFalse(self.server.is_running)

    def test_rejects_non_json_task_request(self) -> None:
        request = Request(self.base_url + "/v1/tasks", data=b"plain text")
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=2.0)
        try:
            self.assertEqual(context.exception.code, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        finally:
            context.exception.close()


class AutomationWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_open_project_and_create_task_prefills_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project_path = root / "sample-project"
            project_path.mkdir()
            settings = FakeSettings(root / "data")
            database = Database(settings)
            window = MainWindow(database, settings)
            try:
                open_request = AutomationRequest(
                    "open_project",
                    {"path": str(project_path)},
                )
                window.handle_automation_request(open_request)
                self.assertEqual(open_request.status_code, HTTPStatus.OK)

                task_request = AutomationRequest(
                    "create_task",
                    {"title": "实现接口", "instruction": "添加健康检查"},
                )
                window.handle_automation_request(task_request)
                self.application.processEvents()

                self.assertEqual(task_request.status_code, HTTPStatus.CREATED)
                self.assertEqual(len(database.list_sessions()), 1)
                self.assertIn(str(project_path.resolve()), window.chat_widget._input.toPlainText())
                self.assertIn("添加健康检查", window.chat_widget._input.toPlainText())
                self.assertEqual(database.get_messages(window.chat_widget.active_session_id), [])
                self.assertEqual(task_request.response["current_task"]["status"], "drafted")
            finally:
                window.close()
                self.application.processEvents()

    def test_missing_project_is_rejected_without_creating_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = FakeSettings(root / "data")
            database = Database(settings)
            window = MainWindow(database, settings)
            try:
                request = AutomationRequest(
                    "create_task",
                    {
                        "instruction": "Inspect",
                        "project_path": str(root / "missing"),
                    },
                )
                window.handle_automation_request(request)
                self.assertEqual(request.status_code, HTTPStatus.NOT_FOUND)
                self.assertEqual(database.list_sessions(), [])
            finally:
                window.close()
                self.application.processEvents()

    def test_http_command_crosses_bridge_to_gui_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = FakeSettings(root / "data")
            database = Database(settings)
            window = MainWindow(database, settings)
            bridge = AutomationBridge()
            bridge.command_received.connect(window.handle_automation_request)
            server = AutomationServer(bridge.dispatch, port=0)
            result: dict[str, object] = {}
            server.start()
            try:
                def request_status() -> None:
                    address = f"http://{AUTOMATION_HOST}:{server.port}/v1/status"
                    with urlopen(address, timeout=2.0) as response:
                        result["status"] = response.status
                        result["payload"] = json.loads(response.read())

                client_thread = threading.Thread(target=request_status)
                client_thread.start()
                deadline = time.monotonic() + 3.0
                while client_thread.is_alive() and time.monotonic() < deadline:
                    self.application.processEvents()
                    time.sleep(0.005)
                client_thread.join(timeout=0.2)

                self.assertFalse(client_thread.is_alive())
                self.assertEqual(result["status"], HTTPStatus.OK)
                self.assertEqual(result["payload"]["application"], "DSCode Assistant")
            finally:
                server.stop()
                window.close()
                self.application.processEvents()


if __name__ == "__main__":
    unittest.main()

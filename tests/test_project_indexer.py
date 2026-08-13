"""Tests for safe, content-free project metadata indexing."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from dscode_assistant.project import (
    FileKind,
    IndexPolicy,
    ProjectDescriptor,
    ProjectIndexer,
)


class ProjectIndexerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.indexer = ProjectIndexer()

    @staticmethod
    def _descriptor(root: Path) -> ProjectDescriptor:
        return ProjectDescriptor("project-1", "Sample", root)

    def test_records_relative_paths_and_file_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "src" / "main.py"
            source.parent.mkdir()
            source.write_text("print('hello')", encoding="utf-8")

            snapshot = self.indexer.index(self._descriptor(root))

            self.assertEqual(len(snapshot.files), 1)
            project_file = snapshot.files[0]
            self.assertEqual(project_file.relative_path, "src/main.py")
            self.assertFalse(Path(project_file.relative_path).is_absolute())
            self.assertEqual(project_file.extension, ".py")
            self.assertEqual(project_file.kind, FileKind.SOURCE)
            self.assertEqual(project_file.size, source.stat().st_size)
            self.assertEqual(project_file.modified_ns, source.stat().st_mtime_ns)
            with self.assertRaises(FrozenInstanceError):
                project_file.size = 0
            self.assertFalse(hasattr(project_file, "__dict__"))

    def test_default_exclusions_and_sensitive_names_are_not_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for directory in (
                ".git",
                "node_modules",
                "venv",
                "__pycache__",
                "build",
                "dist",
            ):
                excluded = root / directory
                excluded.mkdir()
                (excluded / "hidden.py").write_text("private", encoding="utf-8")
            for name in (".env", "server.key", "certificate.pem", "credentials.json"):
                (root / name).write_text("secret", encoding="utf-8")
            (root / "visible.py").write_text("visible", encoding="utf-8")

            snapshot = self.indexer.index(self._descriptor(root))

            self.assertEqual(
                tuple(project_file.relative_path for project_file in snapshot.files),
                ("visible.py",),
            )
            self.assertEqual(snapshot.report.skipped_directories, 6)
            self.assertEqual(snapshot.report.excluded_sensitive_files, 4)
            self.assertNotIn("credentials", repr(snapshot.files))

    def test_max_files_truncates_large_directory_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for index in range(10):
                (root / f"file_{index:02}.py").write_text(str(index), encoding="utf-8")
            policy = IndexPolicy(max_files=3)

            first = self.indexer.index(self._descriptor(root), policy)
            second = self.indexer.index(self._descriptor(root), policy)

            self.assertTrue(first.report.truncated)
            self.assertEqual(first.report.indexed_files, 3)
            self.assertEqual(
                tuple(project_file.relative_path for project_file in first.files),
                ("file_00.py", "file_01.py", "file_02.py"),
            )
            self.assertEqual(first, second)

    def test_symlinks_are_skipped_without_leaving_project_root(self) -> None:
        with (
            tempfile.TemporaryDirectory() as project_directory,
            tempfile.TemporaryDirectory() as outside_directory,
        ):
            root = Path(project_directory)
            outside = Path(outside_directory)
            outside_file = outside / "outside.py"
            outside_file.write_text("outside", encoding="utf-8")
            link = root / "linked.py"
            try:
                link.symlink_to(outside_file)
            except OSError as error:
                self.skipTest(f"Symlink creation is unavailable: {error}")
            (root / "inside.py").write_text("inside", encoding="utf-8")

            snapshot = self.indexer.index(self._descriptor(root))

            self.assertEqual(
                tuple(project_file.relative_path for project_file in snapshot.files),
                ("inside.py",),
            )
            self.assertEqual(snapshot.report.skipped_files, 1)

    def test_default_symlink_skip_does_not_require_symlink_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            class FakeSymlinkEntry:
                name = "linked.py"
                path = str(root / name)

                @staticmethod
                def is_symlink() -> bool:
                    return True

                @staticmethod
                def is_dir(*, follow_symlinks: bool) -> bool:
                    return False

                @staticmethod
                def stat(*, follow_symlinks: bool):
                    raise AssertionError("Skipped symlinks must not be stat-indexed.")

            class FakeScandir:
                def __enter__(self):
                    return iter((FakeSymlinkEntry(),))

                def __exit__(self, *_args: object) -> None:
                    return None

            with patch(
                "dscode_assistant.project.indexer.os.scandir",
                return_value=FakeScandir(),
            ):
                snapshot = self.indexer.index(self._descriptor(root))

            self.assertEqual(snapshot.files, ())
            self.assertEqual(snapshot.report.skipped_files, 1)

    def test_permission_error_is_counted_without_exposing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            blocked = root / "blocked"
            blocked.mkdir()
            (root / "visible.py").write_text("visible", encoding="utf-8")
            real_scandir = os.scandir

            def guarded_scandir(path: object):
                if Path(path) == blocked:
                    raise PermissionError("blocked")
                return real_scandir(path)

            with patch("dscode_assistant.project.indexer.os.scandir", guarded_scandir):
                snapshot = self.indexer.index(self._descriptor(root))

            self.assertEqual(snapshot.report.permission_errors, 1)
            self.assertEqual(snapshot.report.skipped_directories, 1)
            self.assertEqual(snapshot.files[0].relative_path, "visible.py")

    def test_indexer_never_uses_content_reading_apis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "source.py").write_text("do not read me", encoding="utf-8")

            with (
                patch.object(Path, "read_text", side_effect=AssertionError("read_text called")),
                patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes called")),
                patch("builtins.open", side_effect=AssertionError("open called")),
            ):
                snapshot = self.indexer.index(self._descriptor(root))

            self.assertEqual(snapshot.files[0].relative_path, "source.py")

    def test_repeated_unlimited_runs_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "z.py").write_text("z", encoding="utf-8")
            (root / "A.ts").write_text("a", encoding="utf-8")
            nested = root / "src"
            nested.mkdir()
            (nested / "main.cpp").write_text("main", encoding="utf-8")

            first = self.indexer.index(self._descriptor(root))
            second = self.indexer.index(self._descriptor(root))

            self.assertEqual(first, second)
            self.assertEqual(
                tuple(project_file.relative_path for project_file in first.files),
                ("A.ts", "src/main.cpp", "z.py"),
            )


if __name__ == "__main__":
    unittest.main()

"""Safe, content-free filesystem indexing for local projects."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from .models import (
    FileKind,
    IndexPolicy,
    IndexReport,
    ProjectDescriptor,
    ProjectFile,
    ProjectSnapshot,
)


class ProjectIndexer:
    """Collect project file metadata without opening file contents."""

    _SOURCE_SUFFIXES: Final = {
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hh",
        ".hpp",
        ".hxx",
        ".java",
        ".js",
        ".jsx",
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
    }
    _CONFIG_NAMES: Final = {
        "cmakelists.txt",
        "makefile",
        "package.json",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "tsconfig.json",
    }
    _CONFIG_SUFFIXES: Final = {
        ".ini",
        ".json",
        ".properties",
        ".toml",
        ".yaml",
        ".yml",
    }
    _DOCUMENTATION_SUFFIXES: Final = {".md", ".rst", ".txt"}
    _ASSET_SUFFIXES: Final = {
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".png",
        ".qss",
        ".svg",
        ".ui",
    }

    def index(
        self,
        project: ProjectDescriptor,
        policy: IndexPolicy | None = None,
    ) -> ProjectSnapshot:
        """Scan one existing directory and return metadata in stable path order."""
        active_policy = policy or IndexPolicy()
        root = project.root_path.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {root}")

        normalized_project = ProjectDescriptor(
            project_id=project.project_id,
            display_name=project.display_name,
            root_path=root,
        )
        files: list[ProjectFile] = []
        counters = _MutableIndexCounters()
        self._scan_directory(
            root,
            root,
            0,
            active_policy,
            files,
            counters,
            set(),
        )
        files.sort(key=lambda item: (item.relative_path.casefold(), item.relative_path))
        report = IndexReport(
            indexed_files=len(files),
            skipped_files=counters.skipped_files,
            skipped_directories=counters.skipped_directories,
            excluded_sensitive_files=counters.excluded_sensitive_files,
            permission_errors=counters.permission_errors,
            truncated=counters.truncated,
        )
        return ProjectSnapshot(normalized_project, tuple(files), report)

    def _scan_directory(
        self,
        root: Path,
        directory: Path,
        depth: int,
        policy: IndexPolicy,
        files: list[ProjectFile],
        counters: _MutableIndexCounters,
        visited_directories: set[Path],
    ) -> None:
        if counters.truncated:
            return
        try:
            resolved_directory = directory.resolve(strict=True)
            resolved_directory.relative_to(root)
        except (OSError, ValueError):
            counters.skipped_directories += 1
            return
        normalized_directory = Path(os.path.normcase(resolved_directory))
        if normalized_directory in visited_directories:
            counters.skipped_directories += 1
            return
        visited_directories.add(normalized_directory)
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: (entry.name.casefold(), entry.name))
        except PermissionError:
            counters.permission_errors += 1
            counters.skipped_directories += 1
            return
        except OSError:
            counters.skipped_directories += 1
            return

        excluded_directories = {name.casefold() for name in policy.excluded_directories}
        for entry in entries:
            if counters.truncated:
                return
            try:
                is_symlink = entry.is_symlink()
                is_directory = entry.is_dir(follow_symlinks=policy.follow_symlinks)
            except PermissionError:
                counters.permission_errors += 1
                counters.skipped_files += 1
                continue
            except OSError:
                counters.skipped_files += 1
                continue

            if is_symlink:
                try:
                    target_is_directory = entry.is_dir(follow_symlinks=True)
                except (OSError, PermissionError):
                    counters.permission_errors += 1
                    counters.skipped_files += 1
                    continue
                if not policy.follow_symlinks:
                    if target_is_directory:
                        counters.skipped_directories += 1
                    else:
                        counters.skipped_files += 1
                    continue
                try:
                    Path(entry.path).resolve(strict=True).relative_to(root)
                except (OSError, ValueError):
                    if target_is_directory:
                        counters.skipped_directories += 1
                    else:
                        counters.skipped_files += 1
                    continue
                is_directory = target_is_directory

            if is_directory:
                if entry.name.casefold() in excluded_directories:
                    counters.skipped_directories += 1
                    continue
                if depth >= policy.max_depth:
                    counters.skipped_directories += 1
                    continue
                self._scan_directory(
                    root,
                    Path(entry.path),
                    depth + 1,
                    policy,
                    files,
                    counters,
                    visited_directories,
                )
                continue

            if self._is_sensitive(entry.name, policy):
                counters.excluded_sensitive_files += 1
                continue
            if len(files) >= policy.max_files:
                counters.truncated = True
                return
            try:
                stat_result = entry.stat(follow_symlinks=policy.follow_symlinks)
            except PermissionError:
                counters.permission_errors += 1
                counters.skipped_files += 1
                continue
            except OSError:
                counters.skipped_files += 1
                continue

            relative_path = Path(entry.path).relative_to(root).as_posix()
            extension = Path(entry.name).suffix.casefold()
            files.append(
                ProjectFile(
                    relative_path=relative_path,
                    extension=extension,
                    kind=self._classify_file(relative_path, extension),
                    size=stat_result.st_size,
                    modified_ns=stat_result.st_mtime_ns,
                )
            )

    @staticmethod
    def _is_sensitive(name: str, policy: IndexPolicy) -> bool:
        normalized = name.casefold()
        return (
            normalized in {value.casefold() for value in policy.sensitive_exact_names}
            or any(normalized.endswith(value.casefold()) for value in policy.sensitive_suffixes)
            or any(normalized.startswith(value.casefold()) for value in policy.sensitive_prefixes)
        )

    @classmethod
    def _classify_file(cls, relative_path: str, extension: str) -> FileKind:
        path = Path(relative_path)
        name = path.name.casefold()
        parts = {part.casefold() for part in path.parts}
        stem = path.stem.casefold()
        if (
            "tests" in parts
            or "test" in parts
            or stem.startswith("test_")
            or stem.endswith("_test")
        ):
            return FileKind.TEST
        if name in cls._CONFIG_NAMES or extension in cls._CONFIG_SUFFIXES:
            return FileKind.CONFIG
        if extension in cls._SOURCE_SUFFIXES:
            return FileKind.SOURCE
        if extension in cls._DOCUMENTATION_SUFFIXES:
            return FileKind.DOCUMENTATION
        if extension in cls._ASSET_SUFFIXES:
            return FileKind.ASSET
        return FileKind.UNKNOWN


class _MutableIndexCounters:
    """Internal mutable counters excluded from the public metadata model."""

    def __init__(self) -> None:
        self.skipped_files = 0
        self.skipped_directories = 0
        self.excluded_sensitive_files = 0
        self.permission_errors = 0
        self.truncated = False

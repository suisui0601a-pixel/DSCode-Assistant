"""Immutable models for local project metadata indexing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class FileKind(str, Enum):
    """Coarse deterministic file categories derived from names and suffixes."""

    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    ASSET = "asset"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProjectDescriptor:
    """Local identity of a project without any source-code content."""

    project_id: str
    display_name: str
    root_path: Path

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("Project ID cannot be empty.")
        if not self.display_name.strip():
            raise ValueError("Project display name cannot be empty.")


@dataclass(frozen=True, slots=True)
class ProjectFile:
    """Filesystem metadata for one non-sensitive project file."""

    relative_path: str
    extension: str
    kind: FileKind
    size: int
    modified_ns: int

    def __post_init__(self) -> None:
        path = Path(self.relative_path)
        if not self.relative_path or path.is_absolute() or ".." in path.parts:
            raise ValueError("Project file path must be a safe relative path.")
        if self.extension and not self.extension.startswith("."):
            raise ValueError("Project file extension must start with a dot.")
        if self.size < 0:
            raise ValueError("Project file size cannot be negative.")
        if self.modified_ns < 0:
            raise ValueError("Project file modification time cannot be negative.")


@dataclass(frozen=True, slots=True)
class IndexPolicy:
    """Resource and exclusion limits for a deterministic metadata scan."""

    max_files: int = 10_000
    max_depth: int = 20
    follow_symlinks: bool = False
    excluded_directories: tuple[str, ...] = (
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "build",
        "dist",
    )
    sensitive_exact_names: tuple[str, ...] = (".env",)
    sensitive_suffixes: tuple[str, ...] = (".key", ".pem")
    sensitive_prefixes: tuple[str, ...] = ("credentials",)

    def __post_init__(self) -> None:
        if self.max_files <= 0:
            raise ValueError("Maximum indexed file count must be positive.")
        if self.max_depth < 0:
            raise ValueError("Maximum scan depth cannot be negative.")
        for values in (
            self.excluded_directories,
            self.sensitive_exact_names,
            self.sensitive_suffixes,
            self.sensitive_prefixes,
        ):
            if any(not value.strip() for value in values):
                raise ValueError("Index exclusion values cannot be empty.")


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Local scan counters that do not expose skipped sensitive filenames."""

    indexed_files: int = 0
    skipped_files: int = 0
    skipped_directories: int = 0
    excluded_sensitive_files: int = 0
    permission_errors: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        counters = (
            self.indexed_files,
            self.skipped_files,
            self.skipped_directories,
            self.excluded_sensitive_files,
            self.permission_errors,
        )
        if any(value < 0 for value in counters):
            raise ValueError("Index report counters cannot be negative.")


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    """A deterministic, content-free project metadata snapshot."""

    project: ProjectDescriptor
    files: tuple[ProjectFile, ...]
    report: IndexReport
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version <= 0:
            raise ValueError("Project snapshot schema version must be positive.")
        paths = tuple(project_file.relative_path for project_file in self.files)
        if len(paths) != len(set(paths)):
            raise ValueError("Project snapshot paths cannot contain duplicates.")
        if paths != tuple(sorted(paths, key=lambda value: (value.casefold(), value))):
            raise ValueError("Project snapshot files must use deterministic path order.")
        if self.report.indexed_files != len(self.files):
            raise ValueError("Indexed file count must match snapshot files.")

"""Public interface for local, content-free project metadata indexing."""

from .indexer import ProjectIndexer
from .models import (
    FileKind,
    IndexPolicy,
    IndexReport,
    ProjectDescriptor,
    ProjectFile,
    ProjectSnapshot,
)

__all__ = [
    "FileKind",
    "IndexPolicy",
    "IndexReport",
    "ProjectDescriptor",
    "ProjectFile",
    "ProjectIndexer",
    "ProjectSnapshot",
]

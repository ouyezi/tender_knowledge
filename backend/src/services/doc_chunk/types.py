from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID


@dataclass
class ImportContext:
    workspace_path: Path
    tree_id_map: dict[str, UUID] = field(default_factory=dict)
    outline_id_map: dict[str, UUID] = field(default_factory=dict)
    image_ref_map: dict[str, UUID] = field(default_factory=dict)
    chunk_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    parse_strategy: str = "doc_chunk"
    outline_node_id_to_tree_id: dict[str, UUID] = field(default_factory=dict)
    content_md: str | None = None


@dataclass
class ImportResult:
    document_id: UUID
    tree_node_count: int
    parse_engine: str
    tree_id_map: dict[str, UUID] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class DocChunkImportError(Exception):
    def __init__(self, message: str, *, code: str = "DOC_CHUNK_IMPORT_FAILED"):
        self.code = code
        super().__init__(message)

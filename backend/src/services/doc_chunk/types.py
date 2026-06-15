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


@dataclass
class ImportResult:
    document_id: UUID
    bid_outline_id: UUID
    tree_node_count: int
    outline_node_count: int
    candidate_count: int
    parse_engine: str
    extract_strategy: str
    tree_id_map: dict[str, UUID] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class OutlineTocEntry:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int
    source_node_id: UUID | None = None


class DocChunkImportError(Exception):
    def __init__(self, message: str, *, code: str = "DOC_CHUNK_IMPORT_FAILED"):
        self.code = code
        super().__init__(message)

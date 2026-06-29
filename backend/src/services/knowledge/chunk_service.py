from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.chunk_embedding import ChunkEmbedding
from src.models.chunk_asset import ChunkAsset
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.asset_link_service import link_assets_to_chunk
from src.services.knowledge.chunk_image_assets import ensure_image_assets_for_chunk
from src.services.knowledge.entry_content_service import build_catalog_path
from src.services.knowledge.taxonomy_service import (
    validate_application_type_code,
    validate_block_type_code,
    validate_business_line_codes,
)
from src.services.knowledge.token_counter import count_tokens


class ChunkConflictError(Exception):
    def __init__(self, existing_id: int, existing_version: str):
        self.existing_id = existing_id
        self.existing_version = existing_version
        super().__init__(f"chunk already exists: id={existing_id}, version={existing_version}")


class ChunkNotFoundError(Exception):
    pass


def bump_version(version: str) -> str:
    major, minor = version.split(".", 1)
    return f"{major}.{int(minor) + 1}"


def create_knowledge_chunk(
    db: Session,
    *,
    kb_id: UUID,
    payload: dict,
    doc_id: UUID,
    primary_node_id: UUID | str,
    force: bool = False,
) -> KnowledgeChunk:
    node_key = str(primary_node_id)
    existing = (
        db.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.doc_id == doc_id,
            KnowledgeChunk.primary_node_id == node_key,
            KnowledgeChunk.is_latest.is_(True),
        )
        .one_or_none()
    )
    if existing is not None and not force:
        raise ChunkConflictError(existing.id, existing.version)

    previous_version_id: int | None = None
    version = "1.0"
    if existing is not None:
        existing.is_latest = False
        previous_version_id = existing.id
        version = bump_version(existing.version)
        if _is_sqlite(db):
            # SQLite tests do not support the Postgres partial unique index condition.
            existing.primary_node_id = f"{existing.primary_node_id}#v{existing.version}"

    content = str(payload.get("content") or "")
    block_type_code = validate_block_type_code(
        db, str(payload.get("block_type_code") or "product_solution")
    )
    application_type_code = validate_application_type_code(
        db, str(payload.get("application_type_code") or "preferred_reference")
    )
    business_line_codes = validate_business_line_codes(db, payload.get("business_line_codes"))
    tree_nodes = _load_heading_nodes(db, kb_id=kb_id, doc_id=doc_id)
    nodes_by_id = {node.node_id: node for node in tree_nodes}
    node_uuid = _coerce_uuid(primary_node_id)
    computed_catalog_path = (
        build_catalog_path(nodes_by_id, node_uuid) if node_uuid in nodes_by_id else []
    )
    children_count = sum(1 for node in tree_nodes if node.parent_id == node_uuid)

    chunk = KnowledgeChunk(
        kb_id=kb_id,
        knowledge_code=str(uuid4()),
        version=version,
        previous_version_id=previous_version_id,
        is_latest=True,
        title=str(payload.get("title") or ""),
        content=content,
        summary=payload.get("summary"),
        knowledge_type=str(payload.get("knowledge_type") or ""),
        content_type=str(payload.get("content_type") or "text"),
        doc_id=doc_id,
        file_name=payload.get("file_name"),
        source_type=str(payload.get("source_type") or ""),
        project_name=payload.get("project_name"),
        page_start=payload.get("page_start"),
        page_end=payload.get("page_end"),
        char_start=payload.get("char_start"),
        char_end=payload.get("char_end"),
        catalog_path=payload.get("catalog_path") or computed_catalog_path,
        primary_node_id=node_key,
        parent_id=payload.get("parent_id"),
        need_parent_context=bool(payload.get("need_parent_context", False)),
        block_type_code=block_type_code,
        application_type_code=application_type_code,
        business_line_codes=business_line_codes,
        tags=list(payload.get("tags") or []),
        industries=list(payload.get("industries") or []),
        customer_types=list(payload.get("customer_types") or []),
        regions=list(payload.get("regions") or []),
        issue_date=payload.get("issue_date"),
        expire_date=payload.get("expire_date"),
        status=str(payload.get("status") or "draft"),
        is_template=bool(payload.get("is_template", False)),
        template_type=payload.get("template_type"),
        variables=list(payload.get("variables") or []),
        is_immutable=bool(payload.get("is_immutable", False)),
        exclusion_rules=list(payload.get("exclusion_rules") or []),
        retrieval_weight=payload.get("retrieval_weight", 1.0),
        security_level=str(payload.get("security_level") or "internal"),
        owner=payload.get("owner"),
        review_status=str(payload.get("review_status") or "approved"),
        winning_flag=bool(payload.get("winning_flag", False)),
        edit_distance_avg=payload.get("edit_distance_avg"),
        content_hash=_compute_content_hash(content),
        token_count=count_tokens(content),
        has_children=children_count > 0,
        children_count=children_count,
    )
    if _is_sqlite(db):
        chunk.id = _next_chunk_id(db)
    db.add(chunk)
    db.flush()
    link_assets_to_chunk(
        db,
        kb_id=kb_id,
        doc_id=doc_id,
        chunk_id=chunk.id,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
    )
    ensure_image_assets_for_chunk(db, chunk)
    db.flush()
    return chunk


def delete_knowledge_chunk(db: Session, *, kb_id: UUID, chunk_id: int) -> None:
    chunk = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.id == chunk_id)
        .one_or_none()
    )
    if chunk is None:
        raise ChunkNotFoundError

    chunk_ids = [
        row.id
        for row in db.query(KnowledgeChunk.id)
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.knowledge_code == chunk.knowledge_code,
        )
        .all()
    ]
    if not chunk_ids:
        return

    db.query(ChunkEmbedding).filter(
        ChunkEmbedding.object_type == "chunk",
        ChunkEmbedding.object_id.in_(chunk_ids),
    ).delete(synchronize_session=False)
    db.query(ChunkAsset).filter(ChunkAsset.chunk_id.in_(chunk_ids)).update(
        {ChunkAsset.chunk_id: None},
        synchronize_session=False,
    )
    db.query(KnowledgeChunk).filter(KnowledgeChunk.id.in_(chunk_ids)).delete(
        synchronize_session=False
    )
    db.flush()


def _compute_content_hash(content: str) -> str:
    normalized = (content or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _coerce_uuid(node_id: UUID | str) -> UUID:
    if isinstance(node_id, UUID):
        return node_id
    return UUID(str(node_id))


def _load_heading_nodes(db: Session, *, kb_id: UUID, doc_id: UUID) -> list[DocumentTreeNode]:
    return (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == doc_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .all()
    )


def _is_sqlite(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"


def _next_chunk_id(db: Session) -> int:
    current_max = db.query(func.max(KnowledgeChunk.id)).scalar()
    return int(current_max or 0) + 1

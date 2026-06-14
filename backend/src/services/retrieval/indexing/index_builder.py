from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.models.manual_asset import ManualAsset, ManualAssetStatus
from src.models.retrieval_index_entry import (
    RetrievalIndexEntry,
    RetrievalIndexStatus,
    RetrievalObjectType,
)
from src.models.wiki import Wiki, WikiStatus
from src.services.retrieval.indexing.embedding_client import EmbeddingClient
from src.services.retrieval.title_normalizer import normalize_outline_title


class IndexBuilder:
    def __init__(self, db: Session, embedding_client: EmbeddingClient | None = None) -> None:
        self.db = db
        self.embedding_client = embedding_client or EmbeddingClient()

    def upsert_from_ku(self, ku: KnowledgeUnit) -> RetrievalIndexEntry | None:
        if ku.status != KnowledgeUnitStatus.published or not ku.searchable:
            return self.deprecate_entry(
                kb_id=ku.kb_id,
                object_type=RetrievalObjectType.ku,
                object_id=ku.ku_id,
            )
        return self._upsert_entry(
            kb_id=ku.kb_id,
            object_type=RetrievalObjectType.ku,
            object_id=ku.ku_id,
            title=ku.title,
            content_text=ku.summary or ku.content,
            product_category_ids=ku.product_category_ids or [],
            chapter_taxonomy_id=ku.chapter_taxonomy_id,
            knowledge_type=ku.knowledge_type,
            import_id=ku.import_id,
            source_doc_id=ku.source_doc_id,
            source_node_id=ku.source_node_id,
            bid_outline_id=ku.bid_outline_id,
            template_library_id=ku.template_library_id,
        )

    def upsert_from_wiki(self, wiki: Wiki) -> RetrievalIndexEntry | None:
        if wiki.status != WikiStatus.published or not wiki.searchable:
            return self.deprecate_entry(
                kb_id=wiki.kb_id,
                object_type=RetrievalObjectType.wiki,
                object_id=wiki.wiki_id,
            )
        return self._upsert_entry(
            kb_id=wiki.kb_id,
            object_type=RetrievalObjectType.wiki,
            object_id=wiki.wiki_id,
            title=wiki.title,
            content_text=wiki.summary or wiki.content,
            product_category_ids=wiki.product_category_ids or [],
            chapter_taxonomy_id=wiki.chapter_taxonomy_id,
            knowledge_type=wiki.wiki_type,
            import_id=wiki.import_id,
            source_doc_id=wiki.source_doc_id,
            source_node_id=wiki.source_node_id,
        )

    def upsert_from_manual_asset(self, asset: ManualAsset) -> RetrievalIndexEntry | None:
        if asset.status != ManualAssetStatus.published or not asset.searchable:
            return self.deprecate_entry(
                kb_id=asset.kb_id,
                object_type=RetrievalObjectType.manual_asset,
                object_id=asset.manual_asset_id,
            )
        return self._upsert_entry(
            kb_id=asset.kb_id,
            object_type=RetrievalObjectType.manual_asset,
            object_id=asset.manual_asset_id,
            title=asset.title,
            content_text=asset.summary or asset.content or "",
            product_category_ids=asset.product_category_ids or [],
            file_purpose=asset.asset_type,
            import_id=asset.import_id,
            source_doc_id=asset.source_doc_id,
        )

    def deprecate_entry(
        self,
        *,
        kb_id: UUID,
        object_type: RetrievalObjectType,
        object_id: UUID,
    ) -> RetrievalIndexEntry | None:
        row = (
            self.db.query(RetrievalIndexEntry)
            .filter(RetrievalIndexEntry.kb_id == kb_id)
            .filter(RetrievalIndexEntry.object_type == object_type)
            .filter(RetrievalIndexEntry.object_id == object_id)
            .one_or_none()
        )
        if row is None:
            return None
        row.status = RetrievalIndexStatus.deprecated
        row.updated_at = datetime.now(timezone.utc)
        row.indexed_at = datetime.now(timezone.utc)
        self.db.flush()
        return row

    def _upsert_entry(
        self,
        *,
        kb_id: UUID,
        object_type: RetrievalObjectType,
        object_id: UUID,
        title: str,
        content_text: str,
        product_category_ids: list,
        chapter_taxonomy_id: UUID | None = None,
        knowledge_type: str | None = None,
        file_purpose: str | None = None,
        import_id: UUID | None = None,
        source_doc_id: UUID | None = None,
        source_node_id: UUID | None = None,
        bid_outline_id: UUID | None = None,
        template_library_id: UUID | None = None,
    ) -> RetrievalIndexEntry:
        row = (
            self.db.query(RetrievalIndexEntry)
            .filter(RetrievalIndexEntry.kb_id == kb_id)
            .filter(RetrievalIndexEntry.object_type == object_type)
            .filter(RetrievalIndexEntry.object_id == object_id)
            .one_or_none()
        )
        if row is None:
            row = RetrievalIndexEntry(
                kb_id=kb_id,
                object_type=object_type,
                object_id=object_id,
            )
            self.db.add(row)
        combined_text = f"{title}\n{content_text}".strip()
        embedding_result = self.embedding_client.embed_text(combined_text)
        row.title = normalize_outline_title(title)
        row.content_text = content_text
        row.product_category_ids = product_category_ids
        row.chapter_taxonomy_id = chapter_taxonomy_id
        row.knowledge_type = knowledge_type
        row.file_purpose = file_purpose
        row.import_id = import_id
        row.source_doc_id = source_doc_id
        row.source_node_id = source_node_id
        row.bid_outline_id = bid_outline_id
        row.template_library_id = template_library_id
        row.status = RetrievalIndexStatus.published
        row.indexed_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        row.meta = {
            "vector_disabled_reason": embedding_result.disabled_reason,
        }
        row.embedding = embedding_result.vector
        self.db.flush()
        return row

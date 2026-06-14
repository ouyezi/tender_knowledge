from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.manual_asset import ManualAsset

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/manual-assets",
    tags=["manual-assets"],
)


@router.get("")
def list_manual_assets(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(ManualAsset).filter(ManualAsset.kb_id == kb_id)
    total = q.count()
    rows = q.order_by(ManualAsset.updated_at.desc()).offset(offset).limit(page_size).all()
    return success(
        {
            "items": [
                {
                    "manual_asset_id": str(row.manual_asset_id),
                    "title": row.title,
                    "summary": row.summary,
                    "content": row.content,
                    "asset_type": row.asset_type,
                    "storage_path": row.storage_path,
                    "product_category_ids": row.product_category_ids,
                    "import_id": str(row.import_id),
                    "candidate_id": str(row.candidate_id),
                    "source_doc_id": str(row.source_doc_id) if row.source_doc_id else None,
                    "searchable": row.searchable,
                    "status": row.status.value,
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/{manual_asset_id}")
def get_manual_asset(
    kb_id: UUID,
    manual_asset_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(ManualAsset)
        .filter(ManualAsset.kb_id == kb_id)
        .filter(ManualAsset.manual_asset_id == manual_asset_id)
        .one_or_none()
    )
    if row is None:
        return success(None, trace_id=get_trace_id())
    return success(
        {
            "manual_asset_id": str(row.manual_asset_id),
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "asset_type": row.asset_type,
            "storage_path": row.storage_path,
            "product_category_ids": row.product_category_ids,
            "import_id": str(row.import_id),
            "candidate_id": str(row.candidate_id),
            "source_doc_id": str(row.source_doc_id) if row.source_doc_id else None,
            "searchable": row.searchable,
            "status": row.status.value,
        },
        trace_id=get_trace_id(),
    )

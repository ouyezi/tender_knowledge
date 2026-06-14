from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.manual_asset import ManualAsset, ManualAssetStatus


def publish(
    db: Session,
    *,
    kb_id: UUID,
    view,
    payload: dict,
    operator_id: str,
) -> dict:
    row = ManualAsset(
        kb_id=kb_id,
        title=payload.get("title") or view.title,
        summary=payload.get("summary", view.summary),
        content=payload.get("content") or view.content,
        asset_type=payload.get("asset_type"),
        storage_path=payload.get("storage_path"),
        product_category_ids=[
            str(item)
            for item in (
                payload.get("product_category_ids")
                or view.suggested_product_category_ids
                or []
            )
        ],
        import_id=UUID(view.source_trace["import_id"]),
        candidate_id=view.raw_id,
        source_doc_id=UUID(view.source_trace["source_doc_id"])
        if view.source_trace.get("source_doc_id")
        else None,
        searchable=payload.get("searchable", True),
        status=ManualAssetStatus.published,
        published_at=datetime.now(timezone.utc),
        published_by=operator_id,
    )
    db.add(row)
    db.flush()
    return {
        "confirmed_object_type": "manual_asset",
        "confirmed_object_id": row.manual_asset_id,
        "status": "published",
    }

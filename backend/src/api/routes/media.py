from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.config import Settings
from src.db.session import get_db
from src.models.document_media_asset import DocumentMediaAsset
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/v1/kbs/{kb_id}/media", tags=["media"])


@router.get("/{asset_id}")
def get_media_asset(
    kb_id: UUID,
    asset_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(DocumentMediaAsset)
        .filter(DocumentMediaAsset.kb_id == kb_id)
        .filter(DocumentMediaAsset.asset_id == asset_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="media asset not found")
    abs_path = Path(Settings().storage_root) / row.storage_path
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="media file missing")
    return FileResponse(abs_path, media_type=row.mime_type)

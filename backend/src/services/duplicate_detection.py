from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.file_import import FileImport


def find_duplicates_by_hash(
    db: Session,
    *,
    kb_id: UUID,
    file_hash: str,
    exclude_import_id: UUID | None = None,
) -> list[FileImport]:
    query = db.query(FileImport).filter(
        FileImport.kb_id == kb_id,
        FileImport.file_hash == file_hash,
    )
    if exclude_import_id is not None:
        query = query.filter(FileImport.import_id != exclude_import_id)
    return query.order_by(FileImport.created_at.asc()).all()

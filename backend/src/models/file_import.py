import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class FileType(str, enum.Enum):
    docx = "docx"
    pdf = "pdf"
    ppt = "ppt"
    xlsx = "xlsx"
    image = "image"
    other = "other"


class FilePurpose(str, enum.Enum):
    actual_bid = "actual_bid"
    template_file = "template_file"
    qualification = "qualification"
    ppt_material = "ppt_material"
    cover_guide = "cover_guide"
    writing_guide = "writing_guide"
    wiki_source = "wiki_source"
    other = "other"


class FileImportStatus(str, enum.Enum):
    uploaded = "uploaded"
    need_confirm = "need_confirm"
    confirmed = "confirmed"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    ignored = "ignored"


class HashStatus(str, enum.Enum):
    computed = "computed"
    unavailable = "unavailable"
    failed = "failed"


class TargetObjectType(str, enum.Enum):
    document = "document"
    template_material = "template_material"
    manual_asset = "manual_asset"
    wiki = "wiki"
    ignored = "ignored"


class DuplicateResolution(str, enum.Enum):
    skip = "skip"
    new_version = "new_version"
    normal = "normal"


class FileImport(Base):
    __tablename__ = "file_imports"
    __table_args__ = (
        Index(
            "uq_file_imports_kb_hash",
            "kb_id",
            "file_hash",
            unique=True,
            postgresql_where=text("file_hash IS NOT NULL"),
            sqlite_where=text("file_hash IS NOT NULL"),
        ),
        Index("ix_file_imports_kb_status_created", "kb_id", "status", "created_at"),
        Index("ix_file_imports_kb_name_size", "kb_id", "file_name", "file_size"),
    )

    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash_status: Mapped[HashStatus] = mapped_column(
        Enum(HashStatus), nullable=False, default=HashStatus.unavailable
    )
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_purpose: Mapped[FilePurpose | None] = mapped_column(Enum(FilePurpose), nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    target_object_type: Mapped[TargetObjectType | None] = mapped_column(
        Enum(TargetObjectType), nullable=True
    )
    enter_parsing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[FileImportStatus] = mapped_column(
        Enum(FileImportStatus), nullable=False, default=FileImportStatus.uploaded
    )
    parent_import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duplicate_resolution: Mapped[DuplicateResolution | None] = mapped_column(
        Enum(DuplicateResolution), nullable=True
    )
    confirmed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

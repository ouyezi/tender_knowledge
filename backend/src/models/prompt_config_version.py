import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class PromptConfigVersion(Base):
    __tablename__ = "prompt_config_versions"

    prompt_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    template_system: Mapped[str] = mapped_column(Text, nullable=False)
    template_user: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

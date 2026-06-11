from pathlib import Path
from uuid import UUID

from src.config import Settings


class FileStorage:
    def __init__(self) -> None:
        cfg = Settings()
        self.root = Path(cfg.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        kb_id: UUID,
        import_id: UUID,
        file_name: str,
        stream,
    ) -> str:
        rel = f"{kb_id}/{import_id}/{file_name}"
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in stream:
                f.write(chunk)
        return rel

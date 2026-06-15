from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from src.config import Settings


def workspace_path_for_task(
    *,
    storage_root: Path,
    kb_id: UUID,
    import_id: UUID,
    parse_task_id: UUID,
) -> Path:
    return storage_root / "doc_chunk_workspaces" / str(kb_id) / str(import_id) / str(parse_task_id)


def ensure_workspace(path: Path, *, overwrite: bool = True) -> Path:
    if overwrite and path.exists():
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_workspace(path: Path, *, on_success: bool) -> None:
    settings = Settings()
    if not path.exists():
        return
    if on_success and not settings.doc_chunk_workspace_retention_on_success:
        shutil.rmtree(path, ignore_errors=True)
        return
    if not on_success and settings.doc_chunk_workspace_retention_hours <= 0:
        shutil.rmtree(path, ignore_errors=True)

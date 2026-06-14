from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.db.session import Base, get_db
from src.main import app
from src.models.knowledge_base import KBStatus, KnowledgeBase


def run_integration_pipeline(cfg, *, storage_root: Path | None = None, monkeypatch_chapter_rules=None) -> int:
    from uuid import uuid4

    from e2e.client import IntegrationClient
    from e2e.logger import JsonlRunLogger
    from e2e.runner import E2EPipelineRunner, default_log_file

    if storage_root is not None:
        os.environ["STORAGE_ROOT"] = str(storage_root)

    test_db_url = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite://")
    sqlite_kwargs = {}
    if test_db_url.startswith("sqlite"):
        sqlite_kwargs = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    engine = create_engine(test_db_url, **sqlite_kwargs)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    session = Session()
    kb = KnowledgeBase(name=f"e2e-{uuid4().hex[:8]}", status=KBStatus.active)
    session.add(kb)
    session.commit()
    session.refresh(kb)
    cfg.kb_id = str(kb.kb_id)

    if monkeypatch_chapter_rules is not None:
        from src.services import chapter_candidate_rules

        monkeypatch_chapter_rules(chapter_candidate_rules)

    log_file = cfg.log_file or default_log_file(cfg)
    logger = JsonlRunLogger(
        log_file=log_file,
        run_id=str(uuid4()),
        purpose=cfg.purpose,
        mode=cfg.mode,
    )

    try:
        with TestClient(app) as client:
            api = IntegrationClient(client, operator_id=cfg.operator_id)
            runner = E2EPipelineRunner(cfg, api, logger, db_session=session)
            return runner.run()
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=engine)

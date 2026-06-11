import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.session import Base, get_db
from src.main import app
from src.models import (  # noqa: F401
    audit_log,
    chapter_taxonomy,
    classification_reference,
    kb_clone_log,
    knowledge_base,
    product_category,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite://")


@pytest.fixture()
def db_engine():
    sqlite_kwargs = {}
    if TEST_DATABASE_URL.startswith("sqlite"):
        sqlite_kwargs = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    engine = create_engine(TEST_DATABASE_URL, **sqlite_kwargs)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(db_engine):
    Base.metadata.create_all(bind=db_engine)
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

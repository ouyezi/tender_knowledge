import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import kb_clone_log, knowledge_base  # noqa: F401

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

from src.db.init_db import init_db


def test_init_db_runs_without_error():
    init_db()

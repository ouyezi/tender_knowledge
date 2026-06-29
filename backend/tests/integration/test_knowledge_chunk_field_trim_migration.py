from sqlalchemy import inspect


def test_knowledge_chunks_schema_after_qualification_info(db_session):
    cols = {c["name"] for c in inspect(db_session.bind).get_columns("knowledge_chunks")}
    assert "qualification_info" in cols
    assert "certificate_number" not in cols
    assert "certificate_date" not in cols
    assert "expire_date" in cols
    assert "char_start" in cols
    assert "char_end" in cols
    assert "page_start" not in cols
    assert "issue_date" not in cols
    assert "variables" not in cols
    assert "winning_flag" not in cols
    assert "source_type" not in cols
    assert "industries" not in cols
    assert "retrieval_weight" not in cols

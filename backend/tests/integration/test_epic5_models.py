from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace, RetrievalTraceStatus


def test_create_retrieval_trace(db_session, seeded_kb):
    trace = RetrievalTrace(
        kb_id=seeded_kb.kb_id,
        intent=RetrievalIntent.knowledge_lookup,
        request_snapshot={"query": "技术方案"},
        stages={"recall": {"count": 0}},
        status=RetrievalTraceStatus.success,
    )
    db_session.add(trace)
    db_session.commit()
    assert trace.trace_id is not None

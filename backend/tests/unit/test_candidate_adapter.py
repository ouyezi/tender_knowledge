import pytest
from uuid import uuid4

from src.models.candidate_knowledge import CandidateKnowledgeStatus
from src.models.candidate_knowledge_stub import CandidateKnowledgeStubStatus
from src.services.candidate_adapter import (
    CandidateNotEditableError,
    assert_editable_document,
    assert_editable_stub,
    format_candidate_id,
    parse_candidate_id,
)


def test_parse_candidate_id_doc_prefix():
    raw = uuid4()
    channel, cid = parse_candidate_id(f"doc_{raw}")
    assert channel == "document"
    assert cid == raw


def test_parse_candidate_id_tpl_prefix():
    raw = uuid4()
    channel, cid = parse_candidate_id(f"tpl_{raw}")
    assert channel == "template"
    assert cid == raw


def test_format_candidate_id_roundtrip():
    raw = uuid4()
    assert parse_candidate_id(format_candidate_id("document", raw)) == ("document", raw)


def test_assert_editable_rejects_published_document():
    with pytest.raises(CandidateNotEditableError):
        assert_editable_document(CandidateKnowledgeStatus.published)


def test_assert_editable_rejects_published_stub():
    with pytest.raises(CandidateNotEditableError):
        assert_editable_stub(CandidateKnowledgeStubStatus.published)


def test_parse_invalid_candidate_id():
    with pytest.raises(ValueError):
        parse_candidate_id(str(uuid4()))

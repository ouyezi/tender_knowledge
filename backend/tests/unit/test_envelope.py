from src.api.envelope import error, success
import uuid


def test_success_envelope_has_trace_id():
    tid = uuid.uuid4()
    body = success({"id": "1"}, trace_id=tid)
    assert body["data"] == {"id": "1"}
    assert body["trace_id"] == str(tid)


def test_error_envelope():
    tid = uuid.uuid4()
    body = error("CONFLICT", "duplicate", trace_id=tid, details={"field": "alias"})
    assert body["error"]["code"] == "CONFLICT"
    assert body["trace_id"] == str(tid)

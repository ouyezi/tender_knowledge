from __future__ import annotations

import uuid
from typing import Any


def new_trace_id() -> uuid.UUID:
    return uuid.uuid4()


def success(data: Any, trace_id: uuid.UUID | None = None) -> dict[str, Any]:
    tid = trace_id or new_trace_id()
    return {"data": data, "trace_id": str(tid)}


def error(
    code: str,
    message: str,
    trace_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tid = trace_id or new_trace_id()
    payload: dict[str, Any] = {
        "error": {"code": code, "message": message},
        "trace_id": str(tid),
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload

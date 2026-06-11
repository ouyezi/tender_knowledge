from __future__ import annotations

import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

trace_id_ctx: ContextVar[uuid.UUID | None] = ContextVar("trace_id", default=None)
operator_id_ctx: ContextVar[str | None] = ContextVar("operator_id", default=None)


def get_trace_id() -> uuid.UUID | None:
    return trace_id_ctx.get()


def get_operator_id() -> str | None:
    return operator_id_ctx.get()


def set_operator_id(operator_id: str | None) -> None:
    operator_id_ctx.set(operator_id)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        raw_trace_id = request.headers.get("X-Trace-Id")
        try:
            trace_id = uuid.UUID(raw_trace_id) if raw_trace_id else uuid.uuid4()
        except ValueError:
            trace_id = uuid.uuid4()

        trace_token = trace_id_ctx.set(trace_id)
        operator_token = operator_id_ctx.set(request.headers.get("X-Operator-Id"))

        try:
            response: Response = await call_next(request)
        finally:
            trace_id_ctx.reset(trace_token)
            operator_id_ctx.reset(operator_token)

        response.headers["X-Trace-Id"] = str(trace_id)
        return response

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from typing import Any, Protocol
from uuid import uuid4

from e2e.types import ApiResponse


class ApiClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, tuple[str, Any, str]] | None = None,
        form_data: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse: ...


def excerpt(text: str, limit: int = 2048) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def http_meta(method: str, path: str, resp: ApiResponse) -> dict[str, Any]:
    return {
        "method": method,
        "path": path,
        "status_code": resp.status_code,
        "response_excerpt": excerpt(resp.raw_text),
    }


class LiveClient:
    def __init__(self, *, base_url: str, operator_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.operator_id = operator_id

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, tuple[str, Any, str]] | None = None,
        form_data: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse:
        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        headers = {"X-Operator-Id": self.operator_id}
        data: bytes | None = None

        if files is not None:
            body, content_type = _encode_multipart(files, form_data or {})
            data = body
            headers["Content-Type"] = content_type
        elif json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    payload = {}
                return ApiResponse(status_code=resp.status, json=payload, raw_text=raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {}
            return ApiResponse(status_code=exc.code, json=payload, raw_text=raw)


class IntegrationClient:
    def __init__(self, test_client, *, operator_id: str) -> None:
        self._client = test_client
        self.operator_id = operator_id

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, tuple[str, Any, str]] | None = None,
        form_data: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse:
        headers = {"X-Operator-Id": self.operator_id}
        kwargs: dict[str, Any] = {"headers": headers}
        if params:
            kwargs["params"] = params
        if json_body is not None:
            kwargs["json"] = json_body
        if form_data:
            kwargs["data"] = form_data
        if files is not None:
            kwargs["files"] = files
        resp = self._client.request(method, path, **kwargs)
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        return ApiResponse(status_code=resp.status_code, json=payload, raw_text=resp.text)


def _encode_multipart(
    files: dict[str, tuple[str, Any, str]],
    form_data: dict[str, str],
) -> tuple[bytes, str]:
    boundary = f"----e2e-{uuid4().hex}"
    body = BytesIO()
    for name, value in form_data.items():
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")
        body.write(part)
    for name, (filename, file_obj, content_type) in files.items():
        payload = file_obj.read() if hasattr(file_obj, "read") else file_obj
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        body.write(part)
        body.write(payload if isinstance(payload, bytes) else str(payload).encode())
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Purpose = Literal["actual_bid", "template_file"]
RunMode = Literal["live", "integration"]
DuplicateAction = Literal["normal", "new_version"]
FromStep = Literal["auto", "upload", "confirm", "parse", "candidates", "publish", "retrieval"]
StopAfter = Literal["candidates", "publish", "retrieval"]


@dataclass
class PipelineConfig:
    purpose: Purpose
    kb_id: str
    file_path: Path
    mode: RunMode = "live"
    auto_publish_count: int = 1
    poll_max_seconds: int = 600
    poll_interval_seconds: float = 5.0
    keep_services: bool = False
    log_file: Path | None = None
    operator_id: str = "admin"
    base_url: str = "http://127.0.0.1:8000"
    resume_import_id: str | None = None
    duplicate_action: DuplicateAction = "normal"
    parent_import_id: str | None = None
    from_step: FromStep = "auto"
    stop_after: StopAfter = "retrieval"


@dataclass
class ApiResponse:
    status_code: int
    json: dict[str, Any]
    raw_text: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def data(self) -> dict[str, Any]:
        payload = self.json.get("data")
        return payload if isinstance(payload, dict) else {}


@dataclass
class StepResult:
    step: str
    ok: bool
    duration_ms: int
    context_patch: dict[str, Any] = field(default_factory=dict)
    http: dict[str, Any] | None = None
    assertion: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    status: str = "ok"


@dataclass
class RunContext:
    kb_id: str
    import_id: str | None = None
    document_id: str | None = None
    parse_task_id: str | None = None
    bid_outline_id: str | None = None
    template_id: str | None = None
    candidate_ids: list[str] = field(default_factory=list)
    published_object_ids: list[str] = field(default_factory=list)
    published_titles: list[str] = field(default_factory=list)
    retrieval_trace_ids: list[str] = field(default_factory=list)
    query_used: str | None = None
    taxonomy_id: str | None = None
    category_id: str | None = None

    def merge(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(self, key):
                continue
            current = getattr(self, key)
            if isinstance(current, list) and isinstance(value, list):
                setattr(self, key, [*current, *value])
            else:
                setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kb_id": self.kb_id,
            "import_id": self.import_id,
            "document_id": self.document_id,
            "parse_task_id": self.parse_task_id,
            "bid_outline_id": self.bid_outline_id,
            "template_id": self.template_id,
            "candidate_ids": self.candidate_ids,
            "published_object_ids": self.published_object_ids,
            "published_titles": self.published_titles,
            "retrieval_trace_ids": self.retrieval_trace_ids,
            "query_used": self.query_used,
            "taxonomy_id": self.taxonomy_id,
            "category_id": self.category_id,
        }

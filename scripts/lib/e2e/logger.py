from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from e2e.types import RunContext, StepResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JsonlRunLogger:
    def __init__(self, *, log_file: Path, run_id: str, purpose: str, mode: str) -> None:
        self.log_file = log_file
        self.run_id = run_id
        self.purpose = purpose
        self.mode = mode
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._context: dict[str, Any] = {}

    def update_context(self, patch: dict[str, Any]) -> None:
        self._context.update({k: v for k, v in patch.items() if v is not None})

    def log_step(self, result: StepResult, *, context: RunContext | None = None) -> None:
        if context is not None:
            self.update_context(context.to_dict())
        if result.context_patch:
            self.update_context(result.context_patch)
        status = "failed" if not result.ok else result.status
        event: dict[str, Any] = {
            "ts": _utc_now(),
            "run_id": self.run_id,
            "step": result.step,
            "status": status,
            "duration_ms": result.duration_ms,
            "purpose": self.purpose,
            "mode": self.mode,
            "context": dict(self._context),
        }
        if result.http:
            event["http"] = result.http
        if result.assertion:
            event["assertion"] = result.assertion
        if result.error:
            event["error"] = result.error
        self._append(event)
        label = "FAILED" if not result.ok else status.upper()
        print(f"[{result.step}] {label} ({result.duration_ms}ms)")

    def log_exception(self, step: str, exc: BaseException, *, duration_ms: int = 0) -> None:
        self.log_step(
            StepResult(
                step=step,
                ok=False,
                duration_ms=duration_ms,
                status="failed",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
        )

    def log_summary(
        self,
        *,
        steps_total: int,
        steps_passed: int,
        steps_failed: int,
        failed_step: str | None,
        exit_code: int,
    ) -> None:
        event = {
            "ts": _utc_now(),
            "run_id": self.run_id,
            "step": "run_summary",
            "status": "ok" if exit_code == 0 else "failed",
            "purpose": self.purpose,
            "mode": self.mode,
            "steps_total": steps_total,
            "steps_passed": steps_passed,
            "steps_failed": steps_failed,
            "failed_step": failed_step,
            "log_file": str(self.log_file),
            "exit_code": exit_code,
        }
        self._append(event)

    def _append(self, event: dict[str, Any]) -> None:
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

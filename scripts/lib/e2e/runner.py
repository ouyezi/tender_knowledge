from __future__ import annotations

import os
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable
from uuid import uuid4

from e2e.client import ApiClient
from e2e.fallback import run_actual_bid_fallback, run_template_fallback
from e2e.logger import JsonlRunLogger
from e2e.resume import detect_from_step
from e2e.pipeline_sections import (
    SECTION_CANDIDATES,
    SECTION_CONFIRM,
    SECTION_PARSE,
    SECTION_PUBLISH,
    SECTION_RETRIEVAL,
    SECTION_UPLOAD,
    clamp_from_step,
    section_in_range,
    start_section,
    stop_section,
)
from e2e.steps import actual_bid, common, template_file
from e2e.types import PipelineConfig, RunContext, StepResult, StopAfter

ROOT = Path(__file__).resolve().parents[3]


class E2EPipelineRunner:
    def __init__(
        self,
        cfg: PipelineConfig,
        api: ApiClient,
        logger: JsonlRunLogger,
        *,
        db_session=None,
    ) -> None:
        self.cfg = cfg
        self.api = api
        self.logger = logger
        self.db_session = db_session
        self.ctx = RunContext(kb_id=cfg.kb_id)
        self._steps_total = 0
        self._steps_passed = 0
        self._failed_step: str | None = None

    def run(self) -> int:
        err = self._validate_config()
        if err:
            print(f"[config] FAILED: {err}")
            return 2

        if self.cfg.mode == "live":
            if not self._run_step(self._bootstrap_services):
                return self._finish(exit_code=2)
        if not self._run_step(lambda: common.step_preflight(self.api, self.cfg, self.ctx)):
            return self._finish(exit_code=2)

        if self.cfg.resume_import_id:
            self.ctx.import_id = self.cfg.resume_import_id

        if self.cfg.from_step == "auto" and self.ctx.import_id:
            resolved = detect_from_step(self.api, self.cfg, self.ctx)
            resolved = clamp_from_step(resolved, self._effective_stop_after())
            self.cfg = replace(self.cfg, from_step=resolved)
            print(f"[resume] auto from-step -> {resolved}")

        pipeline = self._build_pipeline()
        for step_fn in pipeline:
            if not self._run_step(step_fn):
                return self._finish(exit_code=1)
        return self._finish(exit_code=0)

    def _effective_stop_after(self) -> StopAfter:
        if self.cfg.auto_publish_count <= 0:
            return "candidates"
        return self.cfg.stop_after

    def _validate_config(self) -> str | None:
        start = start_section(self.cfg.from_step)
        if start > SECTION_UPLOAD and not self.cfg.resume_import_id:
            return f"--from-step {self.cfg.from_step} requires --import-id"
        if self.cfg.duplicate_action == "new_version" and not self.cfg.parent_import_id:
            return "--duplicate-action new_version requires --parent-import-id"
        if self.cfg.auto_publish_count < 0:
            return "--auto-publish-count must be >= 0"
        if start > stop_section(self._effective_stop_after()):
            return (
                f"--from-step {self.cfg.from_step} is after "
                f"--stop-after {self._effective_stop_after()}"
            )
        return None

    def _build_pipeline(self) -> list[Callable[[], StepResult]]:
        fs = self.cfg.from_step
        stop = self._effective_stop_after()
        pipeline: list[Callable[[], StepResult]] = []

        if not self.cfg.resume_import_id and section_in_range(fs, stop, SECTION_UPLOAD):
            pipeline.extend(
                [
                    lambda: common.step_upload(self.api, self.cfg, self.ctx),
                    self._after_upload,
                ]
            )
        if self.cfg.mode == "live" and section_in_range(fs, stop, SECTION_CONFIRM):
            pipeline.append(lambda: common.step_wait_need_confirm(self.api, self.cfg, self.ctx))
        if section_in_range(fs, stop, SECTION_CONFIRM):
            pipeline.append(lambda: common.step_confirm_import(self.api, self.cfg, self.ctx))

        if start_section(fs) >= SECTION_PARSE and self.ctx.import_id:
            pipeline.append(lambda: common.step_load_import_context(self.api, self.cfg, self.ctx))

        if section_in_range(fs, stop, SECTION_PARSE):
            if self.cfg.purpose == "actual_bid":
                pipeline.extend(self._actual_bid_steps())
            else:
                pipeline.extend(self._template_steps())

        if section_in_range(fs, stop, SECTION_CANDIDATES):
            pipeline.append(self._ensure_candidates)
            pipeline.append(lambda: common.step_list_candidates(self.api, self.cfg, self.ctx))
        if section_in_range(fs, stop, SECTION_PUBLISH):
            pipeline.append(lambda: common.step_auto_publish(self.api, self.cfg, self.ctx))
        if section_in_range(fs, stop, SECTION_RETRIEVAL):
            pipeline.extend(
                [
                    lambda: common.step_retrieval_dynamic(self.api, self.cfg, self.ctx),
                    lambda: common.step_retrieval_smoke(self.api, self.cfg, self.ctx),
                ]
            )
        return pipeline

    def _actual_bid_steps(self) -> list[Callable[[], StepResult]]:
        steps: list[Callable[[], StepResult]] = [
            lambda: actual_bid.step_parse_trigger(self.api, self.cfg, self.ctx),
        ]
        if self.db_session is not None:
            steps.append(self._sync_actual_bid_parse)
        else:
            steps.append(
                lambda: actual_bid.step_parse_poll(
                    self.api,
                    self.cfg,
                    self.ctx,
                    run_fallback=lambda: run_actual_bid_fallback(self.ctx.import_id or ""),
                )
            )
        steps.extend(
            [
                lambda: actual_bid.step_parse_wizard_confirm(self.api, self.cfg, self.ctx),
            ]
        )
        return steps

    def _template_steps(self) -> list[Callable[[], StepResult]]:
        if self.db_session is not None:
            return [
                self._sync_template_parse,
                lambda: template_file.step_template_parse_poll(self.api, self.cfg, self.ctx),
                lambda: template_file.step_template_parse_confirm(self.api, self.cfg, self.ctx),
            ]
        return [
            lambda: template_file.step_template_parse_trigger(self.api, self.cfg, self.ctx),
            lambda: template_file.step_template_parse_poll(
                self.api,
                self.cfg,
                self.ctx,
                run_fallback=lambda: run_template_fallback(self.ctx.import_id or ""),
            ),
            lambda: template_file.step_template_parse_confirm(self.api, self.cfg, self.ctx),
        ]

    def _sync_actual_bid_parse(self) -> StepResult:
        from src.services.actual_bid_parse_runner import run_actual_bid_parse_pending

        start = time.perf_counter()
        run_actual_bid_parse_pending(self.db_session)
        self.db_session.expire_all()
        if not self.ctx.parse_task_id:
            trigger = actual_bid.step_parse_trigger(self.api, self.cfg, self.ctx)
            if not trigger.ok:
                return StepResult(
                    step="sync_actual_bid_parse",
                    ok=False,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    error=trigger.error,
                )
            run_actual_bid_parse_pending(self.db_session)
            self.db_session.expire_all()
        poll = actual_bid.step_parse_poll(self.api, self.cfg, self.ctx)
        poll.step = "sync_actual_bid_parse"
        return poll

    def _sync_template_parse(self) -> StepResult:
        from src.services.template_parse_runner import run_template_parse_pending

        start = time.perf_counter()
        trigger = template_file.step_template_parse_trigger(self.api, self.cfg, self.ctx)
        if not trigger.ok:
            return StepResult(
                step="sync_template_parse",
                ok=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error=trigger.error,
            )
        run_template_parse_pending(self.db_session)
        self.db_session.expire_all()
        return StepResult(
            step="sync_template_parse",
            ok=True,
            duration_ms=int((time.perf_counter() - start) * 1000),
            context_patch={"parse_task_id": self.ctx.parse_task_id},
        )

    def _after_upload(self) -> StepResult:
        if self.db_session is None or not self.ctx.import_id:
            return StepResult(step="post_upload", ok=True, duration_ms=0, status="skipped")
        from uuid import UUID
        from src.services.import_task_runner import run_post_upload

        start = time.perf_counter()
        run_post_upload(self.db_session, UUID(self.ctx.import_id))
        self.db_session.commit()
        return StepResult(step="post_upload", ok=True, duration_ms=int((time.perf_counter() - start) * 1000))

    def _ensure_candidates(self) -> StepResult:
        list_result = common.step_list_candidates(self.api, self.cfg, self.ctx)
        if list_result.ok:
            return StepResult(
                step="candidate_ensure",
                ok=True,
                duration_ms=0,
                status="skipped",
            )
        if self.db_session is not None:
            result = common.step_candidate_ensure(self.db_session, self.cfg, self.ctx)
        else:
            from src.db.session import SessionLocal

            with SessionLocal() as db:
                result = common.step_candidate_ensure(db, self.cfg, self.ctx)
                db.commit()
        result.step = "candidate_ensure"
        if not result.ok:
            return result
        refresh = common.step_list_candidates(self.api, self.cfg, self.ctx)
        if not refresh.ok:
            refresh.step = "candidate_ensure"
            return refresh
        return StepResult(
            step="candidate_ensure",
            ok=True,
            duration_ms=result.duration_ms,
            context_patch=refresh.context_patch,
        )

    def _bootstrap_services(self) -> StepResult:
        start = time.perf_counter()
        env = {**os.environ, "SKIP_FRONTEND": "1"}
        try:
            subprocess.run(
                ["bash", str(ROOT / "scripts/start.sh")],
                check=True,
                env=env,
                cwd=str(ROOT),
            )
        except subprocess.CalledProcessError as exc:
            return StepResult(
                step="bootstrap_services",
                ok=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error={"type": "BootstrapError", "message": str(exc)},
            )
        return StepResult(step="bootstrap_services", ok=True, duration_ms=int((time.perf_counter() - start) * 1000))

    def _run_step(self, fn: Callable[[], StepResult]) -> bool:
        result = fn()
        self._steps_total += 1
        self.logger.log_step(result, context=self.ctx)
        if result.ok:
            self._steps_passed += 1
            return True
        if self._failed_step is None:
            self._failed_step = result.step
        return False

    def _finish(self, *, exit_code: int) -> int:
        steps_failed = self._steps_total - self._steps_passed
        self.logger.log_summary(
            steps_total=self._steps_total,
            steps_passed=self._steps_passed,
            steps_failed=steps_failed,
            failed_step=self._failed_step,
            exit_code=exit_code,
        )
        return exit_code


def default_log_file(cfg: PipelineConfig) -> Path:
    prefix = "e2e-integration" if cfg.mode == "integration" else "e2e"
    return ROOT / "logs" / f"{prefix}-{uuid4()}.jsonl"

#!/usr/bin/env python3
"""Zhongtie acceptance runner: reset -> kb -> live pipeline -> workbench -> retrieval -> integration."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from e2e.client import LiveClient
from e2e.integration_harness import run_integration_pipeline
from e2e.kb_setup import create_kb_via_api, find_seed_kb_id
from e2e.logger import JsonlRunLogger
from e2e.reset_business_data import reset_business_data
from e2e.runner import E2EPipelineRunner
from e2e.steps import common, retrieval_extended, workbench
from e2e.types import PipelineConfig, RunContext, StepResult

DEFAULT_ZHONGTIE_DOC = Path(
    "/Users/tongqianni/xlab/标书助力/测试招投标文件/标书诊断/中铁/铁建福利商城-标书.docx"
)


class _PhaseRunnerLogger:
    """Proxy logger used by E2EPipelineRunner to inject phase labels."""

    def __init__(self, logger: JsonlRunLogger, *, phase: str) -> None:
        self._logger = logger
        self._phase = phase
        self.steps_total = 0
        self.steps_passed = 0
        self.failed_step: str | None = None

    def log_step(self, result: StepResult, *, context: RunContext | None = None) -> None:
        self._logger.log_step(result, context=context, phase=self._phase)
        self.steps_total += 1
        if result.ok:
            self.steps_passed += 1
        elif self.failed_step is None:
            self.failed_step = result.step

    def log_summary(  # runner requires this method; orchestrator owns final summary.
        self,
        *,
        steps_total: int,
        steps_passed: int,
        steps_failed: int,
        failed_step: str | None,
        exit_code: int,
    ) -> None:
        return None


def _patch_chapter_rules(module) -> None:
    module._CACHE = {
        "default": {"candidate_type": "ku", "suggested_knowledge_type": "solution"},
        "rules": {},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zhongtie E2E acceptance runner")
    parser.add_argument("--file", type=Path, default=DEFAULT_ZHONGTIE_DOC)
    parser.add_argument("--poll-max", type=int, default=7200)
    parser.add_argument("--skip-reset", action="store_true")
    parser.add_argument("--skip-integration", action="store_true")
    parser.add_argument("--skip-workbench", action="store_true")
    parser.add_argument("--keep-services", action="store_true")
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--clone-from-kb-id", default=None)
    parser.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--import-id", default=None, help="Resume live pipeline from existing import")
    parser.add_argument("--kb-id", default=None, help="Reuse existing KB and skip create_kb")
    return parser


def _step_from_exception(step: str, started: float, exc: BaseException) -> StepResult:
    return StepResult(
        step=step,
        ok=False,
        duration_ms=int((time.perf_counter() - started) * 1000),
        error={
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        },
    )


def _run_step(
    logger: JsonlRunLogger,
    fn,
    ctx: RunContext,
    *,
    phase: str,
) -> StepResult:
    result = fn()
    logger.log_step(result, context=ctx, phase=phase)
    return result


def main() -> int:
    args = build_parser().parse_args()
    if not args.import_id and not args.file.exists():
        print(f"file not found: {args.file}")
        return 2

    run_id = str(uuid4())
    log_file = args.log_file or (ROOT / "logs" / f"zhongtie-{run_id}.jsonl")
    logger = JsonlRunLogger(log_file=log_file, run_id=run_id, purpose="actual_bid", mode="live")
    api = LiveClient(base_url=args.base_url, operator_id="admin", upload_timeout=1800)

    steps_total = 0
    steps_passed = 0
    failed_step: str | None = None
    kb_id = args.kb_id
    ctx = RunContext(kb_id=kb_id or "")

    def track(result: StepResult) -> None:
        nonlocal steps_total, steps_passed, failed_step
        steps_total += 1
        if result.ok:
            steps_passed += 1
        elif failed_step is None:
            failed_step = result.step

    def finish(exit_code: int) -> int:
        if not args.keep_services:
            subprocess.run(["bash", str(ROOT / "scripts/stop.sh")], cwd=str(ROOT), check=False)
        logger.log_summary(
            steps_total=steps_total,
            steps_passed=steps_passed,
            steps_failed=steps_total - steps_passed,
            failed_step=failed_step,
            exit_code=exit_code,
        )
        return exit_code

    # Phase 0: reset business data
    if not args.skip_reset and not args.import_id:
        started = time.perf_counter()
        try:
            stats = reset_business_data()
            result = StepResult(
                step="reset_business_data",
                ok=True,
                duration_ms=int((time.perf_counter() - started) * 1000),
                context_patch=stats,
            )
        except Exception as exc:  # pragma: no cover - protective branch for live runner
            result = _step_from_exception("reset_business_data", started, exc)
        logger.log_step(result, context=ctx, phase="phase0")
        track(result)
        if not result.ok:
            return finish(2)

    # Phase 1: create kb (unless --kb-id)
    if not kb_id:
        started = time.perf_counter()
        try:
            from src.db.session import SessionLocal

            with SessionLocal() as db:
                seed_id = find_seed_kb_id(db, explicit=args.clone_from_kb_id)
            create_resp = create_kb_via_api(api, clone_from_kb_id=seed_id)
            if not create_resp.ok:
                result = StepResult(
                    step="create_kb",
                    ok=False,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    http={"method": "POST", "path": "/api/v1/kbs", "status_code": create_resp.status_code},
                    error={"type": "HTTPError", "message": create_resp.raw_text[:500]},
                )
            else:
                kb_id = str(create_resp.data().get("kb_id") or "")
                if not kb_id:
                    result = StepResult(
                        step="create_kb",
                        ok=False,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        error={"type": "ValidationError", "message": "missing kb_id in response"},
                    )
                else:
                    ctx.kb_id = kb_id
                    result = StepResult(
                        step="create_kb",
                        ok=True,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        context_patch={"kb_id": kb_id, "clone_from_kb_id": seed_id},
                    )
        except Exception as exc:  # pragma: no cover - protective branch for live runner
            result = _step_from_exception("create_kb", started, exc)
        logger.log_step(result, context=ctx, phase="phase1")
        track(result)
        if not result.ok:
            return finish(2)

    if not kb_id:
        result = StepResult(
            step="create_kb",
            ok=False,
            duration_ms=0,
            error={"type": "ValidationError", "message": "kb_id unavailable after phase1"},
        )
        logger.log_step(result, context=ctx, phase="phase1")
        track(result)
        return finish(2)

    # Phase 2: live pipeline (stop at candidates)
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id=kb_id,
        file_path=args.file,
        mode="live",
        auto_publish_count=0,
        stop_after="candidates",
        poll_max_seconds=args.poll_max,
        keep_services=True,
        base_url=args.base_url,
        resume_import_id=args.import_id,
    )
    phase2_logger = _PhaseRunnerLogger(logger, phase="phase2")
    runner = E2EPipelineRunner(cfg, api, phase2_logger)
    phase2_exit = runner.run()
    steps_total += phase2_logger.steps_total
    steps_passed += phase2_logger.steps_passed
    if phase2_logger.failed_step and failed_step is None:
        failed_step = phase2_logger.failed_step
    ctx = runner.ctx
    if phase2_exit != 0:
        return finish(phase2_exit)

    # Phase 3: workbench scenarios (continue-on-failure)
    if not args.skip_workbench:
        for step_fn in workbench.WORKBENCH_STEPS:
            result = _run_step(
                logger,
                lambda sf=step_fn: sf(api, cfg, ctx),
                ctx,
                phase="phase3",
            )
            track(result)

    # Phase 4: retrieval checks
    retrieval_steps = [
        common.step_retrieval_dynamic,
        common.step_retrieval_smoke,
        retrieval_extended.step_retrieval_bm25_only,
        retrieval_extended.step_retrieval_category_filter,
        retrieval_extended.step_retrieval_trace,
    ]
    for step_fn in retrieval_steps:
        result = _run_step(
            logger,
            lambda sf=step_fn: sf(api, cfg, ctx),
            ctx,
            phase="phase4",
        )
        track(result)

    # Phase 5: integration regression
    exit_code = 0 if steps_passed == steps_total else 1
    if not args.skip_integration:
        started = time.perf_counter()
        int_cfg = PipelineConfig(
            purpose="actual_bid",
            kb_id="placeholder",
            file_path=ROOT / "backend/tests/fixtures/sample-actual-bid.docx",
            mode="integration",
            poll_max_seconds=30,
            log_file=log_file.with_name(f"{log_file.stem}-integration{log_file.suffix}"),
        )
        int_exit = run_integration_pipeline(int_cfg, monkeypatch_chapter_rules=_patch_chapter_rules)
        result = StepResult(
            step="integration_regression",
            ok=int_exit == 0,
            duration_ms=int((time.perf_counter() - started) * 1000),
            assertion={"exit_code": int_exit},
        )
        logger.log_step(result, context=ctx, phase="phase5")
        track(result)
        if int_exit != 0:
            exit_code = 1

    return finish(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())

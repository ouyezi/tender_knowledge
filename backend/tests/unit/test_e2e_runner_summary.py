import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))

from e2e.logger import JsonlRunLogger
from e2e.runner import E2EPipelineRunner
from e2e.types import PipelineConfig, StepResult


def test_runner_fail_fast_records_failed_step(tmp_path):
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id="kb-1",
        file_path=Path("a.docx"),
        mode="integration",
        log_file=tmp_path / "run.jsonl",
    )
    logger = JsonlRunLogger(
        log_file=cfg.log_file,
        run_id="run-1",
        purpose=cfg.purpose,
        mode=cfg.mode,
    )
    calls = {"n": 0}

    def flaky_step() -> StepResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return StepResult(step="ok_step", ok=True, duration_ms=1)
        return StepResult(step="bad_step", ok=False, duration_ms=1)

    runner = E2EPipelineRunner(cfg, MagicMock(), logger)
    runner._run_step(flaky_step)
    runner._run_step(flaky_step)
    exit_code = runner._finish(exit_code=1)
    assert exit_code == 1
    summary_line = cfg.log_file.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert '"failed_step": "bad_step"' in summary_line

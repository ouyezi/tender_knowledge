import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))

from e2e.logger import JsonlRunLogger
from e2e.types import StepResult


def test_logger_writes_jsonl_and_summary(tmp_path):
    log_path = tmp_path / "run.jsonl"
    logger = JsonlRunLogger(
        log_file=log_path,
        run_id="run-1",
        purpose="actual_bid",
        mode="integration",
    )
    logger.log_step(
        StepResult(step="upload", ok=True, duration_ms=10, context_patch={"import_id": "x"})
    )
    logger.log_summary(steps_total=1, steps_passed=1, steps_failed=0, failed_step=None, exit_code=0)
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["step"] == "upload"
    assert first["status"] == "ok"
    assert first["context"]["import_id"] == "x"
    summary = json.loads(lines[1])
    assert summary["step"] == "run_summary"
    assert summary["exit_code"] == 0

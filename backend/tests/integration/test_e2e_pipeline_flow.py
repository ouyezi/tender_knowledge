import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))
sys.path.insert(0, str(ROOT))

from e2e.types import PipelineConfig


@pytest.fixture()
def sample_actual_bid_path() -> Path:
    path = ROOT / "tests/fixtures/sample-actual-bid.docx"
    if path.exists():
        return path
    return ROOT / "tests/fixtures/sample-template.docx"


@pytest.fixture()
def sample_template_path() -> Path:
    return ROOT / "tests/fixtures/sample-template.docx"


def _patch_chapter_rules(module) -> None:
    module._CACHE = {
        "default": {"candidate_type": "ku", "suggested_knowledge_type": "solution"},
        "rules": {},
    }


def test_e2e_pipeline_integration_actual_bid(tmp_path, sample_actual_bid_path):
    from e2e.integration_harness import run_integration_pipeline

    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id="placeholder",
        file_path=sample_actual_bid_path,
        mode="integration",
        log_file=tmp_path / "actual_bid.jsonl",
        poll_interval_seconds=0.1,
        poll_max_seconds=30,
    )
    exit_code = run_integration_pipeline(
        cfg,
        storage_root=tmp_path / "uploads",
        monkeypatch_chapter_rules=_patch_chapter_rules,
    )
    assert exit_code == 0
    lines = cfg.log_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    summary = __import__("json").loads(lines[-1])
    assert summary["step"] == "run_summary"
    assert summary["exit_code"] == 0


def test_e2e_pipeline_integration_template_file(tmp_path, sample_template_path):
    from e2e.integration_harness import run_integration_pipeline

    cfg = PipelineConfig(
        purpose="template_file",
        kb_id="placeholder",
        file_path=sample_template_path,
        mode="integration",
        log_file=tmp_path / "template.jsonl",
        poll_interval_seconds=0.1,
        poll_max_seconds=30,
    )
    exit_code = run_integration_pipeline(
        cfg,
        storage_root=tmp_path / "uploads",
        monkeypatch_chapter_rules=_patch_chapter_rules,
    )
    assert exit_code == 0


def test_e2e_pipeline_stops_after_candidates(tmp_path, sample_actual_bid_path):
    import json

    from e2e.integration_harness import run_integration_pipeline

    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id="placeholder",
        file_path=sample_actual_bid_path,
        mode="integration",
        log_file=tmp_path / "stop_candidates.jsonl",
        poll_interval_seconds=0.1,
        poll_max_seconds=30,
        stop_after="candidates",
        auto_publish_count=0,
    )
    exit_code = run_integration_pipeline(
        cfg,
        storage_root=tmp_path / "uploads",
        monkeypatch_chapter_rules=_patch_chapter_rules,
    )
    assert exit_code == 0
    steps = [json.loads(line)["step"] for line in cfg.log_file.read_text(encoding="utf-8").strip().splitlines()]
    assert "list_candidates" in steps
    assert "auto_publish" not in steps
    assert "retrieval_dynamic" not in steps

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))

from e2e.types import PipelineConfig, RunContext


def test_run_context_merge():
    ctx = RunContext(kb_id="kb-1")
    ctx.merge(import_id="imp-1", candidate_ids=["c1"])
    assert ctx.import_id == "imp-1"
    assert ctx.candidate_ids == ["c1"]
    d = ctx.to_dict()
    assert d["kb_id"] == "kb-1"


def test_pipeline_config_defaults():
    cfg = PipelineConfig(purpose="actual_bid", kb_id="kb-1", file_path=Path("a.docx"))
    assert cfg.mode == "live"
    assert cfg.auto_publish_count == 1
    assert cfg.poll_max_seconds == 600

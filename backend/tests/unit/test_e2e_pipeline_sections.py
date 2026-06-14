import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))

from e2e.pipeline_sections import (
    SECTION_CANDIDATES,
    SECTION_PARSE,
    SECTION_PUBLISH,
    clamp_from_step,
    includes_section,
    section_in_range,
    start_section,
    stop_section,
)
from e2e.types import PipelineConfig


def test_pipeline_config_resume_options():
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id="kb-1",
        file_path=Path("a.docx"),
        resume_import_id="imp-1",
        duplicate_action="new_version",
        parent_import_id="parent-1",
        from_step="candidates",
    )
    assert cfg.duplicate_action == "new_version"
    assert cfg.from_step == "candidates"
    assert start_section("candidates") == SECTION_CANDIDATES
    assert includes_section("candidates", SECTION_PARSE) is False
    assert includes_section("candidates", SECTION_CANDIDATES) is True
    assert section_in_range("upload", "candidates", SECTION_PUBLISH) is False
    assert section_in_range("upload", "candidates", SECTION_CANDIDATES) is True
    assert clamp_from_step("publish", "candidates") == "candidates"
    assert stop_section("candidates") == SECTION_CANDIDATES

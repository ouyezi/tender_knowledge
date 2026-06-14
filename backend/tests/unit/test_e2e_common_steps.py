import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))
sys.path.insert(0, str(ROOT))

from e2e.client import IntegrationClient
from e2e.steps.common import step_confirm_import, step_preflight, step_upload
from e2e.types import PipelineConfig, RunContext
from src.services.import_task_runner import run_post_upload


def test_preflight_and_upload_confirm(client, seeded_kb, sample_docx_path, db_session):
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id=str(seeded_kb.kb_id),
        file_path=sample_docx_path,
        mode="integration",
    )
    ctx = RunContext(kb_id=cfg.kb_id)
    api = IntegrationClient(client, operator_id="admin")

    assert step_preflight(api, cfg, ctx).ok

    upload = step_upload(api, cfg, ctx)
    assert upload.ok
    assert ctx.import_id
    run_post_upload(db_session, __import__("uuid").UUID(ctx.import_id))
    db_session.commit()

    confirm = step_confirm_import(api, cfg, ctx)
    assert confirm.ok

import json
import shutil
from pathlib import Path
from uuid import uuid4

from src.models.chunk_asset import ChunkAsset
from src.models.document_media_asset import DocumentMediaAsset
from src.services.knowledge_v2.asset_seed_service import seed_chunk_assets_from_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_seed_chunk_assets_from_workspace_images(db_session, seeded_kb, tmp_path):
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE_ROOT, workspace)

    image_asset_id_1 = uuid4()
    image_asset_id_2 = uuid4()
    doc_id = uuid4()

    images_manifest = {
        "schema_version": "1.0",
        "images": [
            {
                "image_ref": "images/fig-1.png",
                "char_start": 12,
                "char_end": 24,
            },
            {
                "image_ref": "images/fig-2.png",
                "anchor": {"char_start": 30, "char_end": 42},
            },
            {
                "image_ref": "images/skip.png",
            },
        ],
    }
    (workspace / "images" / "manifest.json").write_text(
        json.dumps(images_manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    db_session.add_all(
        [
            DocumentMediaAsset(
                asset_id=image_asset_id_1,
                kb_id=seeded_kb.kb_id,
                document_id=doc_id,
                storage_path="kb/media/doc/fig-1.png",
                mime_type="image/png",
            ),
            DocumentMediaAsset(
                asset_id=image_asset_id_2,
                kb_id=seeded_kb.kb_id,
                document_id=doc_id,
                storage_path="kb/media/doc/fig-2.png",
                mime_type="image/png",
            ),
        ]
    )
    db_session.flush()

    count = seed_chunk_assets_from_workspace(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=doc_id,
        workspace_path=workspace,
        image_ref_map={
            "images/fig-1.png": image_asset_id_1,
            "images/fig-2.png": image_asset_id_2,
        },
    )

    assert count == 2
    rows = (
        db_session.query(ChunkAsset)
        .filter(ChunkAsset.kb_id == seeded_kb.kb_id, ChunkAsset.doc_id == doc_id)
        .order_by(ChunkAsset.char_start.asc())
        .all()
    )
    assert len(rows) == 2
    assert rows[0].asset_type == "image"
    assert rows[0].chunk_id is None
    assert rows[0].char_start == 12
    assert rows[0].char_end == 24
    assert rows[0].image_storage_url == "kb/media/doc/fig-1.png"
    assert rows[1].asset_type == "image"
    assert rows[1].char_start == 30
    assert rows[1].char_end == 42
    assert rows[1].image_storage_url == "kb/media/doc/fig-2.png"


def test_seed_chunk_assets_from_workspace_tables(db_session, seeded_kb, tmp_path):
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE_ROOT, workspace)

    chunk_path = workspace / "chunks" / "chunk-0002.json"
    chunk_payload = json.loads(chunk_path.read_text(encoding="utf-8"))
    chunk_payload["blocks"] = list(chunk_payload["blocks"]) + [
        {
            "type": "table",
            "markdown": "|A|B|\n|---|---|\n|1|2|",
        },
        {
            "type": "table",
            "block_index": 3,
            "char_start": 50,
            "char_end": 70,
        },
    ]
    chunk_path.write_text(json.dumps(chunk_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_id = uuid4()
    count = seed_chunk_assets_from_workspace(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=doc_id,
        workspace_path=workspace,
    )

    assert count == 2
    rows = (
        db_session.query(ChunkAsset)
        .filter(
            ChunkAsset.kb_id == seeded_kb.kb_id,
            ChunkAsset.doc_id == doc_id,
            ChunkAsset.asset_type == "table",
        )
        .order_by(ChunkAsset.char_start.asc())
        .all()
    )
    assert len(rows) == 2
    assert rows[0].chunk_id is None
    assert rows[0].char_start == 10
    assert rows[0].char_end == 40
    assert rows[0].raw_markdown == "|A|B|\n|---|---|\n|1|2|"
    assert rows[1].char_start == 50
    assert rows[1].char_end == 70
    assert rows[1].table_schema is not None
    assert rows[1].table_schema.get("layout_type") == "simple"
    assert rows[1].raw_markdown == "|列A|列B|\n|---|---|\n|1|2|"
    assert rows[1].table_summary == "【表格:示例】列A=1; 列B=2"
    assert rows[1].table_headers == ["列A", "列B"]
    assert rows[1].table_rows == [["1", "2"]]

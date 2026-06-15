from pathlib import Path
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.services.doc_chunk.mappers.media_assets import import_media_assets
from src.services.doc_chunk.types import ImportContext

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_import_media_assets_empty_manifest(db_session, seeded_kb):
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=uuid4(),
        source_type=DocumentSourceType.actual_bid,
        document_name="t.docx",
        parse_status=DocumentParseStatus.parsing,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()
    ctx = ImportContext(workspace_path=FIXTURE_ROOT)
    mapping = import_media_assets(db_session, ctx=ctx, document=document, kb_id=seeded_kb.kb_id)
    assert mapping == {}

from uuid import uuid4

from src.services.doc_chunk.outline_store import (
    persist_outline_node_map,
    resolve_outline_node_id,
)


def test_resolve_outline_node_id_reverse_lookup(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    doc_id = uuid4()
    tree_id = uuid4()
    persist_outline_node_map(
        document_id=doc_id,
        outline_node_to_tree_id={"n1": tree_id, "n2": uuid4()},
    )
    assert resolve_outline_node_id(document_id=doc_id, tree_node_id=tree_id) == "n1"
    assert resolve_outline_node_id(document_id=doc_id, tree_node_id=uuid4()) is None

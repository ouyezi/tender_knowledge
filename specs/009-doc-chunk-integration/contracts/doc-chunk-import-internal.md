# Internal Contract: doc_chunk 工作区导入服务

**Version**: 1.0.0  
**Feature**: `009-doc-chunk-integration`  
**Scope**: 后端内部服务（非公开 REST）；供 `actual_bid_parse_runner` 调用

## Module

`src.services.doc_chunk.import_service`

## Entry

```python
def import_workspace(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    document_id: UUID,
    parse_task_id: UUID,
    workspace: Path,
    file_import: FileImport,
    task: ActualBidParseTask,
) -> ImportResult:
    ...
```

## Preconditions

- `workspace/manifest.json` 存在且 `status` ∈ `{success, partial_success}`
- `workspace/document_tree.json`, `outline.json`, `linkage.json`, `chunks/index.json` 存在
- `file_import.file_purpose == actual_bid`
- 调用方已创建 `Document` 记录或 import 内创建

## Processing order

1. **load_workspace** — 解析 JSON，校验 `schema_version: 1.0`
2. **import_media_assets** — `images/manifest.json` → `DocumentMediaAsset`；构建 `image_ref_map`
3. **import_document_tree** — `document_tree.json` → `DocumentTreeNode`；构建 `tree_id_map`
4. **import_bid_outline** — `outline.json` + `linkage` → `BidOutline` / `BidOutlineNode`
5. **classify_headings** — enrich metadata + 可选 `classify_heading_nodes_for_document`
6. **import_candidates** — linkage primary chunks → `CandidateKnowledge`
7. **persist_suggestion** — `document_parse_suggestion` 含质量摘要

## ImportResult

```json
{
  "document_id": "uuid",
  "bid_outline_id": "uuid",
  "tree_node_count": 3451,
  "outline_node_count": 173,
  "candidate_count": 172,
  "parse_engine": "doc_chunk",
  "extract_strategy": "toc",
  "warnings": []
}
```

## blocks_v1 转换

`src.services.doc_chunk.blocks_v1.chunk_blocks_to_content(blocks, image_ref_map) -> str`

| Input block | Output block |
|-------------|--------------|
| paragraph | `{type, text}` |
| table | `{type, text}` |
| image + mapped ref | `{type: image, asset_id, image_ref?}` |
| image + unmapped | `{type: image, fallback: "[image]"}` 或跳过并 warning |

## Errors

| Code | 条件 |
|------|------|
| `DOC_CHUNK_WORKSPACE_INVALID` | 缺少必需文件或 schema 不匹配 |
| `DOC_CHUNK_LINKAGE_INCOMPLETE` | linkage entry 缺 tree id（非 flat_fallback 豁免） |
| `DOC_CHUNK_IMPORT_FAILED` | DB 写入失败 |

失败时 MUST NOT 留下部分 DocumentTree 且无对应 Document 的孤儿数据（与 FR-011 一致）。

## Idempotency

重跑同一 `import_id` + `force_reparse`：调用方先 `_clear_document_tree_for_reparse`（与 legacy 相同），再 import。

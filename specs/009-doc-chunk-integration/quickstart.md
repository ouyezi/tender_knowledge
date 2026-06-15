# Quickstart: 实际标书解析接入 doc_chunk

**Feature**: `009-doc-chunk-integration`

## 前置条件

1. `tender_skills` 已安装且 003 修复通过：

```bash
cd ../tender_skills
pip install -e ".[dev]"
python -m pytest tests/unit tests/contract -q
```

2. `tender_knowledge` 后端依赖包含 doc_chunk（实现后）：

```bash
cd backend
pip install -e ".[dev]"
# pyproject 将含 path 依赖 ../tender_skills
```

3. PostgreSQL 与 `.env` 已配置（与 Epic 3 quickstart 相同）。

4. 环境变量（可选）：

```bash
USE_DOC_CHUNK_PARSE=true          # 默认 true
DOC_CHUNK_SKIP_ENRICH=false
DOC_CHUNK_WORKSPACE_RETENTION_ON_SUCCESS=false
```

---

## 场景 1：doc_chunk 路径解析小型标书

1. 启动 API：`cd backend && uvicorn src.main:app --reload`
2. 通过 Epic 1 流程上传并确认 `file_purpose=actual_bid` 的 docx。
3. 触发解析：`POST /api/v1/kbs/{kb_id}/actual-bid-parse/trigger`
4. 轮询 `GET .../tasks/{parse_task_id}` 直至 `status=ready`。
5. **验证**：
   - `llm_progress.parse_engine == "doc_chunk"`
   - `document_id`、`bid_outline_id` 非空
   - `outline_node_count` 与 `candidate_count` 比例 ∈ [0.8, 1.2]（排除 Preface）

```bash
curl -s "http://localhost:8000/api/v1/kbs/$KB_ID/actual-bid-parse/tasks/$TASK_ID" \
  -H "X-Operator-Id: admin" | jq '.data.llm_progress.parse_engine'
```

---

## 场景 2：确认向导端到端

1. 解析 `ready` 后打开前端：Outline Center → Actual Bid Parse Confirm Wizard。
2. 完成项目名称、产品分类、目录浏览、候选列表步骤并提交。
3. **验证**：无 API 4xx/5xx；Bid Outline 与候选列表条数与任务摘要一致。

---

## 场景 3：legacy 回退

```bash
USE_DOC_CHUNK_PARSE=false uvicorn src.main:app --reload
```

对同一测试文件触发解析。

**验证**：

- `llm_progress.parse_engine == "legacy"` 或字段缺失（实现约定其一并在契约测试固定）
- 既有 `tests/contract/test_actual_bid_parse*.py` 通过

---

## 场景 4：模板路径不受影响

对 `file_purpose=template` 文件触发模板解析。

**验证**：不调用 `doc_chunk_import_service`；模板解析契约测试全绿。

---

## 场景 5：单元测试（实现后）

```bash
cd backend
pytest tests/unit/test_doc_chunk_import*.py -v
pytest tests/contract/test_actual_bid_parse*.py -v
```

Fixture：`tests/fixtures/doc_chunk_workspace_minimal/`（从 tender_skills 导出）。

---

## 场景 6：大型标书（可选，本地）

```bash
export DOC_CHUNK_CANBU_FIXTURE="/path/to/餐补标书.docx"
pytest tests/integration/test_doc_chunk_canbu_parse.py -v
```

**验证**：端到端 < 基线 150%；进度日志持续更新。

---

## 故障排查

| 现象 | 检查 |
|------|------|
| `DOC_CHUNK_WORKSPACE_INVALID` | `{storage_root}/doc_chunk_workspaces/.../manifest.json` |
| 候选无图片 | `image_ref_map` 与 `document_media_assets` |
| 目录条数正常、候选极少 | `USE_DOC_CHUNK_PARSE` 是否为 true；linkage 是否完整 |
| docm 失败 | 应先转换 docx；doc_chunk 不直接读 docm |

---

## 相关文档

- [spec.md](./spec.md)
- [data-model.md](./data-model.md)
- [contracts/doc-chunk-import-internal.md](./contracts/doc-chunk-import-internal.md)
- tender_skills: `docs/superpowers/specs/2026-06-15-doc-chunk-tk-integration-fixes.md`

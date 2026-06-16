# Design: doc_chunk 目录提取依赖同步（tender_skills → tender_knowledge）

**Date**: 2026-06-16  
**Status**: Approved (brainstorming)  
**Related**: `specs/009-doc-chunk-integration/` · `tender_skills` `163db06` · `003-doc-chunk-tk-integration-fixes`  
**Problem**: `tender_skills` 已优化目录提取（含 Word 列表编号还原、003 契约修复），`tender_knowledge` doc_chunk 默认路径需对齐最新依赖并通过 CI + 本地大样例回归

## 1. 背景与目标

### 1.1 现状

| 层 | 状态 |
|----|------|
| tk 解析默认路径 | `use_doc_chunk_parse=true` → `run_doc_chunk_pipeline` → `import_workspace`（009 已合并） |
| tender_skills 003 | `document_tree` ID 唯一、linkage 全覆盖、blocks_v1、enrich 元数据 |
| tender_skills `163db06` | `docx_numbering` 恢复 `numPr`/`chineseCounting` 前缀（如「六、资格证明」） |
| tk legacy 路径 | `walk_document` + `extract_toc_entries` + `outline_heading_filter`（**本次不改动**） |
| tk fixture | `tests/fixtures/doc_chunk_workspace_minimal/` 可能落后于 tender_skills 最新输出 |
| tk 大样例回归 | quickstart 场景 6 已规划，`test_doc_chunk_canbu_import.py` **尚未实现** |

### 1.2 产品目标

1. **依赖对齐**：backend 使用最新已验证 `tender_skills`（目标 commit `163db06` 或联调时 `main` HEAD）。
2. **CI 全绿**：刷新 minimal workspace fixture 后，现有 `test_doc_chunk_*` 与 `test_actual_bid_parse*` 通过。
3. **本地大样例**：餐补/鼎信等真实标书可重复跑 `run_pipeline` → `import_workspace` 端到端（不进 CI）。
4. **最小适配**：`doc_chunk/mappers/*`、`import_service` 仅在测试失败时做最小修复。

### 1.3 不在范围

- legacy 解析路径（`USE_DOC_CHUNK_PARSE=false`）逻辑同步或废弃
- 移植 tender_skills viewer 的 markdown `section_slice` 到 tk
- 前端确认向导、API 契约变更
- `tender_skills` 包内新功能开发
- 检索 / 生成流水线（Epic 5/6）行为变更

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **② 依赖 + fixture + 本地集成测试（推荐）** | 升级依赖、重导 minimal fixture、新增 skip 式 canbu import 测试 | CI 有门禁；大样例可重复、不进 CI | 需维护 fixture 导出步骤 |
| ① 纯依赖 + 手测 | 仅重装依赖与跑 pytest，大样例靠 quickstart 手跑 | 改动最小 | 大样例不可重复；fixture 易漂移 |
| ③ 独立回归脚本 + 指标快照 | 在②上加 `scripts/regression/` 与 JSON 基线 diff | 便于版本对比 | 基线维护成本高，当前过重 |

**决议：方案 ②**

---

## 3. 架构与数据流

数据流保持不变：

```text
docx → docm_converter（如需）
     → run_doc_chunk_pipeline（tender_skills run_pipeline）
     → workspace JSON（manifest / outline / document_tree / linkage / chunks）
     → import_workspace（tk 薄适配层）
     → DocumentMediaAsset → DocumentTreeNode → BidOutline → Candidates
```

变更仅发生在：

- `tender_skills` 包版本（path editable）
- `tests/fixtures/doc_chunk_workspace_minimal/` 内容
- 测试与文档（+ 可能的极小 mapper 修复）

---

## 4. 依赖升级与 Fixture 刷新

### 4.1 目标版本

- **tender_skills 目标 commit**：`163db06`（或联调当日 `git rev-parse HEAD`，记入 quickstart）
- **依赖声明**：保持 `backend/pyproject.toml` 中 `doc-chunk @ file:../../tender_skills`（editable path，不改为 git URL pin）

### 4.2 升级步骤

```bash
# 1. tender_skills 自检
cd ../tender_skills
git checkout <target-commit>
pip install -e ".[dev]"
python -m pytest tests/unit tests/contract -q

# 2. tk backend 重装
cd ../tender_knowledge/backend
pip install -e ".[dev]"

# 3. 刷新 minimal fixture
python -m doc_chunk.cli.main run /path/to/minimal.docx /tmp/ws-minimal \
  --overwrite --skip-refine
# 拷贝 /tmp/ws-minimal 下全部 JSON 到 tests/fixtures/doc_chunk_workspace_minimal/
```

**Fixture 来源**：优先 tk 现有 `sample_docx` 测试夹具；若结构不足，使用 tender_skills 契约最小 docx。

**全量替换文件**（8 项保持一致）：

- `manifest.json`、`outline.json`、`document_tree.json`、`linkage.json`
- `chunks/index.json`、`chunks/chunk-*.json`
- `images/manifest.json`

### 4.3 适配层「仅失败时修改」

| 失败类型 | 可能改动点 |
|---------|-----------|
| workspace 必填文件变化 | `workspace_loader.py` |
| 标题带编号导致 enrich/candidate 跳过 | `linkage_validation.normalize_title` 增加编号前缀剥离 |
| `outline.json.strategy` 枚举新增 | `bid_outline.map_outline_strategy` |
| integration 候选条数变化 | 更新 `test_doc_chunk_parse_flow` 期望值（附注释说明） |

---

## 5. 测试与验收

### 5.1 CI 门禁（必过）

```bash
cd backend
pytest tests/unit/test_doc_chunk_*.py -v
pytest tests/integration/test_doc_chunk_parse_flow.py -v
pytest tests/contract/test_actual_bid_parse*.py -v
```

关键断言：

- `test_doc_chunk_parse_flow`：任务 `status=ready`，`candidate_count` 与 fixture 一致
- mapper 单测：`build_toc_entries` 产出 `source_node_id` 映射完整

### 5.2 本地大样例（不进 CI）

新增 `backend/tests/integration/test_doc_chunk_canbu_import.py`：

- `@pytest.mark.skipif(not os.environ.get("DOC_CHUNK_CANBU_FIXTURE"))`
- 调用真实 `run_doc_chunk_pipeline`（**不 mock**）
- 调用 `import_workspace` 落库
- 断言（对齐 tender_skills `test_canbu_regression`）：
  - `document_tree` 节点 `node_id` 全局唯一
  - 每个 outline 节点在 linkage 中有非空 `document_tree_node_ids`
  - `candidate_count / outline_count ∈ [0.8, 1.2]`（排除 Preface）
  - 任务无 `DOC_CHUNK_IMPORT_FAILED`

运行：

```bash
export DOC_CHUNK_CANBU_FIXTURE="/path/to/餐补标书.docx"
cd backend && pytest tests/integration/test_doc_chunk_canbu_import.py -v -s
```

可选：`DOC_CHUNK_DINGXIN_FIXTURE` 参数化第二份鼎信样例（有则加，不强制）。

### 5.3 人工抽检（可选）

- 确认向导目录标题含「六、」等编号前缀显示正确
- 候选详情正文非空、嵌入图片可展示

---

## 6. 回滚策略

| 场景 | 动作 |
|------|------|
| 运行时 | `USE_DOC_CHUNK_PARSE=false` 切 legacy |
| 依赖 | `tender_skills` checkout 上一已知好 commit + git revert fixture |
| 数据库 | 无 migration，无需 schema 回滚 |

---

## 7. 文档更新

- `specs/009-doc-chunk-integration/quickstart.md`：补充已验证 tender_skills commit、场景 6 集成测试命令
- 本 design spec 作为实现依据

---

## 8. 实现任务摘要（供 writing-plans 展开）

1. 升级并重装 `tender_skills` + backend 依赖
2. 重导 `doc_chunk_workspace_minimal` fixture
3. 跑 CI 测试套件，按 §4.3 最小修复适配层
4. 新增 `test_doc_chunk_canbu_import.py`
5. 更新 quickstart 文档
6. 本地执行餐补（+ 可选鼎信）大样例并记录指标

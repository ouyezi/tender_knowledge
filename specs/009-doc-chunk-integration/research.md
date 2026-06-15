# Research: 实际标书解析接入 doc_chunk

**Date**: 2026-06-15  
**Feature**: `specs/009-doc-chunk-integration`

## R1: doc_chunk 依赖引入方式

### Decision

在 `backend/pyproject.toml` 中以 **editable path 依赖** 引用同级仓库 `tender_skills`：

```toml
doc-chunk = { path = "../../tender_skills", editable = true }
```

本地开发与 CI 通过环境变量 `DOC_CHUNK_PATH` 覆盖路径；生产镜像构建时将 `tender_skills` 子模块或固定 tag 拷贝进镜像。

### Rationale

- doc_chunk 尚未发布 PyPI；path 依赖与 002/003 验证版本对齐最直接。
- editable 便于联调修复，与 monorepo 邻接布局一致（`xlab/tender_knowledge` + `xlab/tender_skills`）。

### Alternatives considered

- **Git URL + commit pin**：适合 CI，本地需网络；作为 CI 备选。
- **Vendor 拷贝源码**：维护成本高，拒绝。
- **继续内嵌 walk_document**：重复维护，拒绝（本特性目标即替换）。

---

## R2: 解析流水线架构

### Decision

在 `actual_bid_parse_runner._run_entry` 中按 `Settings.use_doc_chunk_parse` 分支：

| 策略 | 路径 |
|------|------|
| `doc_chunk`（默认） | `docm_converter` → `doc_chunk.run_pipeline` → `doc_chunk_import_service` 落库 |
| `legacy` | 现有 `walk_document` → `extract_toc_entries` → `candidate_generate_service` |

新增服务模块（不修改 doc_chunk 包）：

```text
backend/src/services/doc_chunk/
├── workspace_manager.py      # 临时目录创建/清理
├── pipeline_runner.py        # 封装 run_pipeline + on_progress 映射
├── import_service.py         # 工作区 JSON → DB 实体
├── mappers/
│   ├── document_tree.py
│   ├── bid_outline.py
│   ├── candidates.py
│   └── media_assets.py
└── blocks_v1.py              # image_ref → asset_id + blocks_v1 序列化
```

`import_service` 单次事务顺序：**媒体资产 → DocumentTree → BidOutline → 分类 → Candidates → suggestion**。

### Rationale

- 保持 API / 任务模型不变，满足 US2「确认向导无感知」。
- legacy 分支零改动路径，满足 FR-006 回退与 SC-004。
- 落库逻辑集中，便于契约测试 mock 工作区 fixture。

### Alternatives considered

- **完全替换 runner 为新文件**：diff 面大，拒绝；采用分支 + 抽取 import。
- **候选仍走 generate_for_document**：与 doc_chunk 切片重复且可能不一致；拒绝，改由 linkage+chunk 生成（FR-004）。

---

## R3: ID 映射与 linkage 消费

### Decision

维护单次导入的 `ImportContext`（内存，不持久化表）：

| doc_chunk | tender_knowledge |
|-----------|------------------|
| `document_tree.nodes[].node_id` | `DocumentTreeNode.node_id` (UUID) |
| `outline.nodes[].node_id` | 临时键 → `BidOutlineNode` + `source_node_id` |
| `linkage.entries[].primary_chunk_id` | 候选生成主键 |
| `linkage.entries[].document_tree_node_ids[0]` | `CandidateKnowledge.source_node_id` |
| `images/manifest.json` `image_ref` | `DocumentMediaAsset.asset_id` |

outline 节点 → tree heading：优先 `linkage.document_tree_node_ids`；缺失时按 `outline_node_id` 在 tree 中查找。

### Rationale

003 修复后 linkage 对每条 outline 必有 tree 引用；与 doc_chunk 契约一致。

### Alternatives considered

- **仅用 document_tree heading 遍历生成候选**：003 修复前会缺 16 条；拒绝。
- **持久化 doc_chunk 临时 ID 表**：过度设计；拒绝。

---

## R4: 候选生成与 Preface 过滤

### Decision

- 仅对 `linkage.entries` 中 `chunk_ids` 非空且 `primary_chunk_id` 对应 chunk 的 `title != "Preface"` 且 `original_node_ids` 非空者生成候选。
- `metadata.suggested_candidate_type == "ignore"` 或 `chapter_candidate_rules` 解析为 ignore 时跳过。
- 正文：`blocks_to_v1_json(chunk.blocks, image_ref_to_asset_id=ctx.map)`。
- 分类：先应用 doc_chunk enrich metadata hints（字符串→KB UUID 模糊匹配），再可选调用既有 `classify_chunk` 补全。

### Rationale

对齐 spec 边缘案例「Preface 不得误生成候选」与 FR-010。

---

## R5: 进度与阶段映射

### Decision

`doc_chunk` `on_progress` stage 映射到 `ActualBidParseTaskPhase`：

| doc_chunk stage | tk phase | 用户可见消息示例 |
|-----------------|----------|------------------|
| extract | document_parse | 提取文档正文与图片 |
| outline | bid_outline_extract | 生成目录树 |
| tree | document_parse | 构建文档结构树 |
| chunk | candidate_generate | 章节分块 |
| enrich | candidate_generate | 章节分类与元数据 |

写入既有 `llm_progress.logs` 结构，不新增 API 字段。

### Rationale

满足 FR-005；前端 ActualBidParseConfirmWizard 无需改动。

---

## R6: 工作区生命周期

### Decision

- 路径：`{storage_root}/doc_chunk_workspaces/{import_id}/{parse_task_id}/`
- 成功：默认删除（`doc_chunk_workspace_retention_on_success=false`）
- 失败：保留 24h（`doc_chunk_workspace_retention_hours=24`）
- `manifest.json` 摘要写入 `document_parse_suggestion` 扩展字段 `doc_chunk_manifest`（可选，供排障）

### Rationale

满足边缘案例「不得无限堆积」；失败可排障。

---

## R7: Bid Outline diff 与 extract_strategy

### Decision

- `BidOutline.extract_strategy` 新增枚举值 `doc_chunk`，映射自 `outline.json.strategy`（toc/heading_heuristic/content_heuristic/flat_fallback）。
- `force_reparse` + `structure_locked_at` 流程不变：新 outline entries 喂给 `bid_outline_diff_service`，不直接覆盖节点。

### Rationale

Constitution III；与 004 行为一致。

---

## R8: 测试策略

### Decision

| 层级 | 内容 |
|------|------|
| unit | `import_service` 各 mapper；blocks_v1 图片映射；Preface 过滤 |
| contract | 解析 API 不变；`use_doc_chunk_parse=true` 用 workspace fixture 注入 |
| integration | 小型 docx 端到端；可选 `DOC_CHUNK_CANBU_FIXTURE` 大文件 |
| regression | `use_doc_chunk_parse=false` 跑既有契约；template parse 不变 |

Fixtures：`tests/fixtures/doc_chunk_workspace_minimal/` 从 tender_skills 契约样例导出。

### Rationale

SC-001–SC-006 可自动化；大文件不阻塞 CI。

---

## R9: 配置项

### Decision

`Settings` 新增：

```python
use_doc_chunk_parse: bool = True
doc_chunk_path: str | None = None          # 覆盖 tender_skills 路径（可选）
doc_chunk_skip_enrich: bool = False        # pipeline --skip-enrich
doc_chunk_workspace_retention_on_success: bool = False
doc_chunk_workspace_retention_hours: int = 24
doc_chunk_classification_config: str | None = None  # 可选 YAML 路径
```

环境变量：`USE_DOC_CHUNK_PARSE`, `DOC_CHUNK_SKIP_ENRICH`, 等。

### Rationale

FR-006；默认开启 doc_chunk（spec Assumptions）。

---

## Resolved Clarifications

| 原未知项 | 决议 |
|----------|------|
| 依赖安装方式 | path editable + CI git pin |
| 候选生成入口 | linkage + chunk，非 generate_for_document |
| 分类来源 | enrich hints + 既有 classify_chunk |
| legacy 保留范围 | 完整 runner 分支，非 dead code 删除 |

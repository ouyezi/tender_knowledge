# Design: 知识可见性 — 正式知识浏览、章节切片与图片渲染

**Date**: 2026-06-14  
**Status**: Approved  
**Brainstorming**: 2026-06-14（用户确认 OK）  
**Related**: Epic 3 候选生成、Epic 4 候选确认与发布、Epic 5 检索（本设计不修改检索策略）

## 1. 背景与问题

### 1.1 用户反馈

1. **已发布知识在哪里看？** 后端已有 `GET /knowledge-units`、`/wikis`、`/manual-assets` 只读 API，但前端导航无对应页面；用户只能在「候选」中心看到 `status=published` 的候选记录，而非正式资产实体。
2. **知识块只有一行或标题**（如 `doc_8d920ea4-...`）：文档候选生成时 `content = heading.content_preview`，而 heading 节点的 preview 仅为标题文本；章节下 paragraph/table/image 子节点未聚合。
3. **图片不可见**：解析链路将纯图片段落标记为 `node_type=image`、`text="[image]"`，未提取二进制、未提供访问 URL。

### 1.2 根因摘要

| 现象 | 根因 |
|------|------|
| 无正式知识浏览 | 前端缺 `/knowledge` 页面；API 已就绪 |
| 候选仅标题 | `candidate_generate_service` 只取 heading 自身 preview |
| 图片占位 | `docx_tree_materializer` 不写 asset；无 media API |

### 1.3 目标

- **P1 切片修复**：每个 heading 候选包含该章节正文（段落、表格、图片引用），边界清晰、子章节不重复。
- **P2 图片可见**：docx inline 图片解析期抽盘，候选/正式知识/发布页均可渲染。
- **P3 正式知识浏览**：新页面三 Tab（KU / Wiki / 手册资产），只读详情含富文本与来源链。

## 2. Brainstorming 决议

| # | 议题 | 决议 |
|---|------|------|
| D1 | 优先级 | **C**：正式知识浏览 + 切片修复同时交付 |
| D2 | 图片 | **必须可见**；采用解析期抽盘 + 结构化 content blocks |
| D3 | 正式知识页范围 | **B**：KU + Wiki + 手册资产三 Tab（复用现有 API） |
| D4 | 方案选型 | **方案 ①** 结构化内容块 + 解析期抽图（非按需读 docx、非双轨 Tree 预览） |
| D5 | Content 存储 | JSON `blocks_v1` 写入现有 `content` Text 字段；纯文本向后兼容 |
| D6 | 历史数据 | 提供回填脚本；默认不重写已发布 KU |

## 3. 方案对比（Brainstorming）

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **① 结构化块 + 抽图（选用）** | 聚合章节 + JSON blocks + media 表/API | 发布后独立可见；候选与正式一致 | 解析改动较大 |
| ② 纯文本 + 按需拉图 | 聚合 Markdown；看图时读原 docx | 改动小 | 依赖原文件；KU 无法归档图 |
| ③ 双轨 Tree 预览 | 正文纯文本 + 侧边 Document Tree | 复用 Tree API | 知识块内看不到图；体验分裂 |

## 4. 架构

### 4.1 数据流

```text
docx 文件
  → docx_document_walker → document_tree_nodes
  → docx_image_extractor → storage + document_media_assets
  → section_content_builder → CandidateKnowledge.content (blocks_v1)
  → publish → knowledge_units / wikis / manual_assets (content 原样拷贝)
  → RichContentViewer ← GET /media/{asset_id}
```

### 4.2 新增/修改模块

| 模块 | 类型 | 职责 |
|------|------|------|
| `section_content_builder.py` | 新增 | 按 heading 边界聚合子节点 → ContentDocument |
| `content_blocks.py` | 新增 | 块类型、序列化、plain 降级 |
| `docx_image_extractor.py` | 新增 | 从 docx 提取 inline 图至 storage |
| `document_media_asset` | 新表 | asset_id、kb_id、document_id、storage_path、mime_type |
| `media.py` | 新 API | `GET /api/v1/kbs/{kb_id}/media/{asset_id}` |
| `candidate_generate_service` | 修改 | content 改用 section builder |
| `candidates.py` | 修改 | 列表增加 `content_excerpt` |
| `RichContentViewer` | 新前端组件 | 渲染 blocks_v1 / plain |
| `KnowledgeCenterPage` | 新前端页面 | `/knowledge` 三 Tab |

### 4.3 不在范围

- 检索策略与索引分块（Epic 5）
- PPT/PDF 图片提取
- 正式知识编辑、废弃、版本管理 UI
- Document Tree 可视化编辑器

## 5. Content 格式（blocks_v1）

`CandidateKnowledge.content`、`KnowledgeUnit.content`、`Wiki.content` 等 Text 字段存 JSON 字符串：

```json
{
  "format": "blocks_v1",
  "blocks": [
    {"type": "paragraph", "text": "正文段落..."},
    {"type": "table", "text": "列1 | 列2\n值1 | 值2"},
    {"type": "image", "asset_id": "550e8400-e29b-41d4-a716-446655440000", "alt": "架构图"}
  ]
}
```

### 5.1 块类型

| type | 字段 | 说明 |
|------|------|------|
| `paragraph` | `text` | 普通段落 |
| `table` | `text` | 管道符表格文本（与现有 table 节点一致） |
| `image` | `asset_id`, `alt?`, `width?` | 引用 `document_media_assets` |

### 5.2 向后兼容

- 无法解析为 JSON 或缺少 `format`：视为 **plain text**，前端整段 `<pre>` / `Typography.Paragraph` 渲染。
- 混合段落（text + inline image）：拆为 `paragraph` + `image` 两个 block。

### 5.3 发布行为

Publisher（`ku_publisher`、`wiki_publisher` 等）**原样拷贝** candidate 的 `content` 字符串，不在发布时重算聚合。

## 6. 章节切片逻辑

### 6.1 边界规则

对每个 **heading** 节点（`DocumentTreeNode.node_type = heading`）生成候选时：

```
内容范围 = 该 heading 之后、下一个「同级或更高级 heading」之前的所有非 heading 节点
```

- 「同级或更高级」：`level <= 当前 heading.level`（level 数字越小层级越高）。
- 范围内的 **嵌套 heading** 不作为当前候选正文，由各自独立候选承担（避免重复）。

### 6.2 示例

```text
H1 技术方案          ← 候选 A
  P  段落1            ← A
  T  表格1            ← A
  H2 子方案           ← 候选 B
    P  段落2          ← B
  P  段落3            ← A（B 子树结束后、下一 H1 前）
H1 实施计划          ← 候选 C
```

### 6.3 API：`build_section_content`

```python
def build_section_content(
    db: Session,
    *,
    document_id: UUID,
    heading_node_id: UUID,
) -> str:
    """返回 blocks_v1 JSON 字符串。"""
```

实现要点：

1. 按 `sort_order` 加载 document 全部 nodes（同 `tree_version`）。
2. 定位 heading，记录 `level` 与 `sort_order`。
3. 向后扫描至停止条件。
4. 中间节点映射为 blocks；image 节点从 `content_ref` 读 `asset_id`。

### 6.4 空章节

- 无正文块：`{"format":"blocks_v1","blocks":[]}`。
- 列表 `content_excerpt` 显示「（仅标题）」。

## 7. 图片管道

### 7.1 解析期提取

在 `actual_bid_parse_runner` 持久化 Document Tree 时（或紧前）：

1. `docx_image_extractor.extract(docx_path, kb_id, document_id)` 遍历含 `w:drawing` 的段落。
2. 从 docx 关系部件读取二进制，写入：
   `{storage_root}/{kb_id}/media/{document_id}/{asset_id}.{ext}`
3. INSERT `document_media_assets`。
4. 对应 tree node：`node_type=image`，`content_ref=str(asset_id)`，`content_preview=null`。

### 7.2 `document_media_assets` 表

| 列 | 类型 | 说明 |
|----|------|------|
| asset_id | UUID PK | |
| kb_id | UUID | |
| document_id | UUID FK | |
| storage_path | VARCHAR(1024) | 相对 storage_root |
| mime_type | VARCHAR(64) | image/png, image/jpeg, … |
| source_block_index | INT nullable | docx 块序号（追溯） |
| created_at | TIMESTAMPTZ | |

### 7.3 Media API

```
GET /api/v1/kbs/{kb_id}/media/{asset_id}
```

- 校验 asset.kb_id == kb_id。
- 返回 `FileResponse`，正确 `Content-Type`。
- 404 若文件或记录不存在。

### 7.4 提取失败

- 单图失败不阻断 parse task。
- block 写入 `{"type":"image","asset_id":null,"fallback":"[image]"}`。
- 前端显示破损占位 + alt/fallback 文本。

## 8. 前端设计

### 8.1 路由与导航

| 路径 | 页面 | 导航 |
|------|------|------|
| `/knowledge` | KnowledgeCenterPage | 新增「正式知识」（位于「候选」之后） |

### 8.2 正式知识中心

**Tabs**：知识单元 | Wiki | 手册资产

**共用列表列**：标题、类型、摘要（截断）、状态、更新时间、操作（查看）

**Tab 特有列**：

| Tab | API | 额外列 |
|-----|-----|--------|
| 知识单元 | `GET .../knowledge-units` | knowledge_type |
| Wiki | `GET .../wikis` | wiki_type |
| 手册资产 | `GET .../manual-assets` | asset_type |

**筛选（MVP）**：关键词（标题/摘要 client 或 server）、status=published

**详情 Drawer**：

- 元信息 Descriptions
- 来源链：import_id、candidate_id、source_doc_id（链至候选详情）
- 正文：`RichContentViewer`
- 手册资产：`storage_path` 下载/预览链接（若存在）

### 8.3 RichContentViewer

Props: `content: string`, `kbId: string`

行为：

1. 尝试 JSON 解析；`format === "blocks_v1"` → 按 type 渲染。
2. `image` → `<img src={/api/v1/kbs/${kbId}/media/${assetId}} />`。
3. 否则 plain text，`whiteSpace: pre-wrap`。
4. 空 blocks → Empty「暂无正文」。

### 8.4 候选中心改动

| 位置 | 改动 |
|------|------|
| 列表 | 新增「内容摘要」列（`content_excerpt`，~120 字） |
| CandidateDetailDrawer | 非 pending：正文区改用 RichContentViewer |
| CandidateConfirmPage 左栏 | 只读正文改用 RichContentViewer |
| pending 编辑 | 保留 TextArea；增加「预览」Tab 显示 RichContentViewer（编辑后 client 侧 plain 或 blocks 预览） |

## 9. API 变更

### 9.1 候选列表 `GET /candidates`

每条 item 增加：

```json
{
  "content_excerpt": "首段正文截断..."
}
```

由 `content_blocks.excerpt(content, max_len=120)` 计算。

### 9.2 新增 Media API

见 §7.3。

### 9.3 正式知识 API

现有 list/get **不 breaking change**；前端直接消费。可选后续：list 响应增加 `content_excerpt`（本 MVP 可在前端从 content 计算）。

## 10. 错误处理

| 场景 | 行为 |
|------|------|
| 章节无正文 | blocks 空数组；excerpt「（仅标题）」 |
| 图片提取失败 | fallback block；parse 继续 |
| media 404 | 占位 UI |
| 旧纯文本 content | plain 降级 |
| 已发布 KU 与候选 content 不一致 | 不回填 KU（除非脚本 `--include-published-ku`） |

## 11. 历史回填

脚本：`scripts/backfill_candidate_section_content.py`

```
--kb-id UUID
--import-id UUID   # 可选，限定导入
--dry-run          # 仅打印变更统计
--include-published-ku  # 可选，同步已发布 KU/Wiki content
```

默认只更新 `status=pending` 的 `CandidateKnowledge`。

## 12. 测试计划

| 层 | 用例 |
|----|------|
| 单元 | `section_content_builder`：嵌套 heading、空章、表格、边界 |
| 单元 | `content_blocks`：serialize、excerpt、plain 降级 |
| 单元 | `docx_image_extractor`：fixture docx 含 inline 图 |
| 契约 | candidates list 含 content_excerpt |
| 契约 | media API kb 隔离、404 |
| 集成 | 解析 → 候选含段落+图 → 发布 KU → GET KU content 可读 |
| 前端 | RichContentViewer：blocks / plain / 空 / 破图 |

## 13. 交付切片

| 阶段 | 内容 | 验收 |
|------|------|------|
| **P0** | section_content_builder + generate_for_document + content_excerpt | 候选详情见整章正文（图仍可能占位） |
| **P1** | docx_image_extractor + media 表/API + RichContentViewer | 候选/发布页图片可见 |
| **P2** | /knowledge 三 Tab + 详情 Drawer | 已发布 KU/Wiki/手册资产可浏览 |
| **P3** | backfill 脚本 + 候选编辑预览 Tab | 历史 pending 候选可修复 |

## 14. 依赖与风险

| 风险 | 缓解 |
|------|------|
| 大章节 content 超长 | blocks 内单段 text 上限 32KB；超出截断并 log |
| storage 磁盘 | 图片按 document 隔离；复用 storage_root 配置 |
| 检索索引未含图 | 本设计不改 IndexBuilder；文本块仍进索引 |
| 模板候选 tpl_* | 暂不改 stub 生成；RichContentViewer plain 兼容现有 preview |

---

**Approval**: 用户于 2026-06-14 brainstorming 确认 OK。

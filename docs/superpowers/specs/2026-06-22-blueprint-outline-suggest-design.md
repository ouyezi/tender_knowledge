# Design: 蓝图目录建议（Outline Suggest）

**Date**: 2026-06-22  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-21-directory-blueprint-design.md` · `docs/superpowers/specs/2026-06-22-directory-blueprint-generation-extraction-design.md` · Epic 6 Tender Requirement Context（后续合并）

---

## 1. 背景与目标

### 1.1 痛点

| 痛点 | 说明 |
|------|------|
| 蓝图只能看不能用 | 已沉淀的目录蓝图含写作指导，但无法针对具体项目需求快速生成建议目录 |
| 缺少探索入口 | 用户需在脑内消化蓝图后再手工组织新标书目录，效率低 |
| 后续模块无锚点 | 标书生成等下游能力缺少「蓝图 + 需求 → 建议目录」的标准化无状态接口 |

### 1.2 产品定位

在**目录蓝图详情页**提供「目录建议」能力：用户输入自由文本的目录需求描述，系统结合一份或多份目录蓝图经验（节点写作指导、建议结构等）与专用 system prompt，由 LLM 生成一套**全新的有序目录建议**供查看参考。V1 **不落库、不写回蓝图**。

### 1.3 建设目标

- 蓝图详情页：按钮 + 右侧 50% Drawer，上输入、下结果
- 后端：无状态 `POST /blueprints/suggest-outline`，契约自 V1 起可作为对外接口
- 多蓝图输入：`blueprint_ids[]` 自 V1 设计支持，详情页 UI 仅传当前蓝图 ID
- 输出：嵌套有序目录树，每节点含标题、内容建议、拆分/不拆分理由

### 1.4 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 结果用途 | A. 探索/预览，无状态，不落库 |
| 与蓝图节点关系 | A. 独立新大纲，蓝图作经验库，非 1:1 映射 |
| 用户输入 | A. 纯自由文本「目录需求描述」 |
| 多蓝图 | A. API `blueprint_ids[]`，V1 UI 传 `[currentId]` |
| 生成交互 | A. 一次性返回 + loading，复用 120s 超时策略 |
| 实现方案 | B. 独立 `blueprint_outline_suggest_service` + 新 API |
| 写回蓝图 | V1 不做 |
| 流式 / 异步任务 | V1 不做 |

---

## 2. 用户交互

### 2.1 入口

- 页面：`BlueprintDetailPage`（只读与编辑模式均可打开）
- 位置：顶部 Card `extra` 操作区
- 按钮文案：**目录建议**

### 2.2 Drawer 布局

| 区域 | 内容 |
|------|------|
| 容器 | Ant Design `Drawer`，`placement="right"`，`width="50%"` |
| 上半 | 多行文本 `目录需求描述`（必填，placeholder 引导填写项目背景、招标要求、希望突出的章节等） |
| 操作 | 「生成建议」主按钮；生成中 disabled + loading |
| 下半 | 结果区：空态文案 / Spin / 树形结果 |

### 2.3 结果展示（每节点）

- **标题** + **重要程度** Tag（`required` / `recommended` / `optional`）
- **内容建议**：该章节写什么、重点是什么
- **有子节点**：展示「拆分理由」
- **叶子节点**：展示「不拆分理由」

### 2.4 状态与持久化

- 关闭 Drawer 即丢弃本次输入与结果
- 刷新页面不保留
- 不写入蓝图、不创建历史记录表

---

## 3. API 契约

### 3.1 端点

```
POST /api/v1/kbs/{kb_id}/blueprints/suggest-outline
```

### 3.2 Request

```json
{
  "blueprint_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "requirement_description": "某政务云项目，需突出安全合规与运维保障，评分侧重技术方案与实施计划……"
}
```

| 字段 | 类型 | 约束 |
|------|------|------|
| `blueprint_ids` | `UUID[]` | 1–5 个；均须属于 `{kb_id}` 且存在 |
| `requirement_description` | `string` | 去空白后非空；≤ 2000 字符 |

### 3.3 Response（200）

```json
{
  "outline_title": "政务云技术方案建议目录",
  "summary": "按评分权重优先展开技术方案与实施保障，资质与商务章节从简。",
  "nodes": [
    {
      "title": "技术方案",
      "content_suggestion": "阐述总体架构、云平台选型与安全合规设计，对应技术评分大头。",
      "importance": "required",
      "split_reason": "技术评分项细分为架构、安全、运维三块，分别独立成章便于对应打分表。",
      "no_split_reason": null,
      "children": [
        {
          "title": "总体架构设计",
          "content_suggestion": "描述逻辑架构、部署架构及与现有系统的对接方式。",
          "importance": "required",
          "split_reason": null,
          "no_split_reason": "架构设计作为一个整体论述即可，再拆分会打散架构完整性。",
          "children": []
        }
      ]
    }
  ]
}
```

### 3.4 节点字段语义

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | 是 | 章节标题，不含序号前缀 |
| `content_suggestion` | 是 | 该章节内容建议（1–3 句） |
| `importance` | 是 | `required` \| `recommended` \| `optional` |
| `split_reason` | 条件 | 有非空 `children` 时必填，说明为何拆出子目录 |
| `no_split_reason` | 条件 | `children` 为空时必填，说明为何不继续拆分或拆分不合适 |
| `children` | 是 | 有序子节点数组，叶子为 `[]` |

**互斥规则**：`split_reason` 与 `no_split_reason` 二选一非空。

**结构约束**：建议深度 ≤ 4；服务端校验失败返回 502。

### 3.5 错误响应

| HTTP | code | 场景 |
|------|------|------|
| 400 | `invalid_request` | 空描述、ids 为空、ids 超过 5 个、描述超长 |
| 404 | `blueprint_not_found` | 任一 `blueprint_id` 不存在或不属于 kb |
| 503 | `llm_not_configured` | `llm_enabled` 为 false |
| 502 | `outline_suggest_failed` | LLM 调用失败或 JSON/schema 校验失败 |
| 504 | `outline_suggest_timeout` | 超过 `blueprint_suggest_timeout_sec` |

响应 envelope 复用现有 `success` / `error` 格式。

---

## 4. 后端架构

### 4.1 模块划分

```text
backend/src/api/routes/blueprints.py
  └── POST /suggest-outline
        └── blueprint_outline_suggest_service.suggest_outline()

backend/src/services/knowledge/blueprint_outline_suggest_service.py  （新建）
  ├── load_blueprint_contexts()      # 批量加载并精简蓝图
  ├── build_suggest_user_prompt()    # 拼装 user prompt
  ├── call_llm()                     # 复用 urllib 模式（对齐 generate_service）
  ├── parse_and_validate_response()  # JSON 解析 + 节点互斥校验
  └── suggest_outline()              # 入口

backend/src/api/schemas/blueprints.py
  ├── SuggestOutlineRequest
  └── SuggestOutlineResponse / SuggestOutlineNode
```

**不修改** `blueprint_generate_service`（文档提取职责保持独立）。

### 4.2 上下文组装

对每个 `blueprint_id` 调用 `get_blueprint_detail`，精简为：

**蓝图级**

- `name`, `description`, `scenario_tags`, `product_tags`, `industry_tags`
- `suggested_structure_md`（截断至 800 字符）

**节点级**（递归，短 key 省 token）

- `t`: `node_title`
- `imp`: `importance_level`
- `cd`: `content_description`（截断 200 字）
- `tr`: `tender_response_hint`（截断 200 字）
- `children`: 子节点数组

多蓝图按 `blueprint_ids` 顺序放入数组。总 prompt 超限时：

1. 优先截断叶子节点 `cd` / `tr`
2. 再截断深层子树
3. 最后截断 `suggested_structure_md`

### 4.3 LLM 契约

**System prompt 要点**

- 角色：标书目录顾问
- 输入：多份目录蓝图经验 JSON + 用户目录需求描述
- 任务：生成针对需求的**全新**有序目录，非蓝图节点镜像
- 每节点必须给出内容建议；有子目录则说明拆分理由，叶子则说明不拆分理由
- `importance` 取值 `required` | `recommended` | `optional`
- 只返回 JSON，无 markdown 包裹

**User prompt 结构**

```text
【目录蓝图经验】
{compact_blueprints_json}

【用户目录需求】
{requirement_description}
```

### 4.4 配置（`config.py`）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `blueprint_suggest_model` | 同 `blueprint_generate_model` | 可独立调参 |
| `blueprint_suggest_timeout_sec` | `120` | HTTP 读超时 |
| `blueprint_suggest_max_tokens` | `8192` | 建议目录体量小于提取任务 |
| `blueprint_suggest_max_blueprints` | `5` | 请求蓝图数上限 |
| `blueprint_suggest_requirement_max` | `2000` | 需求描述上限 |

### 4.5 数据库

**V1 无迁移**。只读查询现有 `knowledge_blueprints` / `knowledge_blueprint_nodes`。

---

## 5. 前端架构

### 5.1 文件

| 文件 | 职责 |
|------|------|
| `frontend/src/components/Blueprint/BlueprintOutlineSuggestDrawer.tsx` | Drawer：输入、生成、结果、错误提示 |
| `frontend/src/components/Blueprint/BlueprintOutlineSuggestTree.tsx` | 只读递归树展示 |
| `frontend/src/services/blueprints.ts` | `suggestBlueprintOutline()` + TS 类型 |
| `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx` | 按钮与 `open` 状态 |

### 5.2 API Client 类型

```typescript
interface SuggestOutlineRequest {
  blueprint_ids: string[];
  requirement_description: string;
}

interface SuggestOutlineNode {
  title: string;
  content_suggestion: string;
  importance: ImportanceLevel;
  split_reason: string | null;
  no_split_reason: string | null;
  children: SuggestOutlineNode[];
}

interface SuggestOutlineResult {
  outline_title: string;
  summary: string;
  nodes: SuggestOutlineNode[];
}
```

### 5.3 错误 UX

| 场景 | 展示 |
|------|------|
| 未填需求 | 前端 `message.warning` |
| 504 超时 | 「生成超时，请精简需求后重试」 |
| 502 / 503 | 展示 API 错误信息 |
| 生成中关闭 Drawer | 取消展示（请求可自然完成，不更新已关闭 UI） |

---

## 6. 测试计划

| 层级 | 文件 | 覆盖 |
|------|------|------|
| 单元 | `test_blueprint_outline_suggest_service.py` | 上下文精简、prompt 构建、JSON 解析、split/no_split 互斥校验 |
| 集成 | `test_blueprint_api.py`（扩展） | happy path（mock LLM）、400/404/502 |
| 配置 | `test_blueprint_config.py`（扩展） | 新配置项默认值 |
| 前端 | 手动 / 可选组件测试 | Drawer 开关、空态、结果树渲染 |

---

## 7. V1 明确不做

- 结果持久化与历史记录
- 采纳写回蓝图
- SSE 流式输出
- 异步任务轮询
- 需求描述附件上传
- Tender Requirement Context 合并（后续 Epic 6）
- 与 Epic 5 检索/模块建议打通

---

## 8. 远期扩展

| 方向 | 预留 |
|------|------|
| 多蓝图 | `blueprint_ids[]` 已支持；调用方可传多 ID |
| 对外 Open API | 独立端点与服务，可直接暴露 |
| 招标约束 | 请求体可加 `tender_context` 或 ID 字段 |
| 下游消费 | 标书生成模块调用同一 API 获取建议目录 |
| 持久化 | 后续可加 `outline_suggestions` 表，V1 不阻塞 |

---

## 9. 方案选型记录

| 方案 | 结论 |
|------|------|
| A. 扩展 `blueprint_generate_service` | 职责混杂，弃用 |
| **B. 独立 suggest 服务 + API** | **采用** |
| C. 通用 directory_generation 平台 | V1 过度设计，弃用 |

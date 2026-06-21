# tender_knowledge

企业知识库平台研发仓库。当前实现 **四个核心模块**：知识库管理、来源导入、知识录入、知识浏览；文档解析基于同级仓库 `tender_skills` 中的 **doc-chunk**。

## 目录

- [产品定位](#产品定位)
- [核心模块](#核心模块)
- [业务流程](#业务流程)
- [技术栈](#技术栈)
- [前置依赖](#前置依赖)
- [快速开始](#快速开始)
- [环境变量](#环境变量)
- [项目结构](#项目结构)
- [API 概览](#api-概览)
- [测试](#测试)
- [研发规范](#研发规范)

## 产品定位

将企业文档经 **单文件导入 → doc_chunk 解析 → 用途确认 → 知识录入** 治理为结构化知识块（Knowledge Chunk），支持目录树浏览、内容预览、属性预填与向量化存储。

## 核心模块

| 模块 | 前端路由 | 后端 API | 说明 |
|------|----------|----------|------|
| 知识库管理 | `/` | `/api/v1/kbs` | 创建、列表、重命名、停用知识库 |
| 来源导入 | `/file-imports` | `/api/v1/kbs/{kb_id}/file-imports` | 上传 docx/docm/pdf 等，确认用途，触发 doc_chunk 解析 |
| 知识录入 | `/knowledge/entry` | `/api/v1/kbs/{kb_id}/knowledge-chunks/*` | 从已解析文档树选取节点，预填属性并创建知识块 |
| 知识浏览 | `/knowledge/browse` | 同上 | 筛选、查看知识块详情与关联资产 |

启动后访问：

- 前端：<http://127.0.0.1:5173/>
- API 健康检查：<http://127.0.0.1:8000/health>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

## 业务流程

```text
创建知识库
  → 上传文件（来源导入）
  → 确认文件用途（actual_bid | template_file）
  → 后台 doc_chunk 解析（Document Tree + 媒体资产 + Chunk Assets）
  → 知识录入（选目录节点 → 预填 → 保存 Knowledge Chunk → 异步向量化）
  → 知识浏览（筛选、查看内容与图片/表格资产）
```

**文件用途**（`FilePurpose`）：

- `actual_bid` — 实际标书
- `template_file` — 标书模板

解析由 `document_parse_runner` 编排，默认启用 doc_chunk（`USE_DOC_CHUNK_PARSE=true`），结果写入 `documents`、`document_tree_nodes`、`document_media_assets`，供知识录入使用。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11、FastAPI、SQLAlchemy 2.0、Pydantic v2 |
| 数据库 | PostgreSQL 15 + [pgvector](https://github.com/pgvector/pgvector) |
| 文档解析 | `doc-chunk`（path 依赖 `../../tender_skills`） |
| 前端 | React 18、TypeScript 5、Vite 5、Ant Design 5 |
| LLM | 可配置 Qwen / OpenAI 兼容接口（解析 enrich、知识预填、Embedding） |

## 前置依赖

- **Docker** — 运行 PostgreSQL（`docker compose`）
- **Python 3.11+** — 后端与脚本
- **Node.js 18+** — 前端开发服务器
- **同级仓库 `tender_skills`** — doc-chunk 包来源

```text
xlab/
├── tender_knowledge/    ← 本仓库
└── tender_skills/       ← doc-chunk 依赖（backend/pyproject.toml 中 file:../../tender_skills）
```

## 快速开始

### 1. 安装依赖

```bash
# 后端（仓库根目录）
python3.11 -m venv .venv
.venv/bin/pip install -e "backend[dev]"

# 若 doc-chunk 安装失败，先在 tender_skills 中安装：
# cd ../tender_skills && pip install -e ".[dev]"

# 前端
cd frontend && npm install && cd ..
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env：至少设置 LLM_API_KEY（解析 enrich 与知识预填需要）
```

默认数据库连接（与 `docker-compose.yml` 一致）：

```text
postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge
```

### 3. 启动服务

```bash
./scripts/start.sh
```

`start.sh` 会依次：启动 Postgres → 启动后端（`backend/startup.py`，端口 8000）→ 启动前端 dev server（端口 5173）。

| 变量 | 默认 | 说明 |
|------|------|------|
| `BACKEND_PORT` | `8000` | API 端口 |
| `FRONTEND_PORT` | `5173` | 前端端口 |
| `POSTGRES_PORT` | `5433` | 宿主机映射的 Postgres 端口 |
| `SKIP_DOCKER` | `0` | 设为 `1` 跳过 Docker Postgres（使用已有实例） |
| `BACKEND_RELOAD` | `0` | 设为 `1` 启用 uvicorn 热重载 |

停止与重启：

```bash
./scripts/stop.sh
# 保留 Postgres：STOP_POSTGRES=0 ./scripts/stop.sh

./scripts/restart.sh
```

### 4. 手动启动（可选）

```bash
# Postgres
docker compose up -d postgres

# 后端
cd backend
export DATABASE_URL=postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge
../.venv/bin/python startup.py

# 前端（新终端）
cd frontend && npm run dev
```

首次启动时，`init_db()` 会自动创建 pgvector 扩展并同步 ORM 表结构。

## 环境变量

完整示例见 [.env.example](.env.example)。常用项：

```bash
# 数据库
DATABASE_URL=postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge

# LLM（LLM_PROVIDER: qwen | openai | custom）
LLM_PROVIDER=qwen
LLM_API_KEY=sk-...
LLM_BASE_URL=          # custom 时必填
LLM_MODEL=               # 留空则使用 preset 默认模型

# doc_chunk 解析
USE_DOC_CHUNK_PARSE=true
DOC_CHUNK_SKIP_ENRICH=false
DOC_CHUNK_WORKSPACE_RETENTION_ON_SUCCESS=false
DOC_CHUNK_WORKSPACE_RETENTION_HOURS=24

# 存储与 Embedding
STORAGE_ROOT=data/uploads
EMBEDDING_MODEL=text-embedding-v2
KNOWLEDGE_PREFILL_MODEL=qwen3-max
```

## 项目结构

```text
tender_knowledge/
├── backend/
│   ├── startup.py                # 入口：init_db + uvicorn
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py               # FastAPI app、路由注册
│   │   ├── config.py             # Settings
│   │   ├── api/routes/           # knowledge_bases, file_imports, knowledge_chunks, media
│   │   ├── db/                   # engine、session、init_db
│   │   ├── models/               # ORM 实体
│   │   └── services/
│   │       ├── document_parse_runner.py
│   │       ├── doc_chunk/        # 工作区、pipeline、import、mappers
│   │       ├── knowledge/        # 知识块 CRUD、预填、向量化、录入内容
│   │       ├── file_import_service.py
│   │       ├── file_import_purge_service.py
│   │       └── confirm_service.py
│   └── tests/                    # unit / contract / integration
├── frontend/
│   └── src/
│       ├── App.tsx               # 四模块路由
│       ├── layout/               # AppShell、KBContext
│       ├── pages/                # KnowledgeBaseList, FileImportCenter, Knowledge
│       ├── components/Knowledge/
│       └── services/
├── scripts/                      # start.sh, stop.sh, restart.sh
├── docker-compose.yml
├── .env.example
└── logs/
```

### 数据表

```text
knowledge_bases, kb_clone_logs
file_imports, import_tasks, import_audit_logs, file_purpose_suggestions, downstream_task_entries
documents, document_tree_nodes, document_media_assets, document_parse_suggestions
actual_bid_parse_tasks
knowledge_chunks, chunk_assets, chunk_embeddings
```

## API 概览

所有 JSON 接口返回统一 envelope：`{ "data": ..., "trace_id": "..." }`。写操作需请求头 `X-Operator-Id`（前端默认 `admin`）。

### 知识库 `/api/v1/kbs`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/kbs` | 创建知识库 |
| GET | `/api/v1/kbs` | 列表（`?status=active`） |
| GET | `/api/v1/kbs/{kb_id}` | 详情 |
| PATCH | `/api/v1/kbs/{kb_id}` | 重命名 |
| POST | `/api/v1/kbs/{kb_id}/deactivate` | 停用 |

### 来源导入 `/api/v1/kbs/{kb_id}/file-imports`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `` | 上传文件 |
| GET | `` | 分页列表 |
| GET | `/{import_id}` | 详情 |
| POST | `/{import_id}/confirm` | 确认用途并进入解析 |
| POST | `/{import_id}/ignore` | 忽略 |
| POST | `/{import_id}/retry` | 重试导入任务 |
| POST | `/{import_id}/retry-parse` | 重试解析 |
| DELETE | `/{import_id}` | 删除 |
| POST | `/purge-all` | 清空知识库下全部导入 |
| GET | `/audit-logs` | 审计日志 |

### 知识块 `/api/v1/kbs/{kb_id}/knowledge-chunks`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/entry/documents` | 可录入的已解析文档 |
| GET | `/entry/documents/{doc_id}/tree` | 文档目录树 |
| GET | `/entry/documents/{doc_id}/nodes/{node_id}/preview` | 节点预览（正文 + 资产） |
| POST | `/prefill` | LLM 预填知识属性 |
| POST | `` | 创建知识块（触发后台 embedding） |
| GET | `` | 列表与筛选 |
| GET | `/{chunk_id}` | 详情 |
| GET | `/chunk-assets` | 资产列表 |

### 媒体 `/api/v1/kbs/{kb_id}/media/{asset_id}`

返回文档内图片等媒体文件的二进制内容。

## 测试

```bash
# 后端
cd backend
../.venv/bin/python -m pytest tests/ -q

# 分层
../.venv/bin/python -m pytest tests/unit -q
../.venv/bin/python -m pytest tests/contract -q
../.venv/bin/python -m pytest tests/integration -q

# 前端
cd frontend && npm test
```

默认使用 SQLite 内存库；可通过 `TEST_DATABASE_URL` 覆盖为 Postgres。

## 研发规范

新功能开发遵循 Spec Kit 流水线，详见 [.specify/memory/constitution.md](.specify/memory/constitution.md)：

```text
/speckit.specify → /speckit.plan → /speckit.tasks → 按任务 TDD 实现
```

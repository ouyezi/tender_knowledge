# Quickstart: Epic 0 分类底座

**Feature**: `specs/001-classification-base`  
**Purpose**: 端到端验证 P0–P3（多 KB 壳层 + 产品分类 + 章节分类 + 生命周期）

## Prerequisites

- Docker & Docker Compose
- Python 3.11+（项目根 `.venv`）
- Node.js 20+（`frontend/`）

## 一键启动

```bash
# 首次：安装依赖
python -m venv .venv
.venv/bin/pip install -e "backend/[dev]"
cd frontend && npm install && cd ..

# 启动 PostgreSQL + API + 管理后台
./scripts/start.sh

# 停止
./scripts/stop.sh

# 重启
./scripts/restart.sh
```

| 服务 | 地址 |
|------|------|
| API Health | http://127.0.0.1:8000/health |
| OpenAPI | http://127.0.0.1:8000/docs |
| 管理后台 | http://127.0.0.1:5173 |

日志：`logs/backend.log`、`logs/frontend.log`  
PID：`.run/`

### 数据库说明

- Docker Postgres 映射宿主端口 **5433**（避免与本机 5432 冲突）
- 默认连接串：`postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge`
- 应用启动时自动 `create_all` 建表（Alembic 迁移后续补齐）
- 可复制 `.env.example` 为 `.env` 覆盖 `DATABASE_URL`

### 手动启动（可选）

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge
.venv/bin/python backend/startup.py   # 另开终端
cd frontend && npm run dev            # 另开终端
```

前端通过 Vite 代理 `/api` → `127.0.0.1:8000`，请使用 **http://127.0.0.1:5173** 或 **http://localhost:5173** 访问。

## 测试

```bash
cd backend && ../.venv/bin/pytest -v
cd frontend && npm run build
```

当前：**23** 项后端测试（contract / integration / unit）。

## Validation Scenarios

### VS-0 — P0 多知识库

```bash
BASE="http://127.0.0.1:8000/api/v1/kbs"

# 创建空 KB
curl -s -X POST "$BASE" -H "Content-Type: application/json" \
  -H "X-Operator-Id: admin" \
  -d '{"name":"KB-demo"}' | jq .

# 从已有 KB 克隆分类树
curl -s -X POST "$BASE" -H "Content-Type: application/json" \
  -H "X-Operator-Id: admin" \
  -d '{"name":"KB-cloned","clone_from_kb_id":"<source-kb-uuid>"}' | jq .

curl -s "$BASE?status=active" -H "X-Operator-Id: admin" | jq '.data.items'
```

**Expected**: 列表含 active KB；克隆后目标 KB 含源 KB 的产品/章节分类。

### VS-1 — P1 产品分类树（SC-001）

```bash
KB_ID="<demo-kb-uuid>"
PC="http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/product-categories"

curl -s -X POST "$PC" -H "Content-Type: application/json" \
  -H "X-Operator-Id: admin" \
  -d '{"category_name":"福利产品","category_code":"welfare","aliases":[]}' | jq .

curl -s -X POST "$PC" -H "Content-Type: application/json" \
  -H "X-Operator-Id: admin" \
  -d '{"parent_id":"<root-uuid>","category_name":"餐补","category_code":"meal","aliases":["员工餐补"]}' | jq .

curl -s "$PC/tree" | jq '.data.nodes'
curl -s "$PC/search?q=餐补" | jq '.data.items | length'
```

**Expected**: 树展示多级结构；别名搜索命中。

> 别名无需重复标准名；若 `aliases` 含与 `category_name` 相同的项，服务端会自动去重。

### VS-2 — P2 章节分类与产品绑定（SC-002）

```bash
TAX="http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/chapter-taxonomies"

curl -s -X POST "$TAX" -H "Content-Type: application/json" \
  -H "X-Operator-Id: admin" \
  -d '{
    "standard_name":"售后服务方案",
    "taxonomy_code":"after-sales",
    "synonyms":["驻场服务方案"],
    "product_category_ids":["<meal-category-uuid>"]
  }' | jq .

curl -s "$TAX?product_category_id=<meal-category-uuid>" | jq '.data.items'
```

**Expected**: 同义名可维护；按产品分类筛选返回绑定章节。

### VS-3 — P3 影响分析与合并（SC-003, SC-005）

```bash
# 注入测试引用（需已存在至少一个产品分类）
.venv/bin/python backend/scripts/seed_classification_references.py

curl -s "$PC/<source-uuid>/impact" | jq '.data'
curl -s -X POST "$PC/<source-uuid>/merge" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: admin" \
  -d '{"target_category_id":"<target-uuid>"}' | jq .

curl -s "$PC/<source-uuid>" | jq '.data.status'   # → "merged"
```

**Expected**: impact 返回 `by_object_type` 分组；合并迁移引用并写 audit。

### VS-4 — Epic 1 就绪（SC-004）

```bash
curl -s "$PC/tree?status=active" | jq '.data.nodes | length'
curl -s "$TAX/tree?status=active" | jq '.data.nodes | length'
```

**Expected**: active 分类树可供下游读接口消费。

### VS-5 — UI 冒烟（管理后台）

1. 顶栏切换知识库；停用 KB 后页面只读。
2. **产品分类中心**：创建/编辑/别名/影响分析/合并/停用/归档。
3. **章节目录中心**：章节类型 + 绑定产品分类 + 生命周期操作。

**Expected**: 与 VS-0–3 API 行为一致；无控制台网络错误。

## Troubleshooting

| 现象 | 检查 |
|------|------|
| API 500 `role "tender" does not exist` | 连到了本机 5432 而非 Docker 5433；执行 `./scripts/restart.sh` |
| 浏览器 CORS / OPTIONS 405 | 使用前端代理访问；或确认后端已启用 CORSMiddleware |
| 409 `Duplicate alias in request` | 别名列表含与标准名重复项（已自动过滤，需重启后端） |
| 409 CONFLICT on alias | 别名已被其他分类占用 |
| 409 HAS_ACTIVE_CHILDREN | 停用前需先处理 active 子节点 |
| impact 全 0 | Epic 0 正常；运行 `seed_classification_references.py` |
| merge HAS_CHILDREN | 源节点仍有 active 子分类 |

## Related Artifacts

- [spec.md](./spec.md) — 用户故事与 FR
- [data-model.md](./data-model.md) — 实体与约束
- [contracts/knowledge-base-api.md](./contracts/knowledge-base-api.md) — KB API
- [contracts/product-category-api.md](./contracts/product-category-api.md)
- [contracts/chapter-taxonomy-api.md](./contracts/chapter-taxonomy-api.md)
- [research.md](./research.md) — 技术决策

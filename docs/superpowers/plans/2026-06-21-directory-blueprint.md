# Directory Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付「目录蓝图」全栈功能：从文档目录树 LLM 提取写作模板、独立表存储、录入页 Tab 编辑、蓝图列表/详情管理，并在文档 purge 时级联删除。

**Architecture:** 独立 `knowledge_blueprints` / `knowledge_blueprint_nodes` 表 + `/api/v1/kbs/{kb_id}/blueprints/*` 路由；`generate` 无状态不落库；保存经人工确认后 upsert；前端共享 `BlueprintEditor` 组件。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL, pytest; React 18, TypeScript, Ant Design 5.

**Design spec:** `docs/superpowers/specs/2026-06-21-directory-blueprint-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/alembic/versions/20260621_1000_directory_blueprint.py` | 蓝图两表 DDL |
| `backend/src/models/knowledge_blueprint.py` | 主表 ORM + `ImportanceLevel` 枚举 |
| `backend/src/models/knowledge_blueprint_node.py` | 节点表 ORM |
| `backend/src/config.py` | `blueprint_generate_model` / `blueprint_generate_timeout_sec` |
| `backend/src/services/knowledge/blueprint_tree_utils.py` | flat↔nested、node_code 编号 |
| `backend/src/services/knowledge/blueprint_service.py` | CRUD、replace_nodes、by-source |
| `backend/src/services/knowledge/blueprint_generate_service.py` | 子树拼接 + LLM + JSON 解析 |
| `backend/src/api/schemas/blueprints.py` | Pydantic 请求/响应 |
| `backend/src/api/routes/blueprints.py` | REST API |
| `backend/src/services/knowledge/entry_content_service.py` | tree 返回 `has_blueprint` |
| `backend/src/services/file_import_purge_service.py` | purge 级联删蓝图 |
| `backend/src/main.py` | 注册 blueprints router |
| `frontend/src/services/blueprints.ts` | API client + 类型 |
| `frontend/src/components/Blueprint/*.tsx` | 共享编辑器组件族 |
| `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx` | 三栏 + 右 Tab + 提取按钮 |
| `frontend/src/pages/Knowledge/BlueprintListPage.tsx` | 列表筛选 |
| `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx` | 详情/编辑 |
| `frontend/src/App.tsx` / `frontend/src/layout/AppShell.tsx` | 路由与导航 |

---

## Task 1: 蓝图 LLM 配置项

**Files:**
- Modify: `backend/src/config.py`
- Create: `backend/tests/unit/test_blueprint_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_blueprint_config.py
from src.config import settings


def test_blueprint_generate_defaults():
    assert settings.blueprint_generate_model == "qwen-plus"
    assert settings.blueprint_generate_timeout_sec == 30
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/unit/test_blueprint_config.py -v
```

Expected: FAIL `AttributeError: blueprint_generate_model`

- [ ] **Step 3: Add settings fields**

In `backend/src/config.py` inside `class Settings`:

```python
    blueprint_generate_model: str = "qwen-plus"
    blueprint_generate_timeout_sec: int = 30
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/unit/test_blueprint_config.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/config.py backend/tests/unit/test_blueprint_config.py
git commit -m "feat: add blueprint generate LLM config settings"
```

---

## Task 2: 数据库 Migration + ORM Models

**Files:**
- Create: `backend/alembic/versions/20260621_1000_directory_blueprint.py`
- Create: `backend/src/models/knowledge_blueprint.py`
- Create: `backend/src/models/knowledge_blueprint_node.py`
- Modify: `backend/src/models/__init__.py`

- [ ] **Step 1: Create Alembic migration**

`down_revision = "20260620_1000"`. 创建 `knowledge_blueprints` 与 `knowledge_blueprint_nodes`：

```python
# 关键约束
sa.UniqueConstraint("kb_id", "source_node_id", name="uq_blueprints_kb_source_node")
sa.Index("ix_knowledge_blueprints_kb_id", "kb_id")
sa.Index("ix_knowledge_blueprint_nodes_blueprint_id", "blueprint_id")
sa.Index("ix_knowledge_blueprint_nodes_parent_node_id", "parent_node_id")
```

字段类型参照 design spec §3.2–3.3；JSON 列用 `postgresql.JSONB`；`importance_level` 用 `sa.String(20)`。

- [ ] **Step 2: Create ORM models**

`knowledge_blueprint.py`:

```python
class BlueprintStatus(str, enum.Enum):
    active = "active"
    archived = "archived"

class KnowledgeBlueprint(Base):
    __tablename__ = "knowledge_blueprints"
    blueprint_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # ... 其余字段 per spec
```

`knowledge_blueprint_node.py`:

```python
class ImportanceLevel(str, enum.Enum):
    required = "required"
    recommended = "recommended"
    optional = "optional"
```

- [ ] **Step 3: Export in `models/__init__.py`**

- [ ] **Step 4: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: 无报错，两表存在

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260621_1000_directory_blueprint.py \
  backend/src/models/knowledge_blueprint.py \
  backend/src/models/knowledge_blueprint_node.py \
  backend/src/models/__init__.py
git commit -m "feat: add knowledge blueprint database models and migration"
```

---

## Task 3: blueprint_tree_utils（TDD）

**Files:**
- Create: `backend/src/services/knowledge/blueprint_tree_utils.py`
- Create: `backend/tests/unit/test_blueprint_tree_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_blueprint_tree_utils.py
from src.services.knowledge.blueprint_tree_utils import (
    assign_node_codes,
    flatten_tree,
    nest_tree,
)


def test_assign_node_codes_nested():
    nodes = [
        {"node_title": "A", "node_level": 1, "children": [
            {"node_title": "A1", "node_level": 2, "children": []},
        ]},
    ]
    assign_node_codes(nodes)
    assert nodes[0]["node_code"] == "1"
    assert nodes[0]["children"][0]["node_code"] == "1.1"


def test_flatten_and_nest_roundtrip():
    nested = [{"node_title": "Root", "node_level": 1, "node_order": 0, "children": []}]
    flat = flatten_tree(nested)
    assert len(flat) == 1
    assert flat[0]["node_title"] == "Root"
    back = nest_tree(flat)
    assert back[0]["node_title"] == "Root"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && pytest tests/unit/test_blueprint_tree_utils.py -v
```

- [ ] **Step 3: Implement utils**

```python
# blueprint_tree_utils.py
def assign_node_codes(nodes: list[dict], *, prefix: str = "") -> None:
    for index, node in enumerate(nodes, start=1):
        code = f"{prefix}{index}" if not prefix else f"{prefix}.{index}"
        node["node_code"] = code
        children = node.get("children") or []
        assign_node_codes(children, prefix=code)

def flatten_tree(nested: list[dict], *, parent_id=None) -> list[dict]:
    ...

def nest_tree(flat: list[dict]) -> list[dict]:
    ...
```

实现 `map_llm_flags_to_importance(required_flag, recommended_flag) -> str` 供 generate 使用。

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_tree_utils.py backend/tests/unit/test_blueprint_tree_utils.py
git commit -m "feat: add blueprint tree utils with node_code assignment"
```

---

## Task 4: blueprint_service CRUD（TDD）

**Files:**
- Create: `backend/src/services/knowledge/blueprint_service.py`
- Create: `backend/tests/unit/test_blueprint_service.py`

- [ ] **Step 1: Write failing tests**（使用 `db_session`, `seeded_kb` fixture）

```python
def test_create_and_get_by_source(db_session, seeded_kb):
    from uuid import uuid4
    from src.services.knowledge.blueprint_service import create_blueprint, get_blueprint_by_source

    doc_id, node_id = uuid4(), uuid4()
    payload = {
        "name": "测试蓝图",
        "source_doc_id": doc_id,
        "source_node_id": node_id,
        "source_chapter_title": "第一章",
        "nodes": [{"node_title": "节1", "node_level": 1, "node_order": 0, "importance_level": "required"}],
    }
    bp = create_blueprint(db_session, kb_id=seeded_kb.kb_id, payload=payload)
    found = get_blueprint_by_source(db_session, kb_id=seeded_kb.kb_id, source_node_id=node_id)
    assert found.blueprint_id == bp.blueprint_id


def test_create_duplicate_source_raises(db_session, seeded_kb):
    # 第二次 create 同 source_node_id → BlueprintConflictError
    ...


def test_update_increments_version(db_session, seeded_kb):
    # PUT 后 version 默认 +1
    ...
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement service**

核心函数：

```python
class BlueprintConflictError(Exception): ...
class BlueprintValidationError(Exception): ...

def create_blueprint(db, *, kb_id, payload) -> KnowledgeBlueprint: ...
def update_blueprint(db, *, kb_id, blueprint_id, payload) -> KnowledgeBlueprint: ...
def replace_nodes(db, *, blueprint_id, flat_nodes) -> None: ...  # delete all + insert
def get_blueprint_by_source(db, *, kb_id, source_node_id): ...
def get_blueprint_detail(db, *, kb_id, blueprint_id) -> dict: ...  # nested nodes
def list_blueprints(db, *, kb_id, filters, page, page_size) -> tuple[list, int]: ...
def delete_blueprint(db, *, kb_id, blueprint_id) -> None: ...
def delete_blueprints_by_doc_id(db, *, doc_id) -> int: ...
```

校验：`name` 非空；至少 1 个 `node_level==1` 节点。

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add blueprint CRUD service with source uniqueness"
```

---

## Task 5: blueprint_generate_service（TDD, mock LLM）

**Files:**
- Create: `backend/src/services/knowledge/blueprint_generate_service.py`
- Create: `backend/tests/unit/test_blueprint_generate_service.py`

- [ ] **Step 1: Write failing tests**

```python
MOCK_LLM_JSON = '''
{
  "outline_title": "供应链方案通用大纲",
  "overall_strategy": "强调仓配能力",
  "usual_page_range": "5-8页",
  "related_regulations": ["ISO9001"],
  "common_mistakes": "忽视应急预案",
  "template_style": "formal",
  "nodes": [{
    "node_title": "总体设计", "node_level": 1, "children": [],
    "purpose": "p", "writing_goal": "g", "writing_hint": "h",
    "required_flag": true, "recommended_flag": false,
    "content_type": "text", "keyword_hint": ["供应链"]
  }]
}
'''

def test_generate_maps_importance_and_node_code(db_session, seeded_kb, monkeypatch):
    # seed document tree with parent+child
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **_: MOCK_LLM_JSON,
    )
    from src.services.knowledge.blueprint_generate_service import generate_blueprint_draft
    draft = generate_blueprint_draft(db_session, kb_id=..., doc_id=..., node_id=parent_id)
    assert draft["name"] == "供应链方案通用大纲"
    assert draft["nodes"][0]["importance_level"] == "required"
    assert draft["nodes"][0]["node_code"] == "1"


def test_generate_rejects_leaf_node(db_session, seeded_kb):
    # 无子节点 → NoChildNodesError
    ...
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement generate service**

```python
class NoChildNodesError(Exception): ...
class BlueprintGenerateTimeoutError(Exception): ...
class BlueprintGenerateFailedError(Exception): ...

def collect_subtree_outline(db, *, kb_id, doc_id, node_id) -> list[dict]:
    # 复用 entry_content_service 的 heading 加载 + 子树收集，仅 title/level

def generate_blueprint_draft(db, *, kb_id, doc_id, node_id) -> dict:
    document = _get_ready_document(...)  # parse_status == ready
    outline = collect_subtree_outline(...)
    if not any child of node_id:
        raise NoChildNodesError
    raw = _chat_with_timeout(system_prompt=..., user_prompt=..., timeout=settings.blueprint_generate_timeout_sec)
    parsed = _parse_llm_json(raw)  # strip markdown fences
    draft = _normalize_draft(parsed, source_meta=...)
    assign_node_codes(draft["nodes"])
    return draft
```

`_chat_with_timeout` 模式复制 `prefill_service._chat_with_timeout`，使用 `settings.blueprint_generate_model`。

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add blueprint LLM generate service with JSON normalization"
```

---

## Task 6: API Schemas + Routes

**Files:**
- Create: `backend/src/api/schemas/blueprints.py`
- Create: `backend/src/api/routes/blueprints.py`
- Modify: `backend/src/main.py`

- [ ] **Step 1: Define Pydantic schemas**

```python
class GenerateBlueprintRequest(BaseModel):
    doc_id: UUID
    node_id: UUID

class BlueprintNodeInput(BaseModel):
    node_code: str | None = None
    node_title: str
    node_level: int
    node_order: int
    importance_level: Literal["required", "recommended", "optional"]
    purpose: str | None = None
    writing_goal: str | None = None
    writing_hint: str | None = None
    content_type: str | None = None
    keyword_hint: list[str] = []
    children: list["BlueprintNodeInput"] = []

class SaveBlueprintRequest(BaseModel):
    name: str
    description: str | None = None
    source_doc_id: UUID
    source_node_id: UUID
    source_chapter_title: str | None = None
    product_tags: list[str] = []
    industry_tags: list[str] = []
    scenario_tags: list[str] = []
    applicable_project_type: list[str] = []
    overall_strategy: str | None = None
    template_style: str | None = None
    usual_page_range: str | None = None
    related_regulations: list[str] = []
    common_mistakes: str | None = None
    version: int | None = None
    nodes: list[BlueprintNodeInput]
```

- [ ] **Step 2: Implement routes**

```python
router = APIRouter(prefix="/api/v1/kbs/{kb_id}/blueprints", tags=["blueprints"])

@router.post("/generate")
@router.get("/by-source")
@router.post("", status_code=201)
@router.put("/{blueprint_id}")
@router.get("")
@router.get("/{blueprint_id}")
@router.delete("/{blueprint_id}")
```

错误映射：
- `NoChildNodesError` → 400 `no_child_nodes`
- `BlueprintGenerateTimeoutError` → 504 `blueprint_generate_timeout`
- `BlueprintGenerateFailedError` → 502 `blueprint_generate_failed`
- `BlueprintConflictError` → 409 `blueprint_source_exists`
- `BlueprintValidationError` → 422

- [ ] **Step 3: Register router in `main.py`**

```python
from src.api.routes.blueprints import router as blueprints_router
app.include_router(blueprints_router)
```

- [ ] **Step 4: Smoke via OpenAPI**

```bash
cd backend && uvicorn src.main:app --reload &
curl -s http://127.0.0.1:8000/docs | head
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add blueprint REST API routes"
```

---

## Task 7: 集成测试

**Files:**
- Create: `backend/tests/integration/test_blueprint_api.py`

- [ ] **Step 1: Write integration tests**

```python
def test_generate_create_get_flow(client, db_session, seeded_kb, monkeypatch):
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr("src.services.knowledge.blueprint_generate_service._chat_with_timeout", lambda **_: MOCK_LLM_JSON)

    gen = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/generate", json={
        "doc_id": str(document.document_id), "node_id": str(parent.node_id),
    })
    assert gen.status_code == 200
    draft = gen.json()["data"]

    create = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=draft)
    assert create.status_code == 201

    dup = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=draft)
    assert dup.status_code == 409

    tree = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/entry/documents/{document.document_id}/tree")
    assert tree.json()["data"]["items"][0]["has_blueprint"] is True


def test_list_filter_and_delete(client, db_session, seeded_kb): ...
```

- [ ] **Step 2: Run integration tests**

```bash
cd backend && pytest tests/integration/test_blueprint_api.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "test: add blueprint API integration tests"
```

---

## Task 8: Tree `has_blueprint` 扩展

**Files:**
- Modify: `backend/src/services/knowledge/entry_content_service.py`
- Modify: `backend/tests/integration/test_knowledge_api.py`（或新建小测试）

- [ ] **Step 1: Write failing test**

```python
def test_document_tree_includes_has_blueprint(client, db_session, seeded_kb):
    # seed blueprint for parent node
    ...
    resp = client.get(f".../tree")
    assert resp.json()["data"]["items"][0]["has_blueprint"] is True
```

- [ ] **Step 2: Implement**

在 `get_document_tree` 中：

```python
from src.models.knowledge_blueprint import KnowledgeBlueprint

blueprint_node_ids = {
    str(row.source_node_id)
    for row in db.query(KnowledgeBlueprint.source_node_id)
    .filter(KnowledgeBlueprint.kb_id == kb_id, KnowledgeBlueprint.source_doc_id == doc_id)
    .all()
}
```

修改 `_build_tree_payload` 签名，增加 `blueprint_node_ids: set[str]`，输出 `"has_blueprint": str(node.node_id) in blueprint_node_ids`。

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: expose has_blueprint flag on entry document tree"
```

---

## Task 9: Purge 级联删除蓝图

**Files:**
- Modify: `backend/src/services/file_import_purge_service.py`
- Modify: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: Write failing test**

```python
def test_purge_deletes_blueprints_for_document(db_session, seeded_kb):
    # seed doc + blueprint linked to doc_id
    ...
    purge_file_import(db_session, kb_id=..., import_id=...)
    assert db_session.query(KnowledgeBlueprint).count() == 0
```

- [ ] **Step 2: Implement**

在删除 `document_tree_nodes` 前：

```python
from src.services.knowledge.blueprint_service import delete_blueprints_by_doc_id

for doc in documents:
    _inc(deleted_counts, "knowledge_blueprints", delete_blueprints_by_doc_id(db, doc_id=doc.document_id))
```

- [ ] **Step 3: Run purge tests**

```bash
cd backend && pytest tests/unit/test_file_import_purge_service.py -v
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: cascade delete blueprints on file import purge"
```

---

## Task 10: 前端 API Client

**Files:**
- Create: `frontend/src/services/blueprints.ts`
- Modify: `frontend/src/services/knowledgeChunks.ts`（`TreeNode` 增加 `has_blueprint?: boolean`）

- [ ] **Step 1: Add types and API functions**

```typescript
export type ImportanceLevel = "required" | "recommended" | "optional";

export interface BlueprintNode {
  node_id?: string;
  node_code?: string;
  node_title: string;
  node_level: number;
  node_order: number;
  importance_level: ImportanceLevel;
  purpose?: string;
  writing_goal?: string;
  writing_hint?: string;
  content_type?: string;
  keyword_hint?: string[];
  children?: BlueprintNode[];
}

export interface BlueprintDraft {
  blueprint_id?: string;
  name: string;
  description?: string;
  source_doc_id: string;
  source_node_id: string;
  source_chapter_title?: string;
  product_tags?: string[];
  industry_tags?: string[];
  scenario_tags?: string[];
  applicable_project_type?: string[];
  overall_strategy?: string;
  template_style?: string;
  usual_page_range?: string;
  related_regulations?: string[];
  common_mistakes?: string;
  version?: number;
  nodes: BlueprintNode[];
}

export async function generateBlueprint(kbId: string, body: { doc_id: string; node_id: string }) { ... }
export async function getBlueprintBySource(kbId: string, params: { doc_id: string; node_id: string }) { ... }
export async function createBlueprint(kbId: string, body: BlueprintDraft) { ... }
export async function updateBlueprint(kbId: string, id: string, body: BlueprintDraft) { ... }
export async function listBlueprints(kbId: string, params: Record<string, string>) { ... }
export async function getBlueprint(kbId: string, id: string) { ... }
export async function deleteBlueprint(kbId: string, id: string) { ... }
```

- [ ] **Step 2: Extend TreeNode**

```typescript
export interface TreeNode {
  ...
  has_blueprint?: boolean;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/blueprints.ts frontend/src/services/knowledgeChunks.ts
git commit -m "feat: add blueprint frontend API client"
```

---

## Task 11: BlueprintEditor 组件族

**Files:**
- Create: `frontend/src/components/Blueprint/BlueprintEditor.tsx`
- Create: `frontend/src/components/Blueprint/BlueprintMetaForm.tsx`
- Create: `frontend/src/components/Blueprint/BlueprintOutlineTree.tsx`
- Create: `frontend/src/components/Blueprint/BlueprintNodeDetailPanel.tsx`
- Create: `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.tsx`
- Create: `frontend/src/constants/blueprintMeta.ts`（importance_level / template_style 标签）

- [ ] **Step 1: Implement `BlueprintMetaForm`**

包含全部字段：name、description、version、product/industry/scenario/applicable_project_type tags、template_style、overall_strategy、usual_page_range、related_regulations、common_mistakes。

- [ ] **Step 2: Implement `BlueprintOutlineTree`**

- 行内编辑标题（Inline Input）
- importance_level 用 `Radio.Group` 或 Tag + 下拉
- 删除节点 `Modal.confirm`
- 底部「+ 添加一级章节」「+ 添加子节点」
- 选中节点回调 `onSelectNode`

- [ ] **Step 3: Implement `BlueprintNodeDetailPanel`**

编辑 purpose/writing_goal/writing_hint/content_type/keyword_hint/node_code。

- [ ] **Step 4: Implement `BlueprintEditor`**

组合 MetaForm + OutlineTree + NodeDetailPanel + 底部【重新生成】【保存为蓝图】；props 见 design spec §6.2。

- [ ] **Step 5: Implement `BlueprintOutlineTreeReadonly`**

`Tree` 组件 `defaultExpandAll`；标题点击 `navigator.clipboard.writeText` + `message.success`。

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add shared BlueprintEditor component suite"
```

---

## Task 12: KnowledgeEntryPage Tab 集成

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx`

- [ ] **Step 1: Add state**

```typescript
const [activeTab, setActiveTab] = useState<"entry" | "blueprint">("entry");
const [blueprintDraft, setBlueprintDraft] = useState<BlueprintDraft | null>(null);
const [blueprintLoading, setBlueprintLoading] = useState(false);
const [existingBlueprintId, setExistingBlueprintId] = useState<string | null>(null);
```

- [ ] **Step 2: Node/doc change reset**

```typescript
useEffect(() => {
  form.resetFields();
  setRightExpanded(false);
  setBlueprintDraft(null);
  setExistingBlueprintId(null);
  setActiveTab("entry");
}, [selectedDocId, selectedNodeId]);
```

- [ ] **Step 3: Extract button in tree Card**

在目录树 `Card` 底部增加【提取目录蓝图】：

```typescript
const selectedNodeHasChildren = useMemo(() => {
  if (!selectedNodeId) return false;
  const find = (nodes: TreeNode[]): TreeNode | undefined => { ... };
  const node = find(treeNodes);
  return Boolean(node?.children?.length);
}, [treeNodes, selectedNodeId]);

const showExtractButton = selectedDocument?.parse_status === "ready";
```

点击逻辑：检查 `has_blueprint` / `getBlueprintBySource` → Modal → `generateBlueprint` → `setBlueprintDraft` → `setActiveTab("blueprint")`。

- [ ] **Step 4: Replace entryPanel with Tabs**

```tsx
entryPanel={
  <Card bodyStyle={{ maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
    <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
      { key: "entry", label: "知识录入", children: <EntryPanel ... /> },
      { key: "blueprint", label: "目录蓝图", children: (
        <BlueprintEditor
          mode="draft"
          value={blueprintDraft ?? EMPTY_DRAFT}
          loading={blueprintLoading}
          readOnly={readOnly}
          onChange={setBlueprintDraft}
          onRegenerate={handleRegenerateBlueprint}
          onSave={handleSaveBlueprint}
          sourceInfo={{ chapterTitle: preview?.catalog_path?.at(-1)?.title ?? "", documentName: selectedDocument?.document_name ?? "" }}
        />
      )},
    ]} />
  </Card>
}
```

- [ ] **Step 5: Update `toTreeData`**

```typescript
{node.has_blueprint ? <Tag color="blue">已生成蓝图</Tag> : null}
```

- [ ] **Step 6: Save handler**

校验 name + 一级节点 → `createBlueprint` 或 409 时 Modal → `updateBlueprint` → 刷新 tree。

- [ ] **Step 7: Manual smoke on entry page**

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: integrate blueprint tab into knowledge entry page"
```

---

## Task 13: 蓝图列表与详情页

**Files:**
- Create: `frontend/src/pages/Knowledge/BlueprintListPage.tsx`
- Create: `frontend/src/pages/Knowledge/BlueprintDetailPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: BlueprintListPage**

参照 `KnowledgeBrowsePage`：筛选 Form + Table + 分页；列：name、scenario_tags、product_tags、industry_tags、updated_at；操作：查看、删除。

- [ ] **Step 2: BlueprintDetailPage**

路由 `/knowledge/blueprints/:id`；只读模式展示 Meta + ReadonlyTree；【编辑】切换 `BlueprintEditor`；【删除】Popconfirm。

- [ ] **Step 3: Register routes and nav**

```tsx
// App.tsx
<Route path="/knowledge/blueprints" element={<BlueprintListPage />} />
<Route path="/knowledge/blueprints/:id" element={<BlueprintDetailPage />} />

// AppShell.tsx NAV_ITEMS
{ key: "/knowledge/blueprints", label: <Link to="/knowledge/blueprints">目录蓝图</Link> }
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add blueprint list and detail pages with navigation"
```

---

## Task 14: 全量回归 + 手工 Smoke

**Files:** none（验证任务）

- [ ] **Step 1: Backend full unit + integration**

```bash
cd backend && pytest tests/unit/test_blueprint_* tests/integration/test_blueprint_api.py tests/unit/test_file_import_purge_service.py -v
```

Expected: PASS

- [ ] **Step 2: Frontend typecheck**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Manual smoke（design spec §8.3）**

1. 提取 → 编辑 → 保存 → 树图标
2. 重复提取确认
3. Tab 切换 / 节点切换清空
4. 列表筛选 → 详情 → 复制 → 编辑
5. purge 文档 → 蓝图消失

- [ ] **Step 4: Update README API 概览**（可选一行蓝图 API）

- [ ] **Step 5: Final commit if README touched**

```bash
git commit -m "docs: document blueprint API in README"
```

---

## Spec Coverage Self-Review

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 独立表存储 | Task 2 |
| LLM generate 30s 独立配置 | Task 1, 5 |
| importance_level 枚举 | Task 2, 3, 5 |
| 1:1 source 绑定 | Task 4, 6 |
| Purge 级联 | Task 9 |
| API 全套 | Task 6, 7 |
| has_blueprint 树图标 | Task 8, 12 |
| 录入页三栏 + Tab | Task 12 |
| 列表/详情/编辑/删除 | Task 13 |
| 全部元信息字段 UI | Task 11 |
| 验收标准 13 项 | Task 14 smoke |
| 拖拽排序 Out of Scope | 未纳入 |
| parse_status 用 `ready` | Task 5 注释 |

无 TBD / 占位符。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-21-directory-blueprint.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间 review，迭代快
2. **Inline Execution** — 在本会话用 executing-plans 按 Task 批量执行，checkpoint Review

**Which approach?**

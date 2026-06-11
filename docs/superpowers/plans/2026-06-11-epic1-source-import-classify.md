# Epic 1 来源导入与文件分类确认 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付单文件导入闭环（上传 → 建议 → 人工确认 → 下游分流占位），含 API、来源导入中心 UI、任务日志与去重。

**Architecture:** 延续 Epic 0 monorepo。纵向切片 P0→P1→P2→P3。上传同步落盘返回 id；hash/建议走 BackgroundTasks + `import_tasks`。确认后写 `downstream_task_entries` 供 Epic 2/3 消费。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, python-multipart, pydantic-settings | React 18, Ant Design 5, Vite | pytest, httpx

**Design doc:** `docs/superpowers/specs/2026-06-11-epic1-source-import-classify-design.md`  
**Feature spec:** `specs/002-source-import-classify/spec.md`  
**Contracts:** `specs/002-source-import-classify/contracts/`

---

## File Map

| 路径 | 职责 |
|------|------|
| `docker-compose.yml` | 增加 `upload_data` volume + backend env |
| `backend/src/config.py` | `STORAGE_ROOT`, `LLM_API_KEY`, size limits |
| `backend/src/models/file_import.py` | FileImport ORM |
| `backend/src/models/file_purpose_suggestion.py` | 建议 ORM |
| `backend/src/models/import_task.py` | 任务 ORM |
| `backend/src/models/downstream_task_entry.py` | 下游占位 ORM |
| `backend/src/models/import_audit_log.py` | 导入审计 ORM |
| `backend/src/services/file_storage.py` | 流式存储 |
| `backend/src/services/file_hash.py` | SHA-256 |
| `backend/src/services/purpose_suggestion.py` | 规则 + 可选 LLM |
| `backend/src/services/duplicate_detection.py` | 去重 |
| `backend/src/services/file_import_service.py` | 上传编排 |
| `backend/src/services/confirm_service.py` | 确认/忽略/分流 |
| `backend/src/services/import_task_runner.py` | 后台任务 |
| `backend/src/api/routes/file_imports.py` | REST |
| `backend/tests/contract/test_file_import_api.py` | API 契约 |
| `backend/tests/integration/test_upload_confirm_flow.py` | 端到端 |
| `backend/tests/fixtures/sample-template.docx` | 测试文件 |
| `frontend/src/pages/FileImportCenter/` | 列表+上传+抽屉 |
| `frontend/src/services/fileImports.ts` | API client |

---

## Phase P0 — 导入基础设施

### Task P0-1: 配置与存储服务

**Files:**
- Create: `backend/src/config.py`
- Create: `backend/src/services/file_storage.py`
- Create: `backend/tests/unit/test_file_storage.py`
- Modify: `docker-compose.yml`
- Modify: `backend/pyproject.toml` (add `python-multipart`, `pydantic-settings` if missing)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_file_storage.py
from pathlib import Path
import pytest
from src.services.file_storage import FileStorage

def test_save_and_resolve_path(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    storage = FileStorage()
    rel = storage.save(
        kb_id="kb-1",
        import_id="imp-1",
        file_name="a.docx",
        stream=iter([b"hello"]),
    )
    assert rel == "kb-1/imp-1/a.docx"
    assert (tmp_path / rel).read_bytes() == b"hello"
```

- [ ] **Step 2: 运行确认 FAIL**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_file_storage.py -v
```

- [ ] **Step 3: 实现 `config.py` + `file_storage.py`**

```python
# backend/src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    storage_root: str = "data/uploads"
    llm_api_key: str | None = None
    max_file_size_docx_mb: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# backend/src/services/file_storage.py
from pathlib import Path
from uuid import UUID
from src.config import settings

class FileStorage:
    def __init__(self) -> None:
        self.root = Path(settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, kb_id: UUID, import_id: UUID, file_name: str, stream) -> str:
        rel = f"{kb_id}/{import_id}/{file_name}"
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in stream:
                f.write(chunk)
        return rel
```

- [ ] **Step 4: docker-compose 增加 volume**

```yaml
# docker-compose.yml services 下增加 backend 可选，或文档说明 STORAGE_ROOT 挂载：
volumes:
  pgdata:
  upload_data:
```

- [ ] **Step 5: 测试 PASS**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_file_storage.py -v
```

---

### Task P0-2: ORM 模型与 init_db

**Files:**
- Create: `backend/src/models/file_import.py`
- Create: `backend/src/models/file_purpose_suggestion.py`
- Create: `backend/src/models/import_task.py`
- Create: `backend/src/models/downstream_task_entry.py`
- Create: `backend/src/models/import_audit_log.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/models/classification_reference.py` (object_type 加 file_import)
- Modify: `backend/src/db/init_db.py`
- Create: `backend/tests/integration/test_file_import_model.py`

- [ ] **Step 1: 写模型集成测试**

```python
# backend/tests/integration/test_file_import_model.py
from uuid import uuid4
from src.models.file_import import FileImport, FileImportStatus, FileType

def test_create_file_import(db_session):
    kb_id = uuid4()
    imp = FileImport(
        kb_id=kb_id,
        file_name="t.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="x/y/t.docx",
        status=FileImportStatus.uploaded,
        created_by="admin",
    )
    db_session.add(imp)
    db_session.commit()
    assert imp.import_id is not None
```

- [ ] **Step 2: 实现模型**（字段见 `specs/002-source-import-classify/data-model.md`）

- [ ] **Step 3: 更新 init_db imports**

- [ ] **Step 4: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_file_import_model.py -v
```

---

### Task P0-3: 路由壳 + 空列表 API

**Files:**
- Create: `backend/src/api/routes/file_imports.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/contract/test_file_import_list_empty.py`

- [ ] **Step 1: 契约测试**

```python
from fastapi.testclient import TestClient
from src.main import app

def test_list_file_imports_empty(api_client, seeded_kb):
    kb_id = seeded_kb["kb_id"]
    client = TestClient(app)
    r = client.get(
        f"/api/v1/kbs/{kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []
```

- [ ] **Step 2: 实现 `GET /` 空列表 + router 注册**

- [ ] **Step 3: pytest PASS**

---

### Task P0-4: 前端壳层

**Files:**
- Create: `frontend/src/pages/FileImportCenter/index.tsx`
- Create: `frontend/src/services/fileImports.ts` (list stub)
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: 添加路由 `/file-imports` 与导航「来源导入」**

- [ ] **Step 2: 空 Table + KB 未选 Alert**

- [ ] **Step 3: `npm run build` 通过**

---

**Checkpoint P0:** 空列表可访问；模型可建；inactive KB 写操作 403（复用 `kb_write_guard`）。

---

## Phase P1 — 上传与规则建议

### Task P1-1: 文件校验与上传 API

**Files:**
- Modify: `backend/src/services/file_import_service.py` (create)
- Modify: `backend/src/api/routes/file_imports.py`
- Create: `backend/tests/fixtures/sample-template.docx` (最小 docx 或二进制占位)
- Create: `backend/tests/contract/test_file_import_upload.py`

- [ ] **Step 1: 上传契约测试**

```python
def test_upload_returns_import_id_quickly(api_client, seeded_kb, sample_docx_path):
    client = TestClient(app)
    with open(sample_docx_path, "rb") as f:
        r = client.post(
            f"/api/v1/kbs/{seeded_kb['kb_id']}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={"file": ("餐补模板.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert r.status_code == 201
    assert "import_id" in r.json()["data"]
```

- [ ] **Step 2: 实现 multipart 上传 + 零字节/非法扩展名 422**

- [ ] **Step 3: pytest PASS**

---

### Task P1-2: Hash + 规则建议 + BackgroundTasks

**Files:**
- Create: `backend/src/services/file_hash.py`
- Create: `backend/src/services/purpose_suggestion.py`
- Create: `backend/src/services/import_task_runner.py`
- Modify: `backend/src/api/routes/file_imports.py`
- Create: `backend/tests/unit/test_purpose_suggestion.py`

- [ ] **Step 1: 规则测试**

```python
from src.services.purpose_suggestion import suggest_from_filename

def test_template_keyword():
    r = suggest_from_filename("餐补模板.docx", "docx")
    assert r.suggested_purpose == "template_file"
    assert r.purpose_confidence >= 0.5
```

- [ ] **Step 2: 实现 hash + runner；上传后 enqueue BackgroundTask**

- [ ] **Step 3: 集成测试：GET detail 最终 `need_confirm` + suggestion 非空**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_purpose_suggestion.py tests/contract/test_file_import_upload.py -v
```

---

### Task P1-3: 列表/详情 API + 前端上传

**Files:**
- Modify: `backend/src/api/routes/file_imports.py` (GET detail)
- Modify: `frontend/src/services/fileImports.ts`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`

- [ ] **Step 1: GET list 分页 + GET detail 含 suggestion**

- [ ] **Step 2: Dragger 上传 + Table 刷新**

- [ ] **Step 3: 手动 quickstart 场景 1**

---

**Checkpoint P1:** 上传 docx 得 import_id；轮询见建议；列表可见记录。

---

## Phase P2 — 用途确认

### Task P2-1: confirm / ignore API

**Files:**
- Create: `backend/src/services/confirm_service.py`
- Modify: `backend/src/api/routes/file_imports.py`
- Create: `backend/tests/contract/test_file_import_confirm.py`

- [ ] **Step 1: 确认测试**

```python
def test_confirm_persists_purpose(api_client, seeded_kb, uploaded_need_confirm):
    imp_id = uploaded_need_confirm["import_id"]
    ver = uploaded_need_confirm["version"]
    r = client.post(
        f"/api/v1/kbs/{seeded_kb['kb_id']}/file-imports/{imp_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "expected_version": ver,
            "file_purpose": "template_file",
            "product_category_ids": [],
            "enter_parsing": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "confirmed"
```

- [ ] **Step 2: 实现 confirm + ignore + classification_reference 写入**

- [ ] **Step 3: 版本冲突 409 测试**

---

### Task P2-2: ConfirmDrawer UI

**Files:**
- Create: `frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`

- [ ] **Step 1: 抽屉展示建议 + 用途 Select + 分类 TreeSelect（调 Epic 0 API）**

- [ ] **Step 2: 保存/忽略；409 提示刷新**

- [ ] **Step 3: inactive KB 禁用按钮**

---

**Checkpoint P2:** 确认后 status=confirmed；忽略无 downstream；P95 确认 <1s（本地目测）。

---

## Phase P3 — 分流、去重、LLM、重试

### Task P3-1: downstream_task_entries

**Files:**
- Modify: `backend/src/services/confirm_service.py`
- Modify: `backend/src/api/routes/file_imports.py` (GET downstream-entries)
- Create: `backend/tests/integration/test_downstream_routing.py`

- [ ] **Step 1: template_file 确认后创建 `template_file_parse`**

- [ ] **Step 2: actual_bid 创建三条 task_type**

- [ ] **Step 3: ignore / enter_parsing=false 零条目**

---

### Task P3-2: 去重与新版本

**Files:**
- Create: `backend/src/services/duplicate_detection.py`
- Modify: `backend/src/services/file_import_service.py`
- Create: `frontend/src/pages/FileImportCenter/DuplicateFileModal.tsx`

- [ ] **Step 1: 第二次上传 409 DUPLICATE_FILE**

- [ ] **Step 2: `duplicate_action=new_version` 创建新 import + parent_import_id**

- [ ] **Step 3: Modal 跳过/新版本 UI**

---

### Task P3-3: 重试、任务日志、可选 LLM

**Files:**
- Modify: `backend/src/api/routes/file_imports.py` (retry, tasks)
- Modify: `backend/src/services/purpose_suggestion.py` (LLM branch)
- Create: `frontend/src/pages/FileImportCenter/TaskLogDrawer.tsx`

- [ ] **Step 1: GET tasks 返回 log_lines**

- [ ] **Step 2: POST retry 重新 enqueue classify**

- [ ] **Step 3: LLM_API_KEY 存在时 mock 测试；无 Key 纯规则**

---

### Task P3-4: quickstart 与文档

**Files:**
- Modify: `specs/002-source-import-classify/quickstart.md`
- Modify: `backend/tests/conftest.py` (fixtures: seeded_kb, uploaded_need_confirm)

- [ ] **Step 1: 跑通 quickstart 场景 1–5**

- [ ] **Step 2: 全量 pytest**

```bash
cd backend && ../.venv/bin/pytest -v
```

---

**Checkpoint P3:** Epic 2/3 可查询 pending downstream；重复流程通；任务可重试。

---

## Spec Coverage Checklist

| Spec FR | Task |
|---------|------|
| FR-001 单文件上传 | P1-1 |
| FR-004 快速返回 id | P1-1, P1-2 |
| FR-005/006 建议与人工优先 | P1-2, P2-1 |
| FR-007 确认前不解析 | P2-1 |
| FR-010 分流 | P3-1 |
| FR-011/012 去重 | P3-2 |
| FR-013 重试 | P3-3 |
| FR-015 任务日志 | P3-3 |
| FR-016 管理后台 | P0-4, P1-3, P2-2, P3-2, P3-3 |
| FR-020 Epic 0 分类 | P2-2 |

---

## Execution Handoff

Plan complete. Choose:

1. **Subagent-Driven (recommended)** — 每 Task 派生子 agent + 阶段评审  
2. **Inline Execution** — 本会话按 Task 批量执行 + checkpoint

实现时 REQUIRED: `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`。

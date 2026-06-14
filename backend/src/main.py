from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.audit import AuditMiddleware
from src.api.routes.actual_bid_parse import router as actual_bid_parse_router
from src.api.routes.bid_outlines import router as bid_outlines_router
from src.api.routes.candidate_audit_logs import router as candidate_audit_logs_router
from src.api.routes.candidate_batch import router as candidate_batch_router
from src.api.routes.candidates import router as candidates_router
from src.api.routes.chapter_patterns import router as chapter_patterns_router
from src.api.routes.chapter_taxonomies import router as chapter_taxonomy_router
from src.api.routes.file_imports import router as file_imports_router
from src.api.routes.knowledge_bases import router as kb_router
from src.api.routes.knowledge_units import router as knowledge_units_router
from src.api.routes.manual_assets import router as manual_assets_router
from src.api.routes.product_categories import router as product_category_router
from src.api.routes.template_assets import router as template_assets_router
from src.api.routes.template_chapters import router as template_chapters_router
from src.api.routes.template_libraries import router as template_libraries_router
from src.api.routes.template_parse import router as template_parse_router
from src.api.routes.templates import router as templates_router
from src.api.routes.wikis import router as wikis_router
from src.db.init_db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="tender_knowledge", version="0.1.0", lifespan=lifespan)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(kb_router)
app.include_router(product_category_router)
app.include_router(chapter_taxonomy_router)
app.include_router(file_imports_router)
app.include_router(template_parse_router)
app.include_router(template_libraries_router)
app.include_router(templates_router)
app.include_router(template_chapters_router)
app.include_router(template_assets_router)
app.include_router(actual_bid_parse_router)
app.include_router(bid_outlines_router)
app.include_router(candidates_router)
app.include_router(candidate_batch_router)
app.include_router(candidate_audit_logs_router)
app.include_router(knowledge_units_router)
app.include_router(wikis_router)
app.include_router(manual_assets_router)
app.include_router(chapter_patterns_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

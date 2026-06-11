from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.audit import AuditMiddleware
from src.api.routes.chapter_taxonomies import router as chapter_taxonomy_router
from src.api.routes.knowledge_bases import router as kb_router
from src.api.routes.product_categories import router as product_category_router
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

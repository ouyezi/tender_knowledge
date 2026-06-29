from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.audit import AuditMiddleware
from src.api.routes.blueprints import router as blueprints_router
from src.api.routes.dynamic_knowledge import router as dynamic_knowledge_router
from src.api.routes.file_imports import router as file_imports_router
from src.api.routes.knowledge_bases import router as kb_router
from src.api.routes.knowledge_chunks import router as knowledge_chunks_router
from src.api.routes.knowledge_taxonomy import router as knowledge_taxonomy_router
from src.api.routes.media import router as media_router
from src.api.routes.writing_techniques import router as writing_techniques_router
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
app.include_router(file_imports_router)
app.include_router(knowledge_chunks_router)
app.include_router(knowledge_taxonomy_router)
app.include_router(dynamic_knowledge_router)
app.include_router(blueprints_router)
app.include_router(writing_techniques_router)
app.include_router(media_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

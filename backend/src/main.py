from fastapi import FastAPI

from src.api.routes.knowledge_bases import router as kb_router

app = FastAPI(title="tender_knowledge", version="0.1.0")
app.include_router(kb_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

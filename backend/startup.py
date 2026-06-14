import os

import uvicorn

if __name__ == "__main__":
    reload = os.getenv("BACKEND_RELOAD", "0") == "1"
    if not reload:
        # Run schema sync before binding :8000 so /health is ready as soon as the port opens.
        from src.db.init_db import init_db

        init_db()
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=reload)

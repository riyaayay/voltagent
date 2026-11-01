"""Root launcher for Hugging Face Space (Gradio SDK launcher).

Mounts frontend/ static assets at "/" on top of the VoltAgent FastAPI app,
running on host 0.0.0.0, port 7860.
"""
from __future__ import annotations

import os
from pathlib import Path
import uvicorn
from fastapi.staticfiles import StaticFiles

from voltagent.api.main import app

# Mount frontend/ static files at "/"
frontend_dir = Path(__file__).resolve().parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, reload=False)

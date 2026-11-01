"""Root launcher for Hugging Face Space (Gradio SDK launcher).

Mounts frontend/ static assets at "/" on top of the VoltAgent FastAPI app,
running on host 0.0.0.0, port 7860.
"""
from __future__ import annotations

import os
from pathlib import Path

# Disable Gradio MCP server which attempts to bind to secondary port 7861
os.environ["GRADIO_MCP_SERVER"] = "false"

from fastapi.staticfiles import StaticFiles
import uvicorn

from voltagent.api.main import app

# ZeroGPU startup check compliance (needed if Space hardware is set to ZeroGPU)
try:
    import spaces

    @spaces.GPU
    def _zerogpu_marker(text: str) -> str:
        return text
except ImportError:
    def _zerogpu_marker(text: str) -> str:
        return text

try:
    import gradio as gr

    demo = gr.Interface(fn=_zerogpu_marker, inputs="text", outputs="text", title="VoltAgent Space")
    try:
        app = gr.mount_gradio_app(app, demo, path="/_gradio", mcp_server=False)
    except TypeError:
        app = gr.mount_gradio_app(app, demo, path="/_gradio")
except Exception:
    pass

# Mount frontend/ static files at "/"
frontend_dir = Path(__file__).resolve().parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, reload=False)

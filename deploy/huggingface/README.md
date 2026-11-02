# Hugging Face Spaces Deployment (Parked)

**Status:** Parked (ZeroGPU incompatible).

Hugging Face Spaces ZeroGPU infrastructure requires dynamic GPU allocation decorated via `@spaces.GPU` in a Gradio UI, which does not fit VoltAgent's sub-15ms CPU-based hybrid retrieval, LangGraph pipeline, and FastAPI/HTML5 Web Speech frontend.

The files in this directory are preserved for reference:
- `app.py`: Gradio/Uvicorn launcher
- `SPACES_README.md`: Gradio Space configuration card
- `demo/`: Text extraction fixture for OSHA 3075 safety manual


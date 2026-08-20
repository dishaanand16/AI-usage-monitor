from fastapi import FastAPI
from app.routers import prompts, agent_runs

app = FastAPI(
    title="FLYYY.AI Usage Monitoring",
    description="Observes, sanitizes, and analyzes real AI usage across an org.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
app.include_router(agent_runs.router, prefix="/runs", tags=["runs"])

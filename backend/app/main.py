from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import prompts, agent_runs

app = FastAPI(
    title="FLYYY.AI Usage Monitoring",
    description="Observes, sanitizes, and analyzes real AI usage across an org.",
    version="0.1.0",
)

# Allow the React dev server (and any local frontend) to call this API.
# In production this would be scoped to the actual deployed frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
app.include_router(agent_runs.router, prefix="/runs", tags=["runs"])

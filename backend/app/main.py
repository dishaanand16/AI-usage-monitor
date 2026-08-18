from fastapi import FastAPI

# Routers filled in on Day 2/3:
#   prompts.py   -> capture + sanitize + store + search
#   assets.py    -> AI asset registry + PII summary
#   agent_runs.py -> declared vs observed data-source access

app = FastAPI(
    title="FLYYY.AI Usage Monitoring",
    description="Observes, sanitizes, and analyzes real AI usage across an org.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


# app.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
# app.include_router(assets.router, prefix="/assets", tags=["assets"])
# app.include_router(agent_runs.router, prefix="/runs", tags=["runs"])

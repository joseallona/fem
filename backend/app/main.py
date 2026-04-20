import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import briefs, jobs, projects, runs, scenario_pipeline, scenarios, settings, signals, sources, themes

logger = logging.getLogger(__name__)

app = FastAPI(title="Forecasting Engine Monitor API", version="0.1.0")


@app.on_event("startup")
def on_startup():
    try:
        from app.services.scheduler import setup_daily_schedules
        setup_daily_schedules()
    except Exception as e:
        logger.warning("Scheduler setup skipped (Redis may not be ready): %s", e)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(themes.router)
app.include_router(sources.router)
app.include_router(signals.router)
app.include_router(scenarios.router)
app.include_router(scenario_pipeline.router)
app.include_router(briefs.router)
app.include_router(runs.router)
app.include_router(jobs.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    return {"status": "ok"}

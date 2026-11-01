"""
BattLab — FastAPI Main Application
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import library, projects, simulations, compare_reports

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("battlab")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BattLab starting up — initialising database …")
    init_db()
    logger.info("Database ready.")
    yield
    logger.info("BattLab shutting down.")


APP_VERSION = "0.2.0-beta"

app = FastAPI(
    title="BattLab API",
    version=APP_VERSION,
    description=(
        "BattLab Virtual Battery Design Platform API. "
        "This is a prototype engineering screening tool. "
        "Results are not experimental measurements and do not constitute "
        "a safety certification or manufacturing approval."
    ),
    lifespan=lifespan,
)

# Robust CORS configuration supporting local dev, Netlify previews, and custom production domains
ALLOWED_ORIGINS_ENV = os.environ.get("ALLOWED_ORIGINS", "")
raw_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if ALLOWED_ORIGINS_ENV:
    raw_origins.extend([o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()])

if "*" in raw_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=raw_origins,
        allow_origin_regex=r"https://.*\.netlify\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(library.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(simulations.router, prefix="/api")
app.include_router(compare_reports.router, prefix="/api")

from fastapi import Depends
from sqlmodel import Session
from app.database import engine
from app.schemas import ConfigurationRead, ConfigurationUpdate
from app.api.projects import get_configuration, update_configuration, get_session


@app.get("/api/configurations/{configuration_id}", response_model=ConfigurationRead, tags=["configurations"])
def get_configuration_endpoint(configuration_id: int, session: Session = Depends(get_session)):
    return get_configuration(configuration_id, session)


@app.patch("/api/configurations/{configuration_id}", response_model=ConfigurationRead, tags=["configurations"])
def patch_configuration_endpoint(configuration_id: int, body: ConfigurationUpdate, session: Session = Depends(get_session)):
    return update_configuration(configuration_id, body, session)



@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "BattLab API",
        "version": APP_VERSION,
        "disclaimer": (
            "This is a prototype engineering screening tool. "
            "Results are not experimental measurements."
        ),
    }

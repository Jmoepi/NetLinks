"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db as app_db
from app.db import init_db

logger = logging.getLogger("uvicorn.error")


def seed_if_empty() -> None:
    """Seed the demo data on first start (empty smes table). Logs and continues on failure."""
    from app.services.seed import is_seeded, seed

    session = app_db.SessionLocal()
    try:
        if is_seeded(session):
            logger.info("Seed skipped: database already has demo data.")
            return
        counts = seed(session)
        session.commit()
        logger.info("Seed completed: %s", counts)
    except Exception:
        session.rollback()
        logger.exception("Seed failed; the API is running without demo data.")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    seed_if_empty()
    yield


app = FastAPI(title="NetLinks API", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

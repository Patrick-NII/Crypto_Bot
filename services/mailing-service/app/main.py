"""Okamoey Mailing Service — FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.mail import router as mail_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Mailing Service starting — SMTP=%s:%s", settings.SMTP_HOST, settings.SMTP_PORT)
    yield
    logger.info("Mailing Service shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mail_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}

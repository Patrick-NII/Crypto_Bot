"""GlueTrade Auth Service -- FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.internal import router as internal_router
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup / shutdown tasks.

    On startup the database tables are created (if they don't already exist).
    """
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# ---- Middleware -----------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers --------------------------------------------------------------

app.include_router(auth_router)
app.include_router(internal_router)


# ---- Health check ----------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check():
    """Return service health status."""
    return {"status": "healthy", "service": settings.APP_NAME}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.proxy import router as proxy_router

app = FastAPI(
    title="Okamoey API Gateway",
    description="Single entry-point reverse proxy for the Okamoey trading platform.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Middleware (applied bottom-up: rate limit runs first, then auth, then CORS)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(proxy_router)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {
        "service": "Okamoey API Gateway",
        "version": "1.0.0",
        "docs": "/docs",
    }

from fastapi import FastAPI

from app.api.ml import router as ml_router
from app.api.ml_v2 import router as ml_v2_router
from app.api.scanner import router as scanner_router

app = FastAPI(
    title="ML Service",
    description="Signal engine, multi-asset scanner, and strategy ranking",
    version="1.0.0",
)

app.include_router(ml_router)
app.include_router(ml_v2_router)
app.include_router(scanner_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8006, reload=True)

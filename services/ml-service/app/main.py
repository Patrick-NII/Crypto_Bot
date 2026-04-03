from fastapi import FastAPI

from app.api.ml import router as ml_router

app = FastAPI(
    title="ML Service",
    description="Machine learning signals, backtesting, and model management",
    version="0.1.0",
)

app.include_router(ml_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8006, reload=True)

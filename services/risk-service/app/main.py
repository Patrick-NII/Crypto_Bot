from fastapi import FastAPI

from app.api.risk import router as risk_router

app = FastAPI(
    title="Risk Service",
    description="Portfolio risk management and trade evaluation",
    version="0.1.0",
)

app.include_router(risk_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "risk-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True)

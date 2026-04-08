import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.alerts import router as alerts_router
from app.api.notifications import router as notifications_router
from app.core.config import settings
from app.services.email_dispatcher import get_dispatcher
from app.services.recap_scheduler import get_scheduler
from app.services.telegram import format_alert, send_message

logger = logging.getLogger(__name__)


async def redis_subscriber():
    """Listen for notification events on Redis pub/sub."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(f"redis://{settings.REDIS_HOST}:6379")
        pubsub = r.pubsub()
        await pubsub.subscribe("notifications")

        logger.info("Redis subscriber started, listening on 'notifications' channel")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    alert_type = data.get("alert_type", "system")
                    chat_id = data.get("chat_id", settings.TELEGRAM_CHAT_ID)
                    if chat_id:
                        text = format_alert(alert_type, data.get("data", {}))
                        await send_message(chat_id=chat_id, text=text)
                except (json.JSONDecodeError, Exception) as e:
                    logger.error("Error processing notification: %s", e)
    except Exception as e:
        logger.warning("Redis subscriber failed to start (Redis may not be available): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the Redis subscriber, email dispatcher, and recap scheduler."""
    task = asyncio.create_task(redis_subscriber())

    dispatcher = get_dispatcher()
    await dispatcher.start()

    scheduler = get_scheduler()
    scheduler.start()

    logger.info("Notification service started")
    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    await dispatcher.stop()
    scheduler.stop()
    logger.info("Notification service stopped")


app = FastAPI(
    title="Notification Service",
    description="Alerts and notifications via Telegram and other channels",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(notifications_router)
app.include_router(alerts_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "notification-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8007, reload=True)

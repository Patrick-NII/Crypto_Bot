import time

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    decode_responses=True,
                )
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        redis = await self._get_redis()

        # If Redis is unavailable, let the request through rather than blocking
        if redis is None:
            return await call_next(request)

        client_ip = self._client_ip(request)
        now = time.time()
        window = 60  # 1 minute
        limit = settings.RATE_LIMIT_PER_MINUTE
        key = f"rate_limit:{client_ip}"

        try:
            pipe = redis.pipeline()
            # Remove entries outside the sliding window
            pipe.zremrangebyscore(key, 0, now - window)
            # Add the current request timestamp
            pipe.zadd(key, {str(now): now})
            # Count requests in the window
            pipe.zcard(key)
            # Set expiry on the key so it auto-cleans
            pipe.expire(key, window)
            results = await pipe.execute()

            request_count = results[2]
            remaining = max(0, limit - request_count)
            reset_at = int(now + window)

            if request_count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_at),
                        "Retry-After": str(window),
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_at)
            return response

        except Exception:
            # On any Redis error, fail open
            return await call_next(request)

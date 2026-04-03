from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.config import settings

PUBLIC_ROUTES = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
]


def _is_public(path: str) -> bool:
    for route in PUBLIC_ROUTES:
        if path == route or path.startswith(route + "/"):
            return True
    # Allow the root path
    if path == "/":
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_public(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header",
            )

        token = auth_header.split(" ", 1)[1]

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token missing subject")

        request.state.user_id = user_id

        return await call_next(request)

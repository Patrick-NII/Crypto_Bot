import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

from app.core.config import settings
from typing import Dict, List, Optional

router = APIRouter()

# Map URL prefixes to upstream service base URLs
ROUTE_TABLE: List[tuple[str, str]] = [
    ("/api/v1/auth", settings.AUTH_SERVICE_URL),
    ("/api/v1/portfolios", settings.PORTFOLIO_SERVICE_URL),
    ("/api/v1/positions", settings.PORTFOLIO_SERVICE_URL),
    ("/api/v1/prices", settings.MARKET_DATA_SERVICE_URL),
    ("/api/v1/markets", settings.MARKET_DATA_SERVICE_URL),
    ("/api/v1/trades", settings.TRADING_ENGINE_URL),
    ("/api/v1/orders", settings.TRADING_ENGINE_URL),
    ("/api/v1/risk", settings.RISK_SERVICE_URL),
    ("/api/v1/ml", settings.ML_SERVICE_URL),
    ("/api/v1/notifications", settings.NOTIFICATION_SERVICE_URL),
    ("/api/v1/alerts", settings.NOTIFICATION_SERVICE_URL),
    ("/api/v1/news", settings.NEWS_SERVICE_URL),
]


def _resolve_upstream(path: str) -> Optional[tuple[str, str]]:
    """Return (upstream_base_url, remaining_path) for the given request path."""
    for prefix, upstream_url in ROUTE_TABLE:
        if path == prefix or path.startswith(prefix + "/"):
            remaining = path[len(prefix):]
            return upstream_url, remaining
    return None


def _forwarded_headers(request: Request) -> Dict[str, str]:
    """Build headers to forward upstream, stripping hop-by-hop headers."""
    skip = {"host", "connection", "keep-alive", "transfer-encoding"}
    return {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in skip
    }


@router.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(request: Request, path: str):
    full_path = f"/api/v1/{path}"
    resolved = _resolve_upstream(full_path)

    if resolved is None:
        raise HTTPException(status_code=404, detail="Route not found")

    upstream_base, remaining_path = resolved
    upstream_url = f"{upstream_base}{full_path}"

    # Preserve query string
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    headers = _forwarded_headers(request)
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=settings.PROXY_TIMEOUT) as client:
            upstream_response = await client.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=body,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gateway timeout: upstream service did not respond in time")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Service unavailable: could not connect to upstream service")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Bad gateway: {exc}")

    # Filter out hop-by-hop response headers
    skip_response = {"transfer-encoding", "connection", "keep-alive"}
    response_headers = {
        k: v
        for k, v in upstream_response.headers.items()
        if k.lower() not in skip_response
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )

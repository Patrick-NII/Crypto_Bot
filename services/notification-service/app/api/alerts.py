from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class Alert(BaseModel):
    id: str = ""
    alert_type: str = "price"
    symbol: str = ""
    condition: str = ""
    target_value: float = 0.0
    enabled: bool = True
    created_at: str = ""


class CreateAlertRequest(BaseModel):
    alert_type: str = "price"
    symbol: str = ""
    condition: str = "above"
    target_value: float = 0.0


@router.get("/", response_model=list[Alert])
async def list_alerts():
    """List alerts (stub: returns empty list)."""
    return []


@router.post("/", response_model=Alert, status_code=status.HTTP_201_CREATED)
async def create_alert(request: CreateAlertRequest):
    """Create alert (stub: returns created alert)."""
    return Alert(
        id=str(uuid4()),
        alert_type=request.alert_type,
        symbol=request.symbol,
        condition=request.condition,
        target_value=request.target_value,
        enabled=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: str):
    """Delete alert (stub: returns 204)."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)

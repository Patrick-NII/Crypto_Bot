"""Agents API — list available agents and their capabilities."""

from fastapi import APIRouter

from app.agents.registry import list_agents

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/agents")
async def get_agents() -> list[dict]:
    """List all available AI agents."""
    return list_agents()

"""Chat API — main endpoint for AI agent conversations."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.agents.registry import get_agent
from app.core.llm_router import chat_completion, classify_complexity, Complexity
from app.memory.conversation import get_history, append_message, clear_history
from app.services.context_builder import build_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    agent_type: str = Field(default="dashboard")
    user_id: str = Field(default="default")
    complexity_override: Complexity | None = Field(default=None)


class ChatResponse(BaseModel):
    reply: str
    agent_type: str
    agent_name: str
    provider: str
    model: str
    complexity: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Send a message to an AI agent and get a response."""
    try:
        agent = get_agent(req.agent_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {req.agent_type}")

    # Build context from live services
    context = await build_context(req.agent_type, req.user_id)

    # Build system prompt with context
    system_prompt = agent.build_system_prompt(context)

    # Get conversation history
    history = await get_history(req.user_id, req.agent_type)

    # Add user message to history
    await append_message(req.user_id, req.agent_type, "user", req.message)

    # Prepare messages for LLM
    messages = history + [{"role": "user", "content": req.message}]

    # Determine complexity
    complexity = req.complexity_override or classify_complexity(req.message)

    # Call LLM
    try:
        reply, provider, model = await chat_completion(messages, system_prompt, complexity)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Save assistant response
    await append_message(req.user_id, req.agent_type, "assistant", reply)

    return ChatResponse(
        reply=reply,
        agent_type=req.agent_type,
        agent_name=agent.config.name,
        provider=provider,
        model=model,
        complexity=complexity.value,
    )


class ClearRequest(BaseModel):
    agent_type: str = Field(default="dashboard")
    user_id: str = Field(default="default")


@router.post("/chat/clear")
async def clear_chat(req: ClearRequest) -> dict:
    """Clear conversation history for a user+agent pair."""
    await clear_history(req.user_id, req.agent_type)
    return {"status": "cleared", "agent_type": req.agent_type}

"""Chat API — main endpoint for AI agent conversations."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request

from app.agents.registry import get_agent
from app.core.auth import resolve_user_id_from_auth_header
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
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    """Send a message to an AI agent and get a response."""
    auth_header = request.headers.get("Authorization")
    effective_user_id = (
        resolve_user_id_from_auth_header(auth_header)
        if auth_header
        else req.user_id
    )

    try:
        agent = get_agent(req.agent_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {req.agent_type}")

    # Build context from live services
    context = await build_context(
        req.agent_type,
        effective_user_id,
        auth_header,
    )

    # Build system prompt with context
    system_prompt = agent.build_system_prompt(context)

    # Get conversation history
    history = await get_history(effective_user_id, req.agent_type)

    # Add user message to history
    await append_message(effective_user_id, req.agent_type, "user", req.message)

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
    await append_message(effective_user_id, req.agent_type, "assistant", reply)

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
async def clear_chat(req: ClearRequest, request: Request) -> dict:
    """Clear conversation history for a user+agent pair."""
    auth_header = request.headers.get("Authorization")
    effective_user_id = (
        resolve_user_id_from_auth_header(auth_header)
        if auth_header
        else req.user_id
    )
    await clear_history(effective_user_id, req.agent_type)
    return {"status": "cleared", "agent_type": req.agent_type}


class PerformanceAnalysisRequest(BaseModel):
    metrics: dict = Field(..., description="User performance metrics")


PERF_SYSTEM_PROMPT = """Tu es un analyste expert crypto pour la plateforme GlueTrade.
Analyse les métriques du portfolio et donne un briefing concis EN FRANÇAIS.

RÈGLES STRICTES :
- Réponse de 1200 caractères MAXIMUM, pas plus.
- Pas de markdown headers (##), pas de listes à puces.
- Utilise des paragraphes courts et directs.
- Structure en 4 blocs séparés par un saut de ligne :

SITUATION : État actuel du portfolio en 1-2 phrases avec les chiffres clés.

DYNAMIQUE : Tendance 24h, momentum, sentiment marché (fear/greed).

OPPORTUNITÉS & RISQUES : Ce qu'il faut surveiller, actions à envisager.

CONSEIL : Une recommandation concrète et actionnable.

Sois direct, précis, utilise les vrais chiffres fournis. Pas de blabla."""


@router.post("/analyze-performance")
async def analyze_performance(req: PerformanceAnalysisRequest) -> dict:
    """Analyze user trading performance and generate AI advice."""
    context = f"User trading performance metrics:\n{req.metrics}"
    messages = [{"role": "user", "content": context}]

    try:
        reply, provider, model = await chat_completion(
            messages, PERF_SYSTEM_PROMPT, Complexity.COMPLEX
        )
        return {
            "analysis": reply,
            "provider": provider,
            "model": model,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

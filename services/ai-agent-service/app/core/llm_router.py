"""LLM Router — Routes requests to OpenAI models based on complexity.

Uses OPENAI_API_KEY from environment. Falls back between tiers on error.
Anthropic is optional fallback if ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import logging
from enum import Enum

import openai

from app.core.config import settings

logger = logging.getLogger(__name__)


class Complexity(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    COMPLEX = "complex"


COMPLEX_KEYWORDS = {
    "strategy", "optimize", "backtest", "rebalance", "correlation",
    "sharpe", "drawdown", "risk-adjusted", "monte carlo", "portfolio optimization",
    "multi-asset", "hedge", "derivative", "options pricing",
}

MEDIUM_KEYWORDS = {
    "analyze", "compare", "suggest", "recommend", "explain why",
    "trend", "signal", "divergence", "support", "resistance",
    "allocation", "diversif", "performance",
}


def classify_complexity(message: str) -> Complexity:
    lower = message.lower()
    word_count = len(message.split())
    if word_count > 100 or any(kw in lower for kw in COMPLEX_KEYWORDS):
        return Complexity.COMPLEX
    if word_count > 30 or any(kw in lower for kw in MEDIUM_KEYWORDS):
        return Complexity.MEDIUM
    return Complexity.FAST


def _model_for(complexity: Complexity) -> str:
    if complexity == Complexity.FAST:
        return settings.MODEL_FAST
    if complexity == Complexity.MEDIUM:
        return settings.MODEL_MEDIUM
    return settings.MODEL_COMPLEX

_openai_client: openai.AsyncOpenAI | None = None


def _get_openai() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _is_anthropic_model(model: str) -> bool:
    return model.startswith("claude")


async def _call_openai(messages: list[dict], system_prompt: str, model: str) -> str:
    client = _get_openai()
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    resp = await client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=0.7,
        max_tokens=2048,
    )
    return resp.choices[0].message.content or ""


async def _call_anthropic(messages: list[dict], system_prompt: str, model: str) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    resp = await client.messages.create(
        model=model,
        system=system_prompt,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )
    return resp.content[0].text


async def _call_model(messages: list[dict], system_prompt: str, model: str) -> tuple[str, str, str]:
    if _is_anthropic_model(model):
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(f"Anthropic model requested but ANTHROPIC_API_KEY is missing: {model}")
        text = await _call_anthropic(messages, system_prompt, model)
        return text, "anthropic", model

    text = await _call_openai(messages, system_prompt, model)
    return text, "openai", model


async def chat_completion(
    messages: list[dict],
    system_prompt: str,
    complexity: Complexity | None = None,
) -> tuple[str, str, str]:
    """Send messages to the appropriate OpenAI model.

    Returns (response_text, provider, model_id).
    Falls back to lower tier on error.
    """
    if complexity is None:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        complexity = classify_complexity(last_user)

    model = _model_for(complexity)

    # Try primary model
    try:
        return await _call_model(messages, system_prompt, model)
    except Exception as e:
        logger.warning("Primary model %s failed: %s — trying fallback", model, e)

    # Fallback: try fast tier
    try:
        fallback_model = settings.MODEL_FAST
        return await _call_model(messages, system_prompt, fallback_model)
    except Exception as e:
        logger.warning("Fast-tier fallback failed: %s", e)

    # Last resort: Anthropic if key is set
    if settings.ANTHROPIC_API_KEY:
        try:
            final_model = settings.MODEL_COMPLEX if _is_anthropic_model(settings.MODEL_COMPLEX) else "claude-sonnet-4-20250514"
            text = await _call_anthropic(messages, system_prompt, final_model)
            return text, "anthropic", final_model
        except Exception as e2:
            logger.error("Anthropic fallback also failed: %s", e2)

    raise RuntimeError("All LLM providers unavailable")

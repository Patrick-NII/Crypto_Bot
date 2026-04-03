"""LLM Router - Routes requests to the appropriate model based on complexity."""

from __future__ import annotations

import logging
from enum import Enum

import anthropic
import openai

from app.core.config import settings

logger = logging.getLogger(__name__)


class Complexity(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    COMPLEX = "complex"


# Keywords that indicate higher complexity
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
    """Classify message complexity to route to appropriate LLM."""
    lower = message.lower()
    word_count = len(message.split())

    # Long messages with analysis keywords -> complex
    if word_count > 100 or any(kw in lower for kw in COMPLEX_KEYWORDS):
        return Complexity.COMPLEX

    # Medium-length or analytical -> medium
    if word_count > 30 or any(kw in lower for kw in MEDIUM_KEYWORDS):
        return Complexity.MEDIUM

    return Complexity.FAST


def _get_model_for_complexity(complexity: Complexity) -> tuple[str, str]:
    """Return (provider, model_id) for a given complexity level."""
    if complexity == Complexity.FAST:
        return "openai", settings.MODEL_FAST
    elif complexity == Complexity.MEDIUM:
        return "openai", settings.MODEL_MEDIUM
    else:
        return "anthropic", settings.MODEL_COMPLEX


_openai_client: openai.AsyncOpenAI | None = None
_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_openai() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


async def chat_completion(
    messages: list[dict],
    system_prompt: str,
    complexity: Complexity | None = None,
) -> tuple[str, str, str]:
    """
    Send messages to the appropriate LLM.

    Returns (response_text, provider, model_id).
    Falls back to a different provider on error.
    """
    if complexity is None:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        complexity = classify_complexity(last_user)

    provider, model_id = _get_model_for_complexity(complexity)

    try:
        if provider == "openai":
            return await _call_openai(messages, system_prompt, model_id), provider, model_id
        else:
            return await _call_anthropic(messages, system_prompt, model_id), provider, model_id
    except Exception as e:
        logger.warning("Primary LLM (%s/%s) failed: %s — falling back", provider, model_id, e)
        # Fallback: swap provider
        try:
            if provider == "openai":
                fb_model = settings.MODEL_COMPLEX
                return await _call_anthropic(messages, system_prompt, fb_model), "anthropic", fb_model
            else:
                fb_model = settings.MODEL_MEDIUM
                return await _call_openai(messages, system_prompt, fb_model), "openai", fb_model
        except Exception as e2:
            logger.error("Fallback LLM also failed: %s", e2)
            raise RuntimeError("All LLM providers unavailable") from e2


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
    client = _get_anthropic()
    resp = await client.messages.create(
        model=model,
        system=system_prompt,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )
    return resp.content[0].text

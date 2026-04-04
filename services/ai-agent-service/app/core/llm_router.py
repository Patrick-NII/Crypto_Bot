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


# Model tiers — all OpenAI
MODELS = {
    Complexity.FAST: "gpt-4o-mini",
    Complexity.MEDIUM: "gpt-4o",
    Complexity.COMPLEX: "gpt-4o",
}

_openai_client: openai.AsyncOpenAI | None = None


def _get_openai() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


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

    model = MODELS[complexity]

    # Try primary model
    try:
        text = await _call_openai(messages, system_prompt, model)
        return text, "openai", model
    except Exception as e:
        logger.warning("OpenAI %s failed: %s — trying fallback", model, e)

    # Fallback: try gpt-4o-mini
    try:
        text = await _call_openai(messages, system_prompt, "gpt-4o-mini")
        return text, "openai", "gpt-4o-mini"
    except Exception as e:
        logger.warning("OpenAI fallback failed: %s", e)

    # Last resort: Anthropic if key is set
    if settings.ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await client.messages.create(
                model="claude-sonnet-4-20250514",
                system=system_prompt,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )
            return resp.content[0].text, "anthropic", "claude-sonnet-4-20250514"
        except Exception as e2:
            logger.error("Anthropic fallback also failed: %s", e2)

    raise RuntimeError("All LLM providers unavailable")

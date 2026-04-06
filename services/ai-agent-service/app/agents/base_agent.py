"""Base agent class with system prompt and context injection."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    agent_type: str
    name: str
    description: str
    system_prompt: str
    capabilities: list[str] = field(default_factory=list)


class BaseAgent:
    """Base class for all page-specific agents."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def build_system_prompt(self, context: str) -> str:
        """Combine the agent's system prompt with live context data."""
        base = (
            f"You are {self.config.name}, an AI assistant for the GlueTrade crypto trading platform.\n"
            f"Role: {self.config.description}\n\n"
            f"{self.config.system_prompt}\n\n"
        )
        if context:
            base += f"## Current Live Data\n{context}\n\n"
        base += (
            "## Guidelines\n"
            "- Be concise and actionable\n"
            "- Use numbers and data to support your points\n"
            "- When suggesting trades, always mention associated risks\n"
            "- Format responses in markdown for readability\n"
            "- If you don't have enough data, say so clearly\n"
        )
        return base

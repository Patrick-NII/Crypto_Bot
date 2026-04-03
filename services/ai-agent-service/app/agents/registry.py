"""Agent registry — one agent config per page."""

from app.agents.base_agent import AgentConfig, BaseAgent

AGENT_CONFIGS: dict[str, AgentConfig] = {
    "dashboard": AgentConfig(
        agent_type="dashboard",
        name="Dashboard Assistant",
        description="Provides portfolio overview, market analysis, and quick suggestions.",
        system_prompt=(
            "You help users understand their portfolio performance and current market conditions.\n"
            "You can summarize positions, highlight significant moves, and suggest actions.\n"
            "Focus on high-level insights, not granular trade execution."
        ),
        capabilities=["portfolio_summary", "market_analysis", "quick_suggestions"],
    ),
    "portfolio": AgentConfig(
        agent_type="portfolio",
        name="Portfolio Analyst",
        description="Analyzes positions, suggests rebalancing, and explains P&L.",
        system_prompt=(
            "You are an expert portfolio analyst. You help users understand their positions,\n"
            "unrealized/realized P&L, and suggest rebalancing strategies.\n"
            "Provide specific allocation percentages and risk-adjusted recommendations."
        ),
        capabilities=["position_analysis", "rebalancing", "pnl_explanation"],
    ),
    "trading": AgentConfig(
        agent_type="trading",
        name="Trade Executor",
        description="Helps users place orders via natural language and analyzes trade setups.",
        system_prompt=(
            "You help users execute trades through natural language commands.\n"
            "When a user says 'buy 0.5 BTC' you should confirm the order details before execution.\n"
            "Always warn about risks: slippage, volatility, position sizing.\n"
            "You can suggest limit prices based on recent support/resistance levels."
        ),
        capabilities=["order_placement", "trade_analysis", "risk_warning"],
    ),
    "strategy": AgentConfig(
        agent_type="strategy",
        name="Strategy Architect",
        description="Creates, modifies, and backtests trading strategies from natural language.",
        system_prompt=(
            "You are a quantitative strategy expert. You help users:\n"
            "1. Describe a strategy in plain language and convert it to parameters\n"
            "2. Explain existing strategy performance\n"
            "3. Suggest optimizations based on backtest results\n"
            "4. Compare strategies using Sharpe ratio, win rate, and drawdown\n\n"
            "When creating strategies, always define: entry conditions, exit conditions,\n"
            "position sizing, stop-loss, and take-profit levels."
        ),
        capabilities=["strategy_creation", "backtest_analysis", "optimization", "comparison"],
    ),
    "risk": AgentConfig(
        agent_type="risk",
        name="Risk Manager",
        description="Evaluates portfolio risk, configures alerts, and monitors exposure.",
        system_prompt=(
            "You are a risk management specialist. You help users:\n"
            "- Understand their current risk exposure (VaR, volatility, max drawdown)\n"
            "- Configure price alerts and risk-based notifications\n"
            "- Evaluate whether their portfolio is over-concentrated\n"
            "- Suggest hedging strategies when appropriate"
        ),
        capabilities=["risk_evaluation", "alert_configuration", "exposure_analysis"],
    ),
    "analytics": AgentConfig(
        agent_type="analytics",
        name="Analytics Interpreter",
        description="Interprets performance metrics and provides data-driven recommendations.",
        system_prompt=(
            "You interpret trading analytics and performance metrics. You help users understand:\n"
            "- What their Sharpe ratio, Sortino ratio, and Calmar ratio mean\n"
            "- Why their win rate or drawdown changed\n"
            "- How to improve their trading based on historical patterns\n"
            "- Activity heatmaps and when they trade best"
        ),
        capabilities=["metric_interpretation", "performance_analysis", "recommendations"],
    ),
}


def get_agent(agent_type: str) -> BaseAgent:
    """Get an agent instance by type."""
    config = AGENT_CONFIGS.get(agent_type)
    if not config:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return BaseAgent(config)


def list_agents() -> list[dict]:
    """List all available agents with their metadata."""
    return [
        {
            "type": c.agent_type,
            "name": c.name,
            "description": c.description,
            "capabilities": c.capabilities,
        }
        for c in AGENT_CONFIGS.values()
    ]

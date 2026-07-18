# TradingAgents/graph/conditional_logic.py

from ..agents.utils.agent_states import AgentState


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        # Check if analyst needs tools (indicated by temp state key)
        if state.get("_market_context"):
            return "tools_market"
        # Report is complete, move to next step (determined by graph edges)
        return "complete"

    def should_continue_social(self, state: AgentState):
        """Determine if social media analysis should continue."""
        if state.get("_social_context"):
            return "tools_social"
        return "complete"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        if state.get("_news_context"):
            return "tools_news"
        return "complete"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        if state.get("_fundamentals_context"):
            return "tools_fundamentals"
        return "complete"

    def should_continue_technical(self, state: AgentState):
        """Determine if technical analysis should continue."""
        if state.get("_technical_context"):
            return "tools_technical"
        return "complete"

    def should_continue_sec(self, state: AgentState):
        """Determine if SEC analysis should continue."""
        if state.get("_sec_context"):
            return "tools_sec"
        return "complete"

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if the Bull/Bear/Neutral debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 3 * self.max_debate_rounds
        ):  # one round = one turn each for Bull, Bear, Neutral
            return "Research Manager"
        latest_speaker = state["investment_debate_state"].get("latest_speaker", "")
        if latest_speaker.startswith("Bull"):
            return "Bear Researcher"
        if latest_speaker.startswith("Bear"):
            return "Neutral Researcher"
        return "Bull Researcher"

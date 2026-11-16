# TradingAgents/graph/conditional_logic.py

from ..agents.utils.agent_states import AgentState


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds

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

# TradingAgents/graph/propagation.py

from typing import Dict, Any
from ..agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self, company_name: str, trade_date: str
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        return {
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),
            "events_report": "",
            "prior_reports": {},
            "prior_analysis_date": "",
            "investment_debate_state": InvestDebateState(
                {
                    "history": "",
                    "bull_history": "",
                    "bear_history": "",
                    "neutral_history": "",
                    "latest_speaker": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "market_score": None,
            "fundamentals_report": "",
            "fundamentals_score": None,
            "sec_report": "",
            "sec_score": None,
            "sentiment_report": "",
            "sentiment_score": None,
            "technical_report": "",
            "technical_score": None,
            "report_usage": {},
            "report_resources": [],
            "report_resources_by_report": {},
            "report_steps_by_report": {},
        }

    def get_graph_args(self, session_id: str = None) -> Dict[str, Any]:
        """Get arguments for the graph invocation.
        
        Args:
            session_id: Optional session ID to maintain context across invocations
        """
        config = {"recursion_limit": self.max_recur_limit}
        if session_id:
            config["configurable"] = {"thread_id": session_id}
        
        return {
            "stream_mode": "values",
            "config": config,
        }

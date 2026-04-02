# TradingAgents/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional

from langgraph.prebuilt import ToolNode

from ..agents import *
from ..default_config import DEFAULT_CONFIG
from ai_engine import LLMProvider
from ..agents.utils.memory import FinancialSituationMemory
from ..agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from ..datasources.info_service_client import require_info_service, set_info_service_url

# Import the new abstract tool methods from agent_utils
from ..agents.utils.agent_utils import (
    get_ticker_data,
    get_ticker_quote,
    get_indicators,
    get_fundamentals,
    get_analysts_recommendation,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_reddit_company_social,
    get_insider_sentiment,
    get_insider_transactions,
    get_global_news
)
from ..agents.utils.edgar_tools import get_edgar_filing_content

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import resolve_trade_signal_from_state
# tool_node_with_resources no longer needed - analysts are self-contained


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "technical", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        set_info_service_url(self.config.get("info_service_url"))
        require_info_service()

        # Import advanced technical tools for tool nodes
        from ..agents.utils.advanced_technical_tools import (
            detect_divergence,
            detect_regime,
            detect_support_resistance
        )

        # Initialize LLMs via provider (deep thinker + quick thinking model)
        llm_provider = LLMProvider(self.config)
        self.deep_thinking_llm = llm_provider.get_deep_llm(request_timeout=120)
        self.quick_thinking_llm = llm_provider.get_quick_llm(request_timeout=120)
        
        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)

        # Create tool nodes
        # Initialize conditional logic for debate and risk analysis loops
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config.get("max_debate_rounds", 1),
            max_risk_discuss_rounds=self.config.get("max_risk_discuss_rounds", 1),
        )
        
        # Initialize graph setup (analysts are now self-contained, no tool nodes needed)
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(
            selected_analysts,
            parallel_analysts=self.config.get("parallel_analysts", True),
        )

    # _create_tool_nodes removed - analysts are now self-contained and handle tools internally

    def propagate(self, company_name, trade_date, session_id: str = None):
        """Run the trading agents graph for a company on a specific date.
        
        Args:
            company_name: The ticker symbol or company name to analyze
            trade_date: The date for the trading analysis
            session_id: Optional session ID to maintain context across invocations
        """

        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date
        )
        args = self.propagator.get_graph_args(session_id=session_id)

        if self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and BUY/SELL/HOLD from structured fields (no extra LLM on narrative)
        return final_state, resolve_trade_signal_from_state(final_state)

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "market_score": final_state.get("market_score"),
            "sentiment_report": final_state["sentiment_report"],
            "sentiment_score": final_state.get("sentiment_score"),
            "news_report": final_state["news_report"],
            "news_score": final_state.get("news_score"),
            "fundamentals_report": final_state["fundamentals_report"],
            "fundamentals_score": final_state.get("fundamentals_score"),
            "sec_report": final_state.get("sec_report", ""),
            "sec_score": final_state.get("sec_score"),
            "technical_report": final_state.get("technical_report", ""),
            "technical_score": final_state.get("technical_score"),
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "trader_tps_plan": final_state.get("trader_tps_plan", ""),
            "risk_debate_state": {
                "risky_history": final_state["risk_debate_state"]["risky_history"],
                "safe_history": final_state["risk_debate_state"]["safe_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "recommendation_score": final_state.get("recommendation_score"),
            "expected_return_pct": final_state.get("expected_return_pct"),
            "bear_case_return_pct": final_state.get("bear_case_return_pct"),
            "bull_case_return_pct": final_state.get("bull_case_return_pct"),
            "final_trade_decision": final_state["final_trade_decision"],
            "risk_score": final_state.get("risk_score"),
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json",
            "w",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_risk_manager(
            self.curr_state, returns_losses, self.risk_manager_memory
        )


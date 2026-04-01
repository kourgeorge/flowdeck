# TradingAgents/graph/setup.py

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph, START

from ..agents import *
from ..agents.utils.agent_states import AgentState

from .conditional_logic import ConditionalLogic
from .tool_node_with_resources import make_extract_resources_node
from .isolated_tool_node import make_isolated_tool_node


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: BaseChatModel,
        deep_thinking_llm: BaseChatModel,
        tool_nodes: Dict[str, Any],
        bull_memory,
        bear_memory,
        trader_memory,
        invest_judge_memory,
        risk_manager_memory,
        conditional_logic: ConditionalLogic,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.risk_manager_memory = risk_manager_memory
        self.conditional_logic = conditional_logic

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
                - "technical": Technical analyst (advanced pattern recognition)
                - "sec": SEC/Regulatory analyst (EDGAR risk factors, MD&A, competition)
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create analyst nodes and isolated tool nodes
        analyst_nodes = {}
        tool_nodes = {}

        if "market" in selected_analysts:
            from ..agents.utils.agent_utils import (
                get_ticker_data, get_ticker_quote, get_indicators, get_analysts_recommendation
            )
            analyst_nodes["market"] = create_market_analyst(self.quick_thinking_llm)
            tool_nodes["market"] = make_isolated_tool_node(
                [get_ticker_data, get_ticker_quote, get_indicators, get_analysts_recommendation],
                "_market_context"
            )

        if "social" in selected_analysts:
            from ..agents.utils.agent_utils import get_ticker_quote, get_reddit_company_social
            analyst_nodes["social"] = create_social_media_analyst(self.quick_thinking_llm)
            tool_nodes["social"] = make_isolated_tool_node(
                [get_ticker_quote, get_reddit_company_social],
                "_social_context"
            )

        if "news" in selected_analysts:
            from ..agents.utils.agent_utils import get_news, get_global_news, get_insider_transactions
            analyst_nodes["news"] = create_news_analyst(self.quick_thinking_llm)
            tool_nodes["news"] = make_isolated_tool_node(
                [get_news, get_global_news, get_insider_transactions],
                "_news_context"
            )

        if "fundamentals" in selected_analysts:
            from ..agents.utils.agent_utils import (
                get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
            )
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(self.quick_thinking_llm)
            tool_nodes["fundamentals"] = make_isolated_tool_node(
                [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement],
                "_fundamentals_context"
            )

        if "technical" in selected_analysts:
            from ..agents.utils.agent_utils import get_ticker_data, get_ticker_quote, get_indicators
            from ..agents.utils.advanced_technical_tools import (
                detect_divergence, detect_regime, detect_support_resistance
            )
            analyst_nodes["technical"] = create_technical_analyst(self.quick_thinking_llm)
            tool_nodes["technical"] = make_isolated_tool_node(
                [get_ticker_data, get_ticker_quote, get_indicators,
                 detect_divergence, detect_regime, detect_support_resistance],
                "_technical_context"
            )

        if "sec" in selected_analysts:
            from ..agents.utils.edgar_tools import get_edgar_filing_content
            analyst_nodes["sec"] = create_sec_analyst(self.quick_thinking_llm)
            tool_nodes["sec"] = make_isolated_tool_node(
                [get_edgar_filing_content],
                "_sec_context"
            )

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(
            self.quick_thinking_llm, self.bull_memory
        )
        bear_researcher_node = create_bear_researcher(
            self.quick_thinking_llm, self.bear_memory
        )
        research_manager_node = create_research_manager(
            self.deep_thinking_llm, self.invest_judge_memory
        )
        trader_node = create_trader(self.quick_thinking_llm, self.trader_memory)

        # Create risk analysis nodes
        risky_analyst = create_risky_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        safe_analyst = create_safe_debator(self.quick_thinking_llm)
        risk_manager_node = create_risk_manager(
            self.deep_thinking_llm, self.risk_manager_memory
        )

        # Create workflow
        workflow = StateGraph(AgentState)
        extract_resources_node = make_extract_resources_node()

        # Add analyst nodes to the graph
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])
            workflow.add_node(f"extract_resources_{analyst_type}", extract_resources_node)

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Risky Analyst", risky_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Safe Analyst", safe_analyst)
        workflow.add_node("Risk Judge", risk_manager_node)

        # Define edges
        # Start with the first analyst
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

        # Connect analysts in sequence
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            
            # Determine next node
            if i < len(selected_analysts) - 1:
                next_node = f"{selected_analysts[i+1].capitalize()} Analyst"
            else:
                next_node = "Bull Researcher"

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                {
                    current_tools: current_tools,
                    "complete": next_node,
                },
            )
            # After tools run, extract resources then loop back to analyst
            workflow.add_edge(current_tools, f"extract_resources_{analyst_type}")
            workflow.add_edge(f"extract_resources_{analyst_type}", current_analyst)

        # Add remaining edges
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Risky Analyst")
        workflow.add_conditional_edges(
            "Risky Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Safe Analyst": "Safe Analyst",
                "Risk Judge": "Risk Judge",
            },
        )
        workflow.add_conditional_edges(
            "Safe Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Risk Judge": "Risk Judge",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Risky Analyst": "Risky Analyst",
                "Risk Judge": "Risk Judge",
            },
        )

        workflow.add_edge("Risk Judge", END)

        # Compile and return
        return workflow.compile()

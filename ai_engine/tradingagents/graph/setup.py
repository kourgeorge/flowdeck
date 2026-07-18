# TradingAgents/graph/setup.py

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph, START
from langgraph.types import Send

from ..agents import *
from ..agents.utils.agent_states import AgentState

# Conditional logic no longer needed - analysts are self-contained
# from .conditional_logic import ConditionalLogic
# from .tool_node_with_resources import make_extract_resources_node
# from .isolated_tool_node import make_isolated_tool_node


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: BaseChatModel,
        deep_thinking_llm: BaseChatModel,
        bull_memory,
        bear_memory,
        neutral_memory,
        trader_memory,
        invest_judge_memory,
        conditional_logic: Any,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.neutral_memory = neutral_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.conditional_logic = conditional_logic

    def setup_graph(
        self,
        selected_analysts=["market", "social", "fundamentals"],
        *,
        parallel_analysts: bool = True,
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": News & Sentiment analyst (news/catalysts + crowd sentiment)
                - "fundamentals": Fundamentals analyst
                - "technical": Technical analyst (advanced pattern recognition)
                - "sec": SEC/Regulatory analyst (EDGAR risk factors, MD&A, competition)
                - "valuation": Valuation analyst (multi-method fair value analysis)
            parallel_analysts: If True and more than one analyst is selected, run analyst
                nodes in parallel (fan-out from START, then barrier before Bull Researcher).
                If False, preserve the previous sequential ordering of selected_analysts.
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create self-contained analyst nodes
        analyst_nodes = {}
        if "market" in selected_analysts:
            analyst_nodes["market"] = create_market_analyst(self.quick_thinking_llm)

        if "social" in selected_analysts:
            analyst_nodes["social"] = create_social_media_analyst(self.quick_thinking_llm)

        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(self.quick_thinking_llm)

        if "technical" in selected_analysts:
            analyst_nodes["technical"] = create_technical_analyst(self.quick_thinking_llm)

        if "sec" in selected_analysts:
            analyst_nodes["sec"] = create_sec_analyst(self.quick_thinking_llm)

        if "valuation" in selected_analysts:
            analyst_nodes["valuation"] = create_valuation_analyst(self.quick_thinking_llm)

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(
            self.quick_thinking_llm, self.bull_memory
        )
        bear_researcher_node = create_bear_researcher(
            self.quick_thinking_llm, self.bear_memory
        )
        neutral_researcher_node = create_neutral_researcher(
            self.quick_thinking_llm, self.neutral_memory
        )
        research_manager_node = create_research_manager(
            self.deep_thinking_llm, self.invest_judge_memory
        )
        trader_node = create_trader(self.quick_thinking_llm, self.trader_memory)

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph (self-contained, no tool nodes needed)
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Neutral Researcher", neutral_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)

        analyst_node_names = [
            f"{analyst_type.capitalize()} Analyst" for analyst_type in selected_analysts
        ]

        # Analyst phase: parallel (Send) or sequential chain; then join to Bull Researcher.
        if parallel_analysts and len(selected_analysts) > 1:

            def fan_out_analysts(state) -> list[Send]:
                return [Send(name, state) for name in analyst_node_names]

            workflow.add_conditional_edges(START, fan_out_analysts)
            workflow.add_edge(analyst_node_names, "Bull Researcher")
        else:
            first_analyst = selected_analysts[0]
            workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")
            for i, analyst_type in enumerate(selected_analysts):
                current_analyst = f"{analyst_type.capitalize()} Analyst"
                if i < len(selected_analysts) - 1:
                    next_node = f"{selected_analysts[i + 1].capitalize()} Analyst"
                else:
                    next_node = "Bull Researcher"
                workflow.add_edge(current_analyst, next_node)

        # Add remaining edges: 3-way Bull/Bear/Neutral debate, then Research Manager.
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Neutral Researcher": "Neutral Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Neutral Researcher": "Neutral Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", END)

        # Compile and return
        return workflow.compile()

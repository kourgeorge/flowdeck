from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.processing import DetectedEvent, TickerEventSummary
from ai_engine.briefing_agent import prompts
from ai_engine.briefing_agent.context_builder import build_digest_context
from ai_engine.briefing_agent.runner import run_digest
from ai_engine.briefing_agent.state import DigestContext, HistoricalDigestBrief, MarketInterpretation


class _MarketOnlyFetcher:
    def get_daily_market_movers(self, limit: int) -> dict:
        return {
            "gainers": [
                {
                    "symbol": "NSA",
                    "shortName": "National Storage Affiliates Trust",
                    "regularMarketPrice": 39.25,
                    "regularMarketChange": 2.05,
                    "regularMarketChangePercent": 5.51,
                },
                {
                    "symbol": "NBIS",
                    "shortName": "Nebius Group",
                    "regularMarketPrice": 31.4,
                    "regularMarketChange": 1.3,
                    "regularMarketChangePercent": 4.32,
                },
            ],
            "losers": [
                {
                    "symbol": "VNET",
                    "shortName": "VNET Group",
                    "regularMarketPrice": 6.8,
                    "regularMarketChange": -0.74,
                    "regularMarketChangePercent": -9.81,
                }
            ],
        }

    def get_news(self, ticker: str, lookback_days: int = 7) -> dict:
        return {"articles": [{"title": f"{ticker} headline"}]}

    def get_fundamentals(self, ticker: str) -> dict:
        return {"ticker": ticker}

    def get_analyst_recommendations(self, ticker: str) -> dict:
        return {"ticker": ticker, "rating": "hold"}

    def get_insider_transactions(self, ticker: str, limit: int = 20) -> dict:
        return {"ticker": ticker, "transactions": []}

    def get_company_info_batch(self, tickers: list[str]) -> dict:
        return {ticker: {"sector": "Real Estate" if ticker == "NSA" else "Technology", "industry": "Test"} for ticker in tickers}


class TestBuildDigestContext(unittest.TestCase):
    @patch("ai_engine.briefing_agent.context_builder._fetch_web_snippet", return_value="Macro snippet")
    @patch("ai_engine.briefing_agent.context_builder._fetch_global_news", return_value={"items": ["Fed", "CPI"]})
    @patch("ai_engine.briefing_agent.context_builder._get_user_context_snapshot", return_value="Long-term investor")
    @patch("ai_engine.briefing_agent.context_builder._load_portfolio_tickers", return_value=[])
    def test_market_context_is_built_without_portfolio_tickers(
        self,
        _mock_tickers,
        _mock_user_context,
        _mock_global_news,
        _mock_web_snippet,
    ) -> None:
        result = build_digest_context(
            user_id=7,
            digest_date="2026-03-16",
            max_priority_tickers=5,
            db=object(),
            fetcher=_MarketOnlyFetcher(),
        )

        self.assertEqual(result.tickers, [])
        self.assertEqual(result.priority_tickers, ["VNET", "NSA", "NBIS"])
        self.assertEqual(result.market_movers["gainers"][0]["symbol"], "NSA")
        self.assertEqual(result.global_news, {"items": ["Fed", "CPI"]})
        self.assertEqual(result.web_search_snippet, "Macro snippet")
        self.assertEqual(result.quotes["NSA"]["name"], "National Storage Affiliates Trust")


class TestRunDigest(unittest.TestCase):
    @patch("ai_engine.briefing_agent.runner.run_narrative_writer", return_value=("Market-only brief", "Watch rates and breadth."))
    @patch(
        "ai_engine.briefing_agent.runner.run_market_interpreter",
        return_value=MarketInterpretation(
            summary="Stocks were mixed as macro data dominated.",
            relevance_to_portfolio="This matters for broad equity exposure.",
        ),
    )
    @patch("ai_engine.briefing_agent.runner.run_ticker_interpreter", return_value={})
    @patch("ai_engine.briefing_agent.runner.run_focus_selector", return_value=None)
    @patch("ai_engine.briefing_agent.runner.get_llm", return_value=object())
    @patch("ai_engine.briefing_agent.runner.get_config_from_env", return_value={})
    @patch(
        "ai_engine.briefing_agent.runner.build_digest_context",
        return_value=DigestContext(
            tickers=[],
            priority_tickers=[],
            market_movers={"gainers": [{"symbol": "NVDA"}]},
            global_news={"items": ["Fed"]},
            web_search_snippet="Macro snippet",
        ),
    )
    def test_run_digest_generates_market_brief_when_no_subscriptions(
        self,
        _mock_context,
        _mock_config,
        _mock_llm,
        _mock_focus,
        _mock_ticker,
        mock_market,
        mock_narrative,
    ) -> None:
        result = run_digest(user_id=7, digest_date="2026-03-16", db=object())

        self.assertEqual(result.narrative, "Market-only brief")
        self.assertEqual(result.what_to_watch, "Watch rates and breadth.")
        self.assertEqual(result.priority_tickers, [])
        self.assertEqual(result.important_events, [])
        mock_market.assert_called_once()
        mock_narrative.assert_called_once()

    @patch("ai_engine.briefing_agent.runner.run_narrative_writer", return_value=("Market-only brief", "Watch rates and breadth."))
    @patch(
        "ai_engine.briefing_agent.runner.run_recent_briefs_summarizer",
        return_value="Recent briefs emphasized rates and breadth.",
    )
    @patch(
        "ai_engine.briefing_agent.runner.run_market_interpreter",
        return_value=MarketInterpretation(
            summary="Stocks were mixed as macro data dominated.",
            relevance_to_portfolio="This matters for broad equity exposure.",
        ),
    )
    @patch("ai_engine.briefing_agent.runner.run_ticker_interpreter", return_value={})
    @patch("ai_engine.briefing_agent.runner.run_focus_selector", return_value=None)
    @patch("ai_engine.briefing_agent.runner.get_config_from_env", return_value={})
    @patch(
        "ai_engine.briefing_agent.runner.get_llm",
        side_effect=["quick-llm", "deep-llm"],
    )
    @patch(
        "ai_engine.briefing_agent.runner.build_digest_context",
        return_value=DigestContext(
            tickers=[],
            priority_tickers=[],
            market_movers={"gainers": [{"symbol": "NVDA"}]},
            global_news={"items": ["Fed"]},
            web_search_snippet="Macro snippet",
        ),
    )
    def test_run_digest_uses_deep_model_only_for_narrative_writer(
        self,
        _mock_context,
        mock_get_llm,
        _mock_config,
        _mock_focus,
        _mock_ticker,
        mock_market,
        mock_recent_summary,
        mock_narrative,
    ) -> None:
        result = run_digest(user_id=7, digest_date="2026-03-16", db=object())

        self.assertEqual(mock_get_llm.call_args_list[0].args[:2], ("quick", {}))
        self.assertEqual(mock_get_llm.call_args_list[1].args[:2], ("deep", {}))
        mock_market.assert_called_once_with(unittest.mock.ANY, "quick-llm")
        mock_recent_summary.assert_called_once_with(unittest.mock.ANY, "quick-llm")
        mock_narrative.assert_called_once_with(unittest.mock.ANY, "deep-llm")
        self.assertEqual(result.models_used["deep_think"], None)

    @patch("ai_engine.briefing_agent.runner.run_narrative_writer", return_value=("Market plus portfolio context", "Watch earnings and macro."))
    @patch(
        "ai_engine.briefing_agent.runner.run_market_interpreter",
        return_value=MarketInterpretation(
            summary="Leadership narrowed while defensives held up.",
            relevance_to_portfolio="Even without priority names, the backdrop still matters.",
        ),
    )
    @patch("ai_engine.briefing_agent.runner.run_ticker_interpreter", return_value={})
    @patch("ai_engine.briefing_agent.runner.run_focus_selector", return_value=[])
    @patch("ai_engine.briefing_agent.runner.get_llm", return_value=object())
    @patch("ai_engine.briefing_agent.runner.get_config_from_env", return_value={})
    @patch(
        "ai_engine.briefing_agent.runner.build_digest_context",
        return_value=DigestContext(
            tickers=["AAPL", "MSFT"],
            priority_tickers=[],
            attention_scores={"AAPL": 0.0, "MSFT": 0.0},
            market_movers={"losers": [{"symbol": "TSLA"}]},
            global_news={"items": ["Retail sales"]},
        ),
    )
    def test_run_digest_keeps_market_brief_when_no_priority_tickers(
        self,
        _mock_context,
        _mock_config,
        _mock_llm,
        _mock_focus,
        _mock_ticker,
        mock_market,
        mock_narrative,
    ) -> None:
        result = run_digest(user_id=7, digest_date="2026-03-16", db=object())

        self.assertEqual(result.narrative, "Market plus portfolio context")
        self.assertEqual(result.what_to_watch, "Watch earnings and macro.")
        self.assertEqual(result.priority_tickers, [])
        self.assertEqual(result.important_events, [])
        mock_market.assert_called_once()
        mock_narrative.assert_called_once()

    @patch("ai_engine.briefing_agent.runner.run_narrative_writer", return_value=("Focused brief", "Watch confirmation."))
    @patch(
        "ai_engine.briefing_agent.runner.run_market_interpreter",
        return_value=MarketInterpretation(
            summary="Mixed market",
            relevance_to_portfolio="Relevant backdrop.",
        ),
    )
    @patch("ai_engine.briefing_agent.runner.run_ticker_interpreter", return_value={})
    @patch("ai_engine.briefing_agent.runner.run_focus_selector", return_value=["AAPL"])
    @patch("ai_engine.briefing_agent.runner.get_llm", return_value=object())
    @patch("ai_engine.briefing_agent.runner.get_config_from_env", return_value={})
    @patch(
        "ai_engine.briefing_agent.runner.build_digest_context",
        return_value=DigestContext(
            tickers=["AAPL", "MSFT"],
            priority_tickers=["AAPL", "MSFT"],
            quotes={"AAPL": {"current_price": 210.0, "name": "Apple Inc."}},
            returns_1d={"AAPL": 5.2},
            event_summaries={
                "AAPL": TickerEventSummary(
                    ticker="AAPL",
                    event_score=3.5,
                    dominant_events=["price_spike_up", "earnings_upcoming"],
                    event_count=2,
                    events=[
                        DetectedEvent(
                            event_type="price_spike_up",
                            domain="price_technical",
                            detected_on="2026-03-16",
                            window_start="2026-03-01",
                            window_end="2026-03-16",
                            strength="high",
                            metric_value=5.2,
                            threshold_value=4.0,
                            metadata={"return_1d_pct": 5.2},
                        ),
                        DetectedEvent(
                            event_type="earnings_upcoming",
                            domain="fundamental",
                            detected_on="2026-03-20",
                            window_start="2026-03-16",
                            window_end="2026-04-15",
                            strength="medium",
                            metric_value=4.0,
                            threshold_value=30.0,
                            metadata={"days_until": 4},
                        ),
                    ],
                ),
            },
        ),
    )
    def test_run_digest_returns_important_events_for_selected_focus_tickers(
        self,
        _mock_context,
        _mock_config,
        _mock_llm,
        _mock_focus,
        _mock_ticker,
        _mock_market,
        _mock_narrative,
    ) -> None:
        result = run_digest(user_id=7, digest_date="2026-03-16", db=object())

        self.assertEqual(result.priority_tickers, ["AAPL"])
        self.assertEqual([item.event.event_type for item in result.important_events], ["price_spike_up", "earnings_upcoming"])
        self.assertEqual(result.important_events[0].ticker, "AAPL")
        self.assertGreater(result.important_events[0].importance_score, result.important_events[1].importance_score)


class TestNarrativePromptComposition(unittest.TestCase):
    def test_default_prompt_composes_base_and_default_style_prompt(self) -> None:
        instructions = prompts.build_narrative_prompt_instructions(None)

        self.assertIn("### Base narrative prompt", instructions)
        self.assertIn(prompts.BASIC_NARRATIVE_WRITING_PROMPT, instructions)
        self.assertIn("valid Markdown", instructions)
        self.assertIn("explicitly name the relevant ticker symbol", instructions)
        self.assertIn("Keep every sentence short, clear, and specific", instructions)
        self.assertIn("Prefer bullet lists to convey messages", instructions)
        self.assertIn("Prefer Markdown tables", instructions)
        self.assertIn("### Style prompt", instructions)
        self.assertIn(prompts.DEFAULT_NARRATIVE_STYLE_PROMPT, instructions)

    def test_technical_prompt_composes_base_and_technical_style_prompt(self) -> None:
        instructions = prompts.build_narrative_prompt_instructions("technical")

        self.assertIn(prompts.BASIC_NARRATIVE_WRITING_PROMPT, instructions)
        self.assertIn(prompts.NARRATIVE_STYLE_PROMPTS["technical"], instructions)
        self.assertIn("Keep sentences short, explicit, and highly specific", instructions)
        self.assertIn("2–4 short sentences", instructions)
        self.assertNotIn(prompts.DEFAULT_NARRATIVE_STYLE_PROMPT, instructions)

    def test_concise_prompt_requests_bulleted_sections(self) -> None:
        instructions = prompts.build_narrative_prompt_instructions("concise")

        self.assertIn("exactly four sections", instructions)
        self.assertIn("valid Markdown bullet list of key insights with 2–3 bullets", instructions)
        self.assertIn("Every bullet must begin with `- `", instructions)
        self.assertIn("Each bullet must be a single short sentence", instructions)
        self.assertIn("Market Highlights", instructions)
        self.assertIn("Risks & Opportunities", instructions)

    def test_balanced_and_professional_prompts_require_short_specific_sentences(self) -> None:
        balanced = prompts.build_narrative_prompt_instructions("balanced")
        professional = prompts.build_narrative_prompt_instructions("professional")

        self.assertIn("Use short, concrete sentences and prefer one idea per sentence", balanced)
        self.assertIn("Prefer bullet lists for key messages", balanced)
        self.assertIn("Use short, precise sentences", professional)
        self.assertIn("Markdown tables for compact facts", professional)

    def test_concise_uses_structured_output(self) -> None:
        self.assertTrue(prompts.style_uses_structured_output("concise"))

    def test_writer_system_requires_markdown(self) -> None:
        self.assertIn("Return valid Markdown only.", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("Treat the user note as a high-priority instruction", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("If the user note requests a language, write the entire brief in that language.", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("Prefer bullet lists to convey messages", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("Prefer Markdown tables", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("Important Events list is provided, treat it as preferred evidence", prompts.NARRATIVE_WRITER_SYSTEM)

    def test_narrative_writer_prompt_marks_user_note_high_priority(self) -> None:
        prompt = prompts.build_narrative_writer_prompt(
            ticker_interpretations_text="(none)",
            market_interpretation_text="Summary: Mixed session\nRelevance to portfolio: Relevant.",
            tool_names=["get_ticker_quote"],
            user_note="in spanish",
            narrative_style="concise",
            period_label="today",
        )

        self.assertIn("## User note for this brief", prompt)
        self.assertIn("This note is a high-priority instruction for this run.", prompt)
        self.assertIn("in spanish", prompt)

    def test_narrative_writer_prompt_includes_recent_briefs_summary(self) -> None:
        prompt = prompts.build_narrative_writer_prompt(
            ticker_interpretations_text="(none)",
            market_interpretation_text="Summary: Mixed session\nRelevance to portfolio: Relevant.",
            tool_names=["get_ticker_quote"],
            recent_briefs_summary="Recent briefs already emphasized rates pressure and defensive positioning.",
            period_label="today",
        )

        self.assertIn("## Summary of recent briefs", prompt)
        self.assertIn("Avoid repeating them unless today's evidence materially changes them", prompt)
        self.assertIn("Recent briefs already emphasized rates pressure", prompt)

    def test_narrative_writer_prompt_includes_important_events(self) -> None:
        prompt = prompts.build_narrative_writer_prompt(
            ticker_interpretations_text="### AAPL\n- Explanation: Apple moved higher.",
            market_interpretation_text="Summary: Mixed session\nRelevance to portfolio: Relevant.",
            tool_names=["get_ticker_quote"],
            important_events_text=(
                "- AAPL: price_spike_up (importance=4.0; strength=high; date=2026-03-16) "
                "— The stock rose sharply in a single session relative to its recent normal movement."
            ),
            period_label="today",
        )

        self.assertIn("## Important events", prompt)
        self.assertIn("Use these deterministic events as the primary evidence", prompt)
        self.assertIn("AAPL: price_spike_up", prompt)

    def test_prompts_include_saved_user_profile_context(self) -> None:
        snapshot = "Persona Type: investor\nPreferred AI Style: technical\nSaved AI Memory: Avoid leverage."

        focus_prompt = prompts.build_focus_selector_prompt(
            portfolio_tickers=["AAPL", "MSFT"],
            attention_scores={"AAPL": 1.0, "MSFT": 0.5},
            default_priority_tickers=["AAPL"],
            max_priority_tickers=2,
            user_note=None,
            user_context_snapshot=snapshot,
        )
        ticker_prompt = prompts.build_ticker_interpreter_prompt(
            ticker="AAPL",
            context_text="Quote: {}",
            tool_names=["get_news"],
            user_context_snapshot=snapshot,
        )
        market_prompt = prompts.build_market_interpreter_prompt(
            market_movers_text="(none)",
            global_news_text="(none)",
            web_snippet=None,
            portfolio_tickers=["AAPL"],
            priority_tickers=["AAPL"],
            ticker_one_liners=None,
            tool_names=["web_search"],
            user_context_snapshot=snapshot,
        )
        narrative_prompt = prompts.build_narrative_writer_prompt(
            ticker_interpretations_text="(none)",
            market_interpretation_text="Summary: Mixed\nRelevance to portfolio: Relevant.",
            tool_names=["get_ticker_quote"],
            user_context_snapshot=snapshot,
        )

        self.assertIn("Saved investor profile and AI memory", focus_prompt)
        self.assertIn("User profile and saved memory", ticker_prompt)
        self.assertIn("User profile and saved memory", market_prompt)
        self.assertIn("Saved investor profile and AI memory", narrative_prompt)

    def test_extract_preferred_style_from_user_context(self) -> None:
        snapshot = "Persona Type: trader\nPreferred AI Style: technical\nDate of Birth: Not set"

        self.assertEqual(
            prompts.extract_preferred_style_from_user_context(snapshot),
            "technical",
        )

    @patch("ai_engine.briefing_agent.runner.run_narrative_writer", return_value=("Brief", "Watch list"))
    @patch(
        "ai_engine.briefing_agent.runner.run_market_interpreter",
        return_value=MarketInterpretation(
            summary="Summary",
            relevance_to_portfolio="Relevant",
        ),
    )
    @patch("ai_engine.briefing_agent.runner.run_ticker_interpreter", return_value={})
    @patch("ai_engine.briefing_agent.runner.run_focus_selector", return_value=None)
    @patch(
        "ai_engine.briefing_agent.runner.run_recent_briefs_summarizer",
        return_value="Recent briefs already emphasized rates pressure and Treasury-yield risk.",
    )
    @patch(
        "ai_engine.briefing_agent.runner._load_recent_digest_briefs",
        return_value=[
            HistoricalDigestBrief(
                narrative="Yesterday focused on rates.",
                what_to_watch="Watch Treasury yields.",
                digest_date="2026-03-15",
                created_at="2026-03-15T14:00:00+00:00",
                span_type="daily",
                span_label="Daily",
                priority_tickers=["AAPL"],
            )
        ],
    )
    @patch("ai_engine.briefing_agent.runner.get_llm", return_value=object())
    @patch("ai_engine.briefing_agent.runner.get_config_from_env", return_value={})
    @patch(
        "ai_engine.briefing_agent.runner.build_digest_context",
        return_value=DigestContext(
            tickers=["AAPL"],
            priority_tickers=["AAPL"],
            user_context_snapshot="# Investor Preferences\nPreferred AI Style: technical",
        ),
    )
    def test_run_digest_uses_saved_preferred_style_when_no_runtime_style(
        self,
        _mock_context,
        _mock_config,
        _mock_llm,
        _mock_recent_briefs,
        _mock_recent_summary,
        _mock_focus,
        _mock_ticker,
        _mock_market,
        mock_narrative,
    ) -> None:
        run_digest(user_id=7, digest_date="2026-03-16", db=object())

        called_state = mock_narrative.call_args[0][0]
        self.assertEqual(called_state.narrative_style, "technical")
        self.assertEqual(len(called_state.recent_digest_briefs), 1)
        self.assertEqual(called_state.recent_digest_briefs[0].narrative, "Yesterday focused on rates.")
        self.assertEqual(
            called_state.recent_briefs_summary,
            "Recent briefs already emphasized rates pressure and Treasury-yield risk.",
        )


if __name__ == "__main__":
    unittest.main()

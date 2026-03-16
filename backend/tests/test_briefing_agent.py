from __future__ import annotations

import unittest
from unittest.mock import patch

from ai_engine.briefing_agent import prompts
from ai_engine.briefing_agent.context_builder import build_digest_context
from ai_engine.briefing_agent.runner import run_digest
from ai_engine.briefing_agent.state import DigestContext, MarketInterpretation


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
        mock_market.assert_called_once()
        mock_narrative.assert_called_once()

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
        mock_market.assert_called_once()
        mock_narrative.assert_called_once()


class TestNarrativePromptComposition(unittest.TestCase):
    def test_default_prompt_composes_base_and_default_style_prompt(self) -> None:
        instructions = prompts.build_narrative_prompt_instructions(None)

        self.assertIn("### Base narrative prompt", instructions)
        self.assertIn(prompts.BASIC_NARRATIVE_WRITING_PROMPT, instructions)
        self.assertIn("valid Markdown", instructions)
        self.assertIn("explicitly name the relevant ticker symbol", instructions)
        self.assertIn("### Style prompt", instructions)
        self.assertIn(prompts.DEFAULT_NARRATIVE_STYLE_PROMPT, instructions)

    def test_technical_prompt_composes_base_and_technical_style_prompt(self) -> None:
        instructions = prompts.build_narrative_prompt_instructions("technical")

        self.assertIn(prompts.BASIC_NARRATIVE_WRITING_PROMPT, instructions)
        self.assertIn(prompts.NARRATIVE_STYLE_PROMPTS["technical"], instructions)
        self.assertNotIn(prompts.DEFAULT_NARRATIVE_STYLE_PROMPT, instructions)

    def test_concise_prompt_requests_bulleted_sections(self) -> None:
        instructions = prompts.build_narrative_prompt_instructions("concise")

        self.assertIn("exactly four sections", instructions)
        self.assertIn("valid Markdown bullet list of key insights with 2–3 bullets", instructions)
        self.assertIn("Every bullet must begin with `- `", instructions)
        self.assertIn("Each bullet must be a single short sentence", instructions)
        self.assertIn("Market Highlights", instructions)
        self.assertIn("Risks & Opportunities", instructions)

    def test_concise_uses_structured_output(self) -> None:
        self.assertTrue(prompts.style_uses_structured_output("concise"))

    def test_writer_system_requires_markdown(self) -> None:
        self.assertIn("Return valid Markdown only.", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("Treat the user note as a high-priority instruction", prompts.NARRATIVE_WRITER_SYSTEM)
        self.assertIn("If the user note requests a language, write the entire brief in that language.", prompts.NARRATIVE_WRITER_SYSTEM)

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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import Execution, Report, Subscription, User
from services import event_monitor_service as ems


class _FakeSummary:
    """Stand-in for ``TickerEventSummary``; only these two fields are read."""

    def __init__(self, event_score: float, dominant_events=None) -> None:
        self.event_score = event_score
        self.dominant_events = list(dominant_events or [])


class _FakeAnalysisService:
    """Records ``start_analysis`` calls instead of spending 200 tokens on a real run."""

    def __init__(self, existing: bool = False) -> None:
        self.existing = existing
        self.calls = []

    def start_analysis(self, **kwargs):
        self.calls.append(kwargs)
        return (kwargs.get("analysis_run_id"), self.existing)


class TestShouldRerun(unittest.TestCase):
    """``should_rerun`` is the entire decision, so pin both thresholds from both sides.

    Cases are expressed relative to the constants rather than to literal scores so that
    calibrating ``MIN_EVENT_SCORE`` / ``MIN_SCORE_DELTA`` does not invalidate the test.
    """

    def test_high_signal_and_big_jump_fires(self) -> None:
        score = ems.MIN_EVENT_SCORE + 2.0
        baseline = score - ems.MIN_SCORE_DELTA - 1.0
        self.assertEqual(ems.should_rerun(score, baseline), (True, "signal_spike"))

    def test_already_noisy_at_last_run_does_not_refire(self) -> None:
        score = ems.MIN_EVENT_SCORE + 2.0
        baseline = score - ems.MIN_SCORE_DELTA + 1.0
        self.assertEqual(ems.should_rerun(score, baseline), (False, "small_delta"))

    def test_big_jump_that_is_still_quiet_does_not_fire(self) -> None:
        score = ems.MIN_EVENT_SCORE - 1.0
        self.assertEqual(ems.should_rerun(score, 0.0), (False, "low_signal"))

    def test_signal_that_collapsed_does_not_fire(self) -> None:
        score = ems.MIN_EVENT_SCORE - 1.0
        baseline = ems.MIN_EVENT_SCORE + 5.0
        self.assertEqual(ems.should_rerun(score, baseline), (False, "low_signal"))

    def test_decay_from_a_high_base_does_not_fire(self) -> None:
        score = ems.MIN_EVENT_SCORE + 1.0
        baseline = score + ems.MIN_SCORE_DELTA
        self.assertEqual(ems.should_rerun(score, baseline), (False, "small_delta"))

    def test_both_thresholds_are_inclusive_at_the_boundary(self) -> None:
        score = ems.MIN_EVENT_SCORE
        baseline = score - ems.MIN_SCORE_DELTA
        self.assertEqual(ems.should_rerun(score, baseline), (True, "signal_spike"))
        # A hair under either threshold must not fire.
        self.assertEqual(ems.should_rerun(score - 0.01, baseline - 0.01)[1], "low_signal")
        self.assertEqual(ems.should_rerun(score, baseline + 0.01)[1], "small_delta")


class TestEventMonitorService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="watcher@example.com", hashed_password="x"))
        self.db.commit()

        # Fixed clock so the cooldown window never depends on wall time.
        self.now = datetime(2026, 8, 13, 12, 0, 0)
        self.stale = self.now - timedelta(hours=ems.COOLDOWN_HOURS + 1)
        self.gateway = object()  # never touched; the summary function is patched

        self.high = ems.MIN_EVENT_SCORE + 2.0
        self.quiet = self.high - ems.MIN_SCORE_DELTA - 1.0
        self.nearly = self.high - ems.MIN_SCORE_DELTA + 1.0

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _subscribe(self, ticker: str) -> None:
        self.db.add(Subscription(user_id=1, ticker=ticker))
        self.db.commit()

    def _add_analysis(
        self,
        ticker: str,
        *,
        created_at: datetime,
        status: str = "completed",
        event_score: float = None,
    ) -> int:
        """A completed analysis, optionally carrying the event score it recorded.

        The report row is written directly on the test session rather than through
        ``report_service.save_report``, which opens its own ``SessionLocal``.
        """
        execution = Execution(
            execution_type="ticker",
            subject_type="ticker",
            subject_id=ticker,
            creator_id=1,
            status=status,
            created_at=created_at,
        )
        self.db.add(execution)
        self.db.commit()
        if event_score is not None:
            self.db.add(
                Report(
                    execution_id=execution.id,
                    report_type=ems.SIGNAL_REPORT_TYPE,
                    content="plan",
                    metadata_json=json.dumps(
                        {"event_score": event_score, "dominant_events": ["new_52w_low"]}
                    ),
                    created_at=created_at,
                )
            )
            self.db.commit()
        return int(execution.id)

    def _summary(self, score: float):
        return patch(
            "processing.get_ticker_event_summary",
            return_value=_FakeSummary(score, ["new_52w_low", "volume_spike"]),
        )

    def _check(self, ticker: str, *, analysis_service=None, allow_rerun: bool = True):
        return ems.check_ticker(
            self.db,
            ticker,
            allow_rerun=allow_rerun,
            gateway=self.gateway,
            analysis_service=analysis_service,
            as_of_date="2026-08-13",
            now=self.now,
        )

    def _ticker_executions(self, ticker: str):
        return (
            self.db.query(Execution)
            .filter(Execution.execution_type == "ticker", Execution.subject_id == ticker)
            .all()
        )

    # --- universe selection -------------------------------------------------

    def test_universe_is_stalest_first_capped_and_filtered(self) -> None:
        for ticker in ("AAPL", "MSFT", "NVDA", "TSLA"):
            self._subscribe(ticker)
        self._add_analysis("AAPL", created_at=self.now - timedelta(days=10))
        self._add_analysis("MSFT", created_at=self.now - timedelta(days=1))
        self._add_analysis("NVDA", created_at=self.now - timedelta(days=5))
        # Subscribed but nothing completed yet -> nothing to invalidate.
        self._add_analysis("TSLA", created_at=self.now, status="running")
        # Analyzed but nobody watches it.
        self._add_analysis("GOOG", created_at=self.now - timedelta(days=20))

        self.assertEqual(
            ems.select_monitor_universe(self.db), ["AAPL", "NVDA", "MSFT"]
        )
        self.assertEqual(ems.select_monitor_universe(self.db, limit=2), ["AAPL", "NVDA"])

    def test_universe_is_empty_without_subscribers(self) -> None:
        self._add_analysis("AAPL", created_at=self.now)
        self.assertEqual(ems.select_monitor_universe(self.db), [])

    # --- reading the baseline off the last analysis --------------------------

    def test_no_completed_analysis_is_skipped(self) -> None:
        self._add_analysis("AAPL", created_at=self.now, status="running")
        with self._summary(self.high):
            result = self._check("AAPL")
        self.assertEqual(result["status"], "skipped_no_analysis")

    def test_analysis_without_a_recorded_score_is_skipped(self) -> None:
        """A run predating the recording has no baseline; fabricating one would invent a delta."""
        self._add_analysis("AAPL", created_at=self.stale)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_no_baseline")
        self.assertEqual(service.calls, [])

    def test_baseline_comes_from_the_newest_analysis(self) -> None:
        """"Versus the last run" means the newest analysis wins, whoever triggered it."""
        self._add_analysis("AAPL", created_at=self.now - timedelta(days=9), event_score=0.0)
        self._add_analysis("AAPL", created_at=self.stale, event_score=self.nearly)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["baseline_score"], self.nearly)
        self.assertEqual(result["status"], "skipped_small_delta")
        self.assertEqual(service.calls, [])

    # --- cooldown -----------------------------------------------------------

    def test_cooldown_short_circuits_before_computing_the_summary(self) -> None:
        self._add_analysis(
            "AAPL", created_at=self.now - timedelta(hours=1), event_score=self.quiet
        )

        with patch(
            "processing.get_ticker_event_summary",
            side_effect=AssertionError("event summary computed during cooldown"),
        ):
            result = self._check("AAPL")

        self.assertEqual(result["status"], "skipped_cooldown")

    # --- the fire path ------------------------------------------------------

    def test_signal_spike_starts_a_rerun_and_writes_no_bookkeeping(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.stale, event_score=self.quiet)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "rerun_started")
        self.assertIsNotNone(result["analysis_run_id"])
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(service.calls[0]["ticker"], "AAPL")
        self.assertEqual(service.calls[0]["analysis_date"], "2026-08-13")

        # The monitor keeps no state of its own: the only new execution is the analysis it
        # started, and it is a plain ticker run.
        self.assertEqual(
            [e.execution_type for e in self.db.query(Execution).all()],
            ["ticker", "ticker"],
        )
        self.assertEqual(
            [r.report_type for r in self.db.query(Report).all()], [ems.SIGNAL_REPORT_TYPE]
        )
        self.assertEqual(
            [e.id for e in self._ticker_executions("AAPL")],
            [analysis_id, result["analysis_run_id"]],
        )

    def test_allow_rerun_false_reports_the_decision_without_spending_tokens(self) -> None:
        self._add_analysis("AAPL", created_at=self.stale, event_score=self.quiet)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service, allow_rerun=False)

        self.assertEqual(result["status"], "would_rerun")
        self.assertEqual(service.calls, [])

    def test_small_delta_does_not_fire(self) -> None:
        self._add_analysis("AAPL", created_at=self.stale, event_score=self.nearly)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_small_delta")
        self.assertEqual(service.calls, [])

    def test_low_signal_does_not_fire(self) -> None:
        self._add_analysis("AAPL", created_at=self.stale, event_score=0.0)
        service = _FakeAnalysisService()

        with self._summary(ems.MIN_EVENT_SCORE - 1.0):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_low_signal")
        self.assertEqual(service.calls, [])

    def test_already_running_analysis_leaves_no_orphan_execution(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.stale, event_score=self.quiet)
        service = _FakeAnalysisService(existing=True)

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_already_running")
        self.assertEqual(len(service.calls), 1)
        # The placeholder run was deleted, so only the seeded analysis survives.
        self.assertEqual([e.id for e in self._ticker_executions("AAPL")], [analysis_id])

    # --- the run loop -------------------------------------------------------

    def test_run_event_monitor_survives_a_failing_ticker(self) -> None:
        self._subscribe("AAPL")
        self._subscribe("MSFT")
        self._add_analysis("AAPL", created_at=self.now - timedelta(days=10), event_score=self.quiet)
        self._add_analysis("MSFT", created_at=self.stale, event_score=self.quiet)
        service = _FakeAnalysisService()

        def _summary(_gateway, ticker, **_kwargs):
            if ticker == "AAPL":
                raise RuntimeError("vendor unreachable")
            return _FakeSummary(self.high, ["new_52w_low"])

        with patch("processing.get_ticker_event_summary", side_effect=_summary):
            summary = ems.run_event_monitor(
                self.db,
                gateway=self.gateway,
                analysis_service=service,
                as_of_date="2026-08-13",
                now=self.now,
            )

        self.assertEqual(summary["checked"], 2)
        self.assertEqual(summary["errors"], ["AAPL"])
        self.assertEqual(summary["statuses"], {"error": 1, "rerun_started": 1})
        self.assertEqual(summary["reruns"], ["MSFT"])
        self.assertEqual([call["ticker"] for call in service.calls], ["MSFT"])


if __name__ == "__main__":
    unittest.main()

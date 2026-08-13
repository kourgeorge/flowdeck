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

        # Fixed clock so cooldown and daily-cap windows never depend on wall time.
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

    def _add_analysis(self, ticker: str, *, created_at: datetime, status: str = "completed") -> int:
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
        return int(execution.id)

    def _seed_baseline(
        self,
        ticker: str,
        *,
        event_score: float,
        analysis_execution_id: int,
        observed_at: datetime = None,
        rerun_analysis_id: int = None,
    ) -> int:
        return ems._write_baseline(
            self.db,
            ticker,
            creator_id=1,
            event_score=event_score,
            dominant_events=["new_52w_low"],
            analysis_execution_id=analysis_execution_id,
            baseline_score=None,
            now=observed_at or self.stale,
            rerun_analysis_id=rerun_analysis_id,
        )

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

    # --- re-baselining ------------------------------------------------------

    def test_first_observation_rebaselines_without_analyzing(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "rebaselined")
        self.assertIsNone(result["baseline_score"])
        self.assertEqual(service.calls, [])

        baseline = ems.load_baseline(self.db, "AAPL")
        self.assertEqual(baseline["event_score"], self.high)
        self.assertEqual(baseline["analysis_execution_id"], analysis_id)

    def test_analysis_since_baseline_rebaselines_instead_of_firing(self) -> None:
        old_analysis = self._add_analysis("AAPL", created_at=self.now - timedelta(days=9))
        self._seed_baseline("AAPL", event_score=self.quiet, analysis_execution_id=old_analysis)
        new_analysis = self._add_analysis("AAPL", created_at=self.now - timedelta(days=1))
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "rebaselined")
        self.assertEqual(service.calls, [])
        self.assertEqual(
            ems.load_baseline(self.db, "AAPL")["analysis_execution_id"], new_analysis
        )

    def test_no_completed_analysis_is_skipped(self) -> None:
        self._add_analysis("AAPL", created_at=self.now, status="running")
        with self._summary(self.high):
            result = self._check("AAPL")
        self.assertEqual(result["status"], "skipped_no_analysis")

    # --- cooldown -----------------------------------------------------------

    def test_cooldown_short_circuits_before_computing_the_summary(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline(
            "AAPL",
            event_score=self.quiet,
            analysis_execution_id=analysis_id,
            observed_at=self.now - timedelta(hours=1),
        )

        with patch(
            "processing.get_ticker_event_summary",
            side_effect=AssertionError("event summary computed during cooldown"),
        ):
            result = self._check("AAPL")

        self.assertEqual(result["status"], "skipped_cooldown")

    # --- the fire path ------------------------------------------------------

    def test_signal_spike_starts_a_rerun_and_records_it(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline("AAPL", event_score=self.quiet, analysis_execution_id=analysis_id)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "rerun_started")
        self.assertIsNotNone(result["analysis_run_id"])
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(service.calls[0]["ticker"], "AAPL")
        self.assertEqual(service.calls[0]["analysis_date"], "2026-08-13")

        baseline = ems.load_baseline(self.db, "AAPL")
        self.assertEqual(baseline["event_score"], self.high)
        rerun = (
            self.db.query(Report)
            .filter(
                Report.execution_id == baseline["execution_id"],
                Report.report_type == ems.RERUN_REPORT_TYPE,
            )
            .one()
        )
        self.assertEqual(
            json.loads(rerun.metadata_json)["analysis_run_id"], result["analysis_run_id"]
        )

    def test_allow_rerun_false_reports_the_decision_without_spending_tokens(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline("AAPL", event_score=self.quiet, analysis_execution_id=analysis_id)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service, allow_rerun=False)

        self.assertEqual(result["status"], "would_rerun")
        self.assertEqual(service.calls, [])

    def test_small_delta_does_not_fire(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline("AAPL", event_score=self.nearly, analysis_execution_id=analysis_id)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_small_delta")
        self.assertEqual(service.calls, [])

    def test_low_signal_does_not_fire(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline("AAPL", event_score=0.0, analysis_execution_id=analysis_id)
        service = _FakeAnalysisService()

        with self._summary(ems.MIN_EVENT_SCORE - 1.0):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_low_signal")
        self.assertEqual(service.calls, [])

    def test_already_running_analysis_leaves_no_orphan_execution(self) -> None:
        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline("AAPL", event_score=self.quiet, analysis_execution_id=analysis_id)
        service = _FakeAnalysisService(existing=True)

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_already_running")
        self.assertEqual(len(service.calls), 1)
        # The placeholder run was deleted, so only the seeded analysis survives.
        self.assertEqual([e.id for e in self._ticker_executions("AAPL")], [analysis_id])

    def test_daily_cap_blocks_further_reruns(self) -> None:
        for index in range(ems.MAX_RERUNS_PER_DAY):
            filler = f"FILL{index}"
            filler_analysis = self._add_analysis(filler, created_at=self.now - timedelta(days=4))
            self._seed_baseline(
                filler,
                event_score=self.high,
                analysis_execution_id=filler_analysis,
                observed_at=self.now,
                rerun_analysis_id=1000 + index,
            )

        analysis_id = self._add_analysis("AAPL", created_at=self.now - timedelta(days=4))
        self._seed_baseline("AAPL", event_score=self.quiet, analysis_execution_id=analysis_id)
        service = _FakeAnalysisService()

        with self._summary(self.high):
            result = self._check("AAPL", analysis_service=service)

        self.assertEqual(result["status"], "skipped_daily_cap")
        self.assertEqual(service.calls, [])

    # --- the run loop -------------------------------------------------------

    def test_run_event_monitor_survives_a_failing_ticker(self) -> None:
        self._subscribe("AAPL")
        self._subscribe("MSFT")
        self._add_analysis("AAPL", created_at=self.now - timedelta(days=10))
        self._add_analysis("MSFT", created_at=self.now - timedelta(days=2))

        def _summary(_gateway, ticker, **_kwargs):
            if ticker == "AAPL":
                raise RuntimeError("vendor unreachable")
            return _FakeSummary(self.high, ["new_52w_low"])

        with patch("processing.get_ticker_event_summary", side_effect=_summary):
            summary = ems.run_event_monitor(
                self.db,
                gateway=self.gateway,
                analysis_service=_FakeAnalysisService(),
                as_of_date="2026-08-13",
                now=self.now,
            )

        self.assertEqual(summary["checked"], 2)
        self.assertEqual(summary["errors"], ["AAPL"])
        self.assertEqual(summary["statuses"], {"error": 1, "rebaselined": 1})
        self.assertEqual(summary["reruns"], [])
        self.assertIsNotNone(ems.load_baseline(self.db, "MSFT"))


if __name__ == "__main__":
    unittest.main()

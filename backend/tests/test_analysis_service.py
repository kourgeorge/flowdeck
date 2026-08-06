import tempfile
import unittest
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.analysis_service import AnalysisService


class TestAnalysisServiceCancellation(unittest.TestCase):
    def test_mark_cancelled_running_analysis_no_longer_blocks_same_ticker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AnalysisService(results_dir=temp_dir)
            service.running_analyses[123] = {
                "analysis_run_id": 123,
                "ticker": "AAPL",
                "date": "2026-06-22",
                "status": "running",
            }

            self.assertEqual(service.get_running_analysis_run_id("aapl", "2026-06-22"), 123)

            self.assertTrue(service.mark_analysis_cancelled(123))

            self.assertEqual(service.running_analyses[123]["status"], "cancelled")
            self.assertIsNone(service.get_running_analysis_run_id("AAPL", "2026-06-22"))


if __name__ == "__main__":
    unittest.main()

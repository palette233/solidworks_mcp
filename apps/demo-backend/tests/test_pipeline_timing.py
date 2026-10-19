from __future__ import annotations

import time
import unittest

from demo_backend.pipeline_timing import PipelineTiming


class PipelineTimingTests(unittest.TestCase):
    def test_records_serializable_stage_and_total_timestamps(self) -> None:
        timing = PipelineTiming("test.pipeline", run_id="test-run")
        with timing.stage("first", itemCount=2):
            time.sleep(0.001)

        payload = timing.finish()

        self.assertEqual(payload["runId"], "test-run")
        self.assertEqual(payload["pipeline"], "test.pipeline")
        self.assertEqual(payload["stageCount"], 1)
        self.assertGreater(payload["durationSeconds"], 0.0)
        self.assertEqual(payload["stages"][0]["status"], "completed")
        self.assertEqual(payload["stages"][0]["itemCount"], 2)
        self.assertIn("startedAtUtc", payload["stages"][0])
        self.assertIn("finishedAtUtc", payload["stages"][0])


if __name__ == "__main__":
    unittest.main()

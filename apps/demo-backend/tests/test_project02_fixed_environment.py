from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.layout_preview import solve_case_preview


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "replay_project02_selected_solution.py"
SPEC = importlib.util.spec_from_file_location("replay_project02_selected_solution", SCRIPT)
assert SPEC and SPEC.loader
REPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY)


class Project02FixedEnvironmentTests(unittest.TestCase):
    def test_a600_is_fixed_and_present_in_every_candidate(self) -> None:
        preview = solve_case_preview(
            ROOT,
            "project02",
            persist=False,
            profile="reduced-prototype",
        )

        self.assertEqual(preview["metrics"]["componentCount"], 9)
        self.assertEqual(preview["metrics"]["fixedEnvironmentPassed"], 8)
        self.assertEqual(preview["metrics"]["fixedEnvironmentTotal"], 8)
        self.assertEqual(preview["staticCollisionPolicy"]["pairCount"], 36)
        self.assertEqual(
            preview["staticCollisionPolicy"]["installationContactPairCount"],
            8,
        )
        for solution in preview["solutions"]:
            fixed = [item for item in solution["modules"] if item["code"] == "A600"]
            self.assertEqual(len(fixed), 1)
            self.assertEqual(fixed[0]["role"], "fixed")

    def test_replay_payload_preserves_a600_and_moves_only_eight_modules(self) -> None:
        source = ROOT / "demo" / "layout_previews" / "project02_solution.json"
        with tempfile.TemporaryDirectory() as directory:
            applied, fixed = REPLAY.movable_replay_layout(source, Path(directory))
            document = json.loads(applied.read_text(encoding="utf-8"))

        self.assertEqual(fixed, ["FL9A24D062A600.001-1"])
        self.assertEqual(len(document["components"]), 8)
        self.assertNotIn(
            "FL9A24D062A600.001-1",
            {item["componentName"] for item in document["components"]},
        )


if __name__ == "__main__":
    unittest.main()

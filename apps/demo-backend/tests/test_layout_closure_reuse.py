from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from demo_backend.layout_closure_reuse import (
    applied_layout_from_replay,
    compare_layouts,
    source_geometry_unchanged,
)


class LayoutClosureReuseTests(unittest.TestCase):
    def test_extract_and_compare_identical_layout(self) -> None:
        component = {
            "componentName": "A-1",
            "layout2d": {
                "x": 1.0,
                "y": 2.0,
                "thetaDegrees": 90.0,
                "thetaAxis": "x",
                "normalOffsetMeters": 0.1,
            },
        }
        replay = {
            "steps": [
                {
                    "tool": "apply_captured_common_base_layout",
                    "payload": {"components": [component]},
                }
            ]
        }
        closed = applied_layout_from_replay(replay)
        result = compare_layouts([component], closed)
        self.assertTrue(result["success"])
        self.assertEqual(result["maxXyErrorMeters"], 0.0)

    def test_relative_change_requires_replay(self) -> None:
        selected = [
            {
                "componentName": "A-1",
                "layout2d": {"x": 1, "y": 2, "thetaDegrees": 0},
            }
        ]
        closed = [
            {
                "componentName": "A-1",
                "layout2d": {"x": 1.001, "y": 2, "thetaDegrees": 0},
            }
        ]
        self.assertFalse(compare_layouts(selected, closed)["success"])

    def test_newer_source_geometry_invalidates_reuse(self) -> None:
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "module.SLDASM"
            closure = root / "closure.json"
            closure.write_text("{}", encoding="utf-8")
            source.write_text("changed", encoding="utf-8")
            os.utime(closure, (1000, 1000))
            os.utime(source, (2000, 2000))
            result = source_geometry_unchanged(
                [{"componentName": "A-1", "filePath": str(source)}], closure
            )
            self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()

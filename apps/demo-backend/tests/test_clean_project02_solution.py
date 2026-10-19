from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build_clean_project02_solution.py"
SPEC = importlib.util.spec_from_file_location("build_clean_project02_solution", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanProject02SolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        layout_path = (
            ROOT / "demo" / "layout_previews" / "project02_selected_solution_replay.json"
        )
        self.layout = MODULE.load_layout(layout_path)
        self.expected = MODULE.insertion_components(self.layout)

    def test_clean_manifest_has_exactly_eight_and_identity_anchor_first(self) -> None:
        self.assertEqual(8, len(self.expected))
        self.assertEqual(MODULE.FIXED_ANCHOR_NAME, self.expected[0]["componentName"])
        self.assertEqual(8, len({item["componentName"] for item in self.expected}))

    def test_exact_top_level_whitelist_passes(self) -> None:
        actual = [
            {"Name": item["componentName"], "Path": item["filePath"]}
            for item in self.expected
        ]
        audit = MODULE.audit_top_level_components(actual, self.expected)
        self.assertTrue(audit["success"])
        self.assertEqual(8, audit["actualCount"])

    def test_residual_base_or_cabinet_component_fails(self) -> None:
        actual = [
            {"Name": item["componentName"], "Path": item["filePath"]}
            for item in self.expected
        ]
        actual.append({"Name": "ResidualMachineBase-1", "Path": r"D:\legacy\base.SLDASM"})
        audit = MODULE.audit_top_level_components(actual, self.expected)
        self.assertFalse(audit["success"])
        self.assertEqual(["ResidualMachineBase-1"], audit["extraNames"])

    def test_wrong_source_path_fails(self) -> None:
        actual = [
            {"name": item["componentName"], "path": item["filePath"]}
            for item in self.expected
        ]
        actual[0]["path"] = r"D:\wrong\replacement.SLDASM"
        audit = MODULE.audit_top_level_components(actual, self.expected)
        self.assertFalse(audit["success"])
        self.assertEqual(1, len(audit["pathMismatches"]))


if __name__ == "__main__":
    unittest.main()

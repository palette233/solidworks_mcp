from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project03_incremental_work_packet import (
    AA00,
    AE00,
    AF00,
    build_project03_ae00_work_packet,
)


ROOT = Path(__file__).resolve().parents[3]


class Project03IncrementalWorkPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = json.loads(
            (ROOT / "demo/layout_previews/project03_module_mate_graph.json").read_text(
                encoding="utf-8-sig"
            )
        )
        geometry = json.loads(
            (ROOT / "demo/layout_previews/project03_first_stage_geometry.json").read_text(
                encoding="utf-8-sig"
            )
        )
        cls.result = build_project03_ae00_work_packet(
            cls.graph, Path(geometry["sourceAssemblyPath"])
        )

    def test_paths_are_recovered_to_existing_unicode_files(self) -> None:
        audit = self.result["pathAudit"]
        self.assertTrue(audit["allResolved"])
        self.assertGreaterEqual(audit["recordCount"], 9)
        for row in audit["records"]:
            self.assertTrue(Path(row["resolvedPath"]).is_file())
            self.assertEqual(len(row["sha256"]), 64)

    def test_interface_is_one_plane_two_holes(self) -> None:
        summary = self.result["summary"]
        self.assertEqual(summary["sourceMateTypes"].count("swMateCOINCIDENT"), 1)
        self.assertEqual(summary["sourceMateTypes"].count("swMateCONCENTRIC"), 2)
        self.assertEqual(summary["sourceMateNames"], ["重合28", "同心39", "同心40"])
        self.assertIsInstance(summary["mateNameUnicodeRecoveryApplied"], bool)
        self.assertAlmostEqual(summary["locatingHoleSpacingMeters"], 0.058, places=6)
        self.assertEqual(summary["endpointCount"], 6)
        self.assertTrue(summary["allEndpointsHavePersistentReferences"])

    def test_plan_is_independent_and_not_case_anchored(self) -> None:
        request = self.result["request"]
        effective = self.result["effectiveGraph"]
        base = self.result["baseGraph"]
        self.assertEqual(base["SchemaVersion"], "editable-module-mate-graph/v1")
        self.assertEqual(base["ModuleCount"], 2)
        self.assertEqual(base["InterModuleMateCount"], 0)
        self.assertEqual(request["initialPlacementMode"], "deterministic")
        self.assertEqual(request["fixedContextModuleTokens"], [AA00, AF00])
        self.assertEqual(request["componentToAdd"]["ModuleToken"], AE00)
        self.assertNotIn(AE00, effective["EditPolicy"].get("caseAnchoredModuleTokens") or [])
        self.assertEqual(effective["InterModuleMateCount"], 3)
        self.assertTrue(self.result["summary"]["safeToStartCad"])

    def test_collision_policy_requires_conditional_exact_gate(self) -> None:
        policy = self.result["effectiveGraph"]["SemanticAssemblyPlanAudit"][
            "collisionPolicy"
        ]
        self.assertEqual(policy["classification"], "intended-installation-contact")
        self.assertIn("exact", policy["exactGate"])


if __name__ == "__main__":
    unittest.main()

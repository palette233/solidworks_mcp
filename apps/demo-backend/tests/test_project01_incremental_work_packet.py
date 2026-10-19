from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project01_incremental_work_packet import (
    HL00,
    JJ00,
    SS00,
    build_project01_ss00_work_packet,
)


ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM"
)


class Project01IncrementalWorkPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        graph = json.loads(
            (ROOT / "demo/layout_previews/project01_module_mate_graph.json").read_text(
                encoding="utf-8-sig"
            )
        )
        cls.result = build_project01_ss00_work_packet(graph, PROTOTYPE)

    def test_paths_are_recovered_to_real_unicode_files(self) -> None:
        audit = self.result["pathAudit"]
        self.assertTrue(audit["allResolved"])
        self.assertGreaterEqual(audit["recordCount"], 9)
        for row in audit["records"]:
            self.assertTrue(Path(row["resolvedPath"]).is_file())
            self.assertEqual(len(row["sha256"]), 64)

    def test_interface_is_one_plane_and_two_locating_holes(self) -> None:
        summary = self.result["summary"]
        self.assertEqual(summary["sourceMateNames"], ["重合4", "同心6", "同心7"])
        self.assertAlmostEqual(summary["locatingHoleSpacingMeters"], 0.058, places=6)
        self.assertEqual(summary["endpointCount"], 6)
        self.assertTrue(summary["allEndpointsHavePersistentReferences"])
        self.assertEqual(summary["expectedResidualDof"], 0)

    def test_plan_preserves_fixed_context_and_adds_only_ss00(self) -> None:
        base = self.result["baseGraph"]
        request = self.result["request"]
        effective = self.result["effectiveGraph"]
        self.assertEqual(base["ModuleCount"], 2)
        self.assertEqual(base["EditPolicy"]["fixedModuleTokens"], [JJ00, HL00])
        self.assertEqual(request["componentToAdd"]["ModuleToken"], SS00)
        self.assertEqual(request["fixedContextModuleTokens"], [JJ00, HL00])
        self.assertEqual(effective["InterModuleMateCount"], 3)
        self.assertTrue(self.result["summary"]["safeToStartCad"])

    def test_collision_policy_requires_source_interface_exact_gate(self) -> None:
        policy = self.result["effectiveGraph"]["SemanticAssemblyPlanAudit"][
            "collisionPolicy"
        ]
        self.assertEqual(policy["classification"], "intended-installation-contact")
        self.assertIn("source interface", policy["exactGate"])


if __name__ == "__main__":
    unittest.main()

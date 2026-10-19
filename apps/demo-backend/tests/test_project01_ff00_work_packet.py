from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project01_ff00_work_packet import build_project01_ff00_work_packet


ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Project01Ff00WorkPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_project01_ff00_work_packet(
            load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
            load(
                ROOT
                / "demo/semantic_ports/project01_SS00_first_increment_v1/assembly_plan_effective.json"
            ),
            PROTOTYPE,
        )

    def test_static_three_datum_interface_is_complete(self) -> None:
        summary = self.result["summary"]
        self.assertEqual(summary["sourceMateNames"], ["重合10", "同心20", "同心19"])
        self.assertAlmostEqual(summary["locatingHoleSpacingMeters"], 0.035, places=6)
        self.assertEqual(summary["endpointCount"], 6)
        self.assertTrue(summary["allEndpointsHavePersistentReferences"])
        self.assertTrue(summary["safeToStartStaticCad"])

    def test_prior_context_is_preserved_and_ff00_is_added(self) -> None:
        base = self.result["baseGraph"]
        effective = self.result["effectiveGraph"]
        request = self.result["request"]
        self.assertEqual(
            {row["ModuleToken"] for row in base["Modules"]},
            {"JJ00", "HL00", "SS00"},
        )
        self.assertEqual(request["componentToAdd"]["ModuleToken"], "FF00")
        self.assertEqual(request["fixedContextModuleTokens"], ["JJ00", "HL00", "SS00"])
        self.assertEqual(effective["ModuleCount"], 4)
        self.assertEqual(base["InterModuleMateCount"], 0)
        self.assertEqual(effective["InterModuleMateCount"], 3)
        self.assertEqual(
            self.result["summary"]["priorContextMatePolicy"],
            "preserve-in-source-assembly-do-not-resubmit-as-new-driving-mates",
        )

    def test_dynamic_scope_is_explicitly_not_closed(self) -> None:
        summary = self.result["summary"]
        self.assertFalse(summary["dynamicGateReady"])
        self.assertTrue(any("25" in row for row in summary["knownLimits"]))


if __name__ == "__main__":
    unittest.main()

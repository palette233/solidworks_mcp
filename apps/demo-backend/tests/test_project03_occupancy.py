from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project03_occupancy import build_project03_occupancy_and_collision_policy
from demo_backend.project_migration import build_project03_migration_skeleton


MODULE_CODES = ("AA00", "AB00", "AC00", "AD00", "AE00", "AF00", "AG00", "AH00", "AI00", "AJ00")


def _pose(code: str, index: int) -> dict:
    offset = float(index)
    return {
        "Name": f"FL9A24D063{code}.001-1",
        "Translation": [offset, 0.0, 0.0],
        "BoundingBoxWorld": [offset, 0.0, 0.0, offset + 0.4, 0.4, 0.4],
    }


def _capture(code: str, index: int) -> dict:
    offset = float(index)
    return {
        "TopLevelComponent": {"Name": f"FL9A24D063{code}.001-1"},
        "CoverageComplete": True,
        "LeafComponentCount": 1,
        "BodyCount": 1,
        "Bodies": [
            {
                "Component": {
                    "Name": f"FL9A24D063{code}.001-1/part-1",
                    "HierarchyPath": f"FL9A24D063{code}.001-1/FL9A24D063{code}.001-1/{code}-part-1",
                },
                "BoundingBoxWorld": [offset, 0.0, 0.0, offset + 0.2, 0.2, 0.2],
            }
        ],
    }


class Project03OccupancyTests(unittest.TestCase):
    def test_builds_complete_28_pair_partition_without_aj00_leaf_capture(self) -> None:
        poses = {"components": [_pose(code, index) for index, code in enumerate(MODULE_CODES)]}
        captures = [
            {"captures": [_capture(code, MODULE_CODES.index(code))]}
            for code in ("AB00", "AC00", "AD00", "AE00", "AG00", "AH00", "AI00")
        ]
        geometry = {
            "transportInstallationInterface": {
                "originWorldMeters": [0, 0, 0],
                "flowAxisWorld": [1, 0, 0],
                "transverseAxisWorld": [0, 1, 0],
                "upAxisWorld": [0, 0, 1],
            },
            "operationSideInference": {"estimatedFacePlaneWorldX": 9.4},
        }
        result = build_project03_occupancy_and_collision_policy(poses, geometry, captures)
        policy = result["staticCollisionPolicy"]
        self.assertEqual(result["status"], "PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY")
        self.assertEqual(result["coverage"]["layoutObjectCount"], 8)
        self.assertEqual(result["coverage"]["capturedLeafBodyCount"], 7)
        self.assertEqual(policy["pairCount"], 28)
        self.assertEqual(len(policy["strictMultiAabbPairs"]), 12)
        self.assertEqual(len(policy["conditionalBrepPairs"]), 9)
        self.assertEqual(len(policy["installationContactPairs"]), 7)
        self.assertEqual(policy["coveredPairCount"], 28)
        self.assertFalse(result["modules"]["AJ00"]["leafCoverageComplete"])
        self.assertFalse(policy["solverInvokesBrep"])

    def test_ready_occupancy_promotes_only_coarse_layout_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            top = source / "project03.SLDASM"
            top.write_bytes(b"assembly")
            module_ids = [f"FL9A24D063A{letter}00.001" for letter in "ABCDEFGHIJ"]
            for module_id in module_ids:
                (source / f"{module_id}.SLDASM").write_bytes(b"module")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "projectId": "03",
                                "family": "test",
                                "sourceAssemblyPath": str(top),
                                "pptPath": str(root / "03.pptx"),
                                "modules": [
                                    {"cadId": item, "capabilities": ["test"], "confidence": "high"}
                                    for item in module_ids
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview = root / "demo/layout_previews"
            preview.mkdir(parents=True)
            (preview / "project03_scanner_geometry.json").write_text(
                json.dumps(
                    {
                        "status": "PROJECT03_SCANNER_GEOMETRY_PARTIALLY_INFERRED",
                        "coarseLayoutUsable": True,
                    }
                ),
                encoding="utf-8",
            )
            (preview / "project03_module_occupancy.json").write_text(
                json.dumps(
                    {
                        "status": "PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY",
                        "prototypeBaselineAcceptedForCoarseLayout": True,
                        "layoutObjects": [],
                    }
                ),
                encoding="utf-8",
            )
            result = build_project03_migration_skeleton(
                root, manifest_path=manifest, source_root_override=source
            )
            statuses = {item["id"]: item["status"] for item in result["requiredEvidence"]}
            for item_id in (
                "baseOperationFace",
                "operationSideCapacity",
                "barcodeFaceAndSide",
                "moduleOccupancy",
                "staticCollisionPolicy",
            ):
                self.assertEqual(statuses[item_id], "available")
            self.assertIn("Confirm the exact AA00 operation face and maintenance envelope.", result["engineeringConfirmationDebt"])


if __name__ == "__main__":
    unittest.main()

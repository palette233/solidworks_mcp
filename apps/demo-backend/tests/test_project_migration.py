from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project_migration import (
    build_project01_migration_skeleton,
    build_project03_migration_skeleton,
)


class ProjectMigrationTests(unittest.TestCase):
    def _write_complete_geometry_artifacts(self, root: Path) -> None:
        preview = root / "demo" / "layout_previews"
        preview.mkdir(parents=True)
        artifacts = {
            "project01_first_stage_geometry.json": {"status": "PROJECT01_FIRST_STAGE_GEOMETRY_CAPTURED"},
            "project01_work_positions.json": {"status": "PROJECT01_TWO_WORK_POSITIONS_INFERRED"},
            "project01_scanner_geometry.json": {"status": "PROJECT01_SCANNER_GEOMETRY_INFERRED"},
            "project01_service_points.json": {"status": "PROJECT01_SERVICE_POINTS_INFERRED"},
            "project01_dual_valve_reach.json": {
                "status": "PROJECT01_DUAL_VALVE_REACH_INFERRED",
                "allRequiredTargetsInsideCommonReach": True,
            },
            "project01_module_occupancy.json": {
                "status": "PROJECT01_OCCUPANCY_AND_COLLISION_POLICY_READY"
            },
        }
        for name, payload in artifacts.items():
            (preview / name).write_text(json.dumps(payload), encoding="utf-8")

    def test_project01_skeleton_resolves_modules_without_inheriting_project02_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            top = source / "project01.SLDASM"
            top.write_bytes(b"assembly")
            module_ids = [
                "FL9C24N074JJ00.001",
                "FL9C24N074LM00.001",
                "FL9C24N074ZZ00.001",
                "FL9C24N074FF00.001",
                "FL9C24N074SS00.001",
                "FL9C24N074HL00.001",
                "FL9C24N074GN00.001",
                "FL9C24N074BD00.001",
                "FL9C24N074SM00.001",
                "FL9C24N074GJ00.001",
            ]
            capabilities = [
                ["frame_enclosure"],
                ["gantry"],
                ["dispense_head"],
                ["lift_positioning", "rotation"],
                ["transport"],
                ["return_transport"],
                ["cleaning", "weighing", "glue_drain", "glue_hardness_test"],
                ["calibration"],
                ["scanner"],
                ["glue_supply"],
            ]
            for module_id in module_ids:
                (source / f"{module_id}.SLDASM").write_bytes(b"module")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "projectId": "01",
                                "family": "ab_glue_tunnel_with_rotation",
                                "sourceAssemblyPath": str(top),
                                "pptPath": str(root / "01.pptx"),
                                "modules": [
                                    {
                                        "cadId": module_id,
                                        "capabilities": capability,
                                        "confidence": "confirmed",
                                    }
                                    for module_id, capability in zip(module_ids, capabilities)
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = build_project01_migration_skeleton(
                root, manifest_path=manifest, source_root_override=source
            )
            self.assertTrue(result["allModuleCadPathsResolved"])
            self.assertEqual(result["resolvedModuleCadCount"], 10)
            self.assertFalse(result["top3SolveReady"])
            self.assertFalse(result["project02NumericParametersInherited"])
            self.assertIn("combinedServiceFunctionPoints", result["missingRequiredEvidence"])
            self.assertIn("FL9C24N074GN00.001", result["proposedTopLevelSolveObjects"])
            self.assertIn("FL9C24N074FF00.001", result["proposedTopLevelSolveObjects"])
            self.assertEqual(len(result["proposedTopLevelSolveObjects"]), 7)
            self.assertEqual(result["notPresentByDesign"][0]["capability"], "ccd_product")

            self._write_complete_geometry_artifacts(root)
            ready = build_project01_migration_skeleton(
                root, manifest_path=manifest, source_root_override=source
            )
            self.assertTrue(ready["top3SolveReady"])
            self.assertEqual(ready["missingRequiredEvidence"], [])
            self.assertEqual(ready["partialEvidence"], [])
            self.assertEqual(ready["status"], "PROJECT01_TOP3_INPUT_READY")
            self.assertEqual(
                ready["moduleOccupancy"]["status"],
                "PROJECT01_OCCUPANCY_AND_COLLISION_POLICY_READY",
            )

    def test_project03_starts_blocked_without_inheriting_other_case_numbers(self) -> None:
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
                                "family": "ab_glue_tunnel_with_rotation",
                                "sourceAssemblyPath": str(top),
                                "pptPath": str(root / "03.pptx"),
                                "modules": [
                                    {"cadId": module_id, "capabilities": ["test"], "confidence": "high"}
                                    for module_id in module_ids
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = build_project03_migration_skeleton(
                root, manifest_path=manifest, source_root_override=source
            )
            self.assertEqual(result["resolvedModuleCadCount"], 10)
            self.assertTrue(result["allModuleCadPathsResolved"])
            self.assertFalse(result["top3SolveReady"])
            self.assertFalse(result["project01NumericParametersInherited"])
            self.assertFalse(result["project02NumericParametersInherited"])
            self.assertEqual(len(result["proposedTopLevelSolveObjects"]), 7)
            self.assertIn("transportInstallationFrame", result["missingRequiredEvidence"])
            self.assertEqual(result["notPresentByDesign"][0]["capability"], "ccd_product")

    def test_project03_scanner_artifact_closes_axis_but_keeps_carrier_identity_partial(self) -> None:
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
                                "family": "ab_glue_tunnel_with_rotation",
                                "sourceAssemblyPath": str(top),
                                "pptPath": str(root / "03.pptx"),
                                "modules": [
                                    {"cadId": module_id, "capabilities": ["test"], "confidence": "high"}
                                    for module_id in module_ids
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview = root / "demo" / "layout_previews"
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

            result = build_project03_migration_skeleton(
                root, manifest_path=manifest, source_root_override=source
            )
            statuses = {item["id"]: item["status"] for item in result["requiredEvidence"]}
            self.assertEqual(statuses["scannerWorkingDistanceAndAxis"], "available")
            self.assertEqual(statuses["barcodeFaceAndSide"], "partial")
            self.assertNotIn("scannerWorkingDistanceAndAxis", result["missingRequiredEvidence"])
            self.assertIn("barcodeFaceAndSide", result["partialEvidence"])
            self.assertEqual(
                result["nextExtractionOrder"][0],
                "resolve AI00 carrier barcode/RFID evidence",
            )


if __name__ == "__main__":
    unittest.main()

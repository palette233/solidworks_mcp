from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project05_migration import PROJECT05_GROUPS, build_project05_migration_skeleton


class Project05MigrationTests(unittest.TestCase):
    def test_skeleton_resolves_reused_cleaner_and_blocks_top3(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            top = source / "project05.SLDASM"
            top.write_bytes(b"assembly")
            module_ids = [
                "FL9C254098A000.001", "FL9C254098B000.001", "FL9C254098Z000.001",
                "FL9C254098D000.001", "FL9C254098E000.001", "FL9C254098F000.001",
                "FL9C254098G000.001", "FL9C254098K000.001", "FL9C254098M000.001",
                "FL9C251093N000.001", "FL9C254098P000.001",
            ]
            for module_id in module_ids:
                (source / f"{module_id}.SLDASM").write_bytes(b"module")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"projects": [{
                "projectId": "05",
                "family": "epoxy_header_with_product_ccd",
                "sourceAssemblyPath": str(top),
                "pptPath": str(root / "05.pptx"),
                "modules": [
                    {"cadId": module_id, "capabilities": ["test"], "confidence": "confirmed"}
                    for module_id in module_ids
                ] + [{"cadId": None, "capabilities": ["glue_supply"], "confidence": "pending"}],
            }]}), encoding="utf-8")

            result = build_project05_migration_skeleton(
                root, manifest_path=manifest, source_root_override=source
            )
            self.assertEqual(result["resolvedModuleCadCount"], 11)
            self.assertTrue(result["allModuleCadPathsResolved"])
            self.assertEqual(len(result["layoutObjectGroups"]), 9)
            self.assertEqual(len(result["proposedTopLevelSolveObjects"]), 8)
            self.assertIn("FL9C251093N000.001", {item["cadId"] for item in result["modules"]})
            self.assertIn("glue_supply", result["unresolvedOptionalCapabilities"])
            self.assertFalse(result["top3SolveReady"])

    def test_first_stage_artifact_advances_status_and_removes_completed_steps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source_root = workspace / "source"
            source_root.mkdir()
            manifest_path = workspace / "manifest.json"
            modules = []
            for group in PROJECT05_GROUPS:
                for cad_id in group["memberCadIds"]:
                    if cad_id not in {item["cadId"] for item in modules}:
                        modules.append({"cadId": cad_id, "capabilities": ["test"], "confidence": "confirmed"})
                        (source_root / f"{cad_id}.SLDASM").write_bytes(b"test")
            source_assembly = source_root / "project05.SLDASM"
            source_assembly.write_bytes(b"test")
            manifest_path.write_text(json.dumps({"projects": [{
                "projectId": "05",
                "family": "test",
                "sourceAssemblyPath": str(source_assembly),
                "pptPath": str(workspace / "05.pptx"),
                "modules": modules,
            }]}), encoding="utf-8")
            artifact = workspace / "demo/layout_previews/project05_first_stage_geometry.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(json.dumps({"status": "PROJECT05_FIRST_STAGE_GEOMETRY_CAPTURED"}), encoding="utf-8")
            process_artifact = workspace / "demo/layout_previews/project05_process_semantics.json"
            process_artifact.write_text(json.dumps({
                "status": "PROJECT05_PROCESS_SEMANTICS_CAPTURED_CAD_COORDINATES_REQUIRED"
            }), encoding="utf-8")
            work_positions_artifact = workspace / "demo/layout_previews/project05_work_positions.json"
            work_positions_artifact.write_text(json.dumps({
                "status": "PROJECT05_TWO_WORK_POSITIONS_INFERRED",
                "coarseLayoutUsable": True,
            }), encoding="utf-8")

            result = build_project05_migration_skeleton(
                workspace,
                manifest_path=manifest_path,
                source_root_override=source_root,
            )

            self.assertEqual(result["status"], "PROJECT05_FIRST_STAGE_GEOMETRY_CAPTURED_MORE_EVIDENCE_REQUIRED")
            self.assertNotIn("capture Project05 top-level poses and module-level mate graph", result["nextExtractionOrder"])
            self.assertNotIn("recover A000-D000 installation frame", result["nextExtractionOrder"])
            self.assertEqual(result["nextExtractionOrder"][0], "recover F000 scan axis and M000 CCD work geometry")
            self.assertNotIn("transportWorkPositions", result["partialEvidence"])
            self.assertNotIn("transportWorkPositions", result["missingRequiredEvidence"])
            work_position_evidence = next(
                item for item in result["requiredEvidence"] if item["id"] == "transportWorkPositions"
            )
            self.assertEqual(work_position_evidence["status"], "available")
            self.assertIn("K000", work_position_evidence["acquisition"])
            self.assertFalse(result["otherProjectNumericParametersInherited"])
            self.assertIn("ccdWorkingGeometry", result["partialEvidence"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_direct_project02_nine_module_solution.py"
SPEC = importlib.util.spec_from_file_location("direct_project02_nine", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DirectProject02NineModuleTests(unittest.TestCase):
    def test_project02_scanner_uses_named_ccd_structure_channel(self) -> None:
        request = json.loads(
            (ROOT / "demo/FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8-sig"
            )
        )
        scanner = "FL9A24D062A180.001-1"
        ccd = "FL9A24D062A200.001-1"
        self.assertIn(scanner, request["portalPassThrough"][ccd])
        ccd_parameters = request["moduleSemantics"][ccd]["parameters"]
        self.assertEqual(
            ccd_parameters["portalPassModeByComponent"][scanner],
            "namedChannel",
        )
        channel_name = ccd_parameters["portalChannelByComponent"][scanner]
        channel = ccd_parameters["passageChannelsLocal"][channel_name]
        scanner_box = request["moduleSemantics"][scanner]["parameters"][
            "channelBodyBoxesLocal"
        ][0]
        clearance = request["minimumClearanceMeters"]
        allowed_delta_u = (
            channel["bounds"][0] + clearance - scanner_box["bounds"][0],
            channel["bounds"][2] - clearance - scanner_box["bounds"][2],
        )
        allowed_delta_v = (
            channel["bounds"][1] + clearance - scanner_box["bounds"][1],
            channel["bounds"][3] - clearance - scanner_box["bounds"][3],
        )
        self.assertLessEqual(allowed_delta_u[0], 1.1)
        self.assertGreaterEqual(allowed_delta_u[1], 1.1)
        self.assertLessEqual(allowed_delta_v[0], 0.805)
        self.assertGreaterEqual(allowed_delta_v[1], 0.805)
        self.assertFalse(allowed_delta_v[0] <= 0.6579303505 <= allowed_delta_v[1])
        self.assertLess(
            request["moduleSemantics"][scanner]["parameters"]["placementPriority"],
            ccd_parameters["placementPriority"],
        )
        retained = next(
            item
            for item in request["processConstraints"]
            if item["id"] == "a180-a200-scanner-ccd-channel-window"
        )
        self.assertTrue(retained["retainInReducedPrototype"])

    def setUp(self) -> None:
        evidence = json.loads(
            (
                ROOT
                / "demo/layout_previews/project02_9modules_direct_solved_v2_result.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.manifest = evidence["manifest"]

    def test_manifest_has_a600_fixed_first_and_nine_unique_modules(self) -> None:
        self.assertEqual(9, len(self.manifest))
        self.assertTrue(self.manifest[0]["fixedEnvironment"])
        self.assertEqual("A600", self.manifest[0]["componentCode"])
        self.assertEqual(9, len({item["componentName"] for item in self.manifest}))

    def test_exact_component_and_pose_audits_pass(self) -> None:
        components = [
            {"Name": row["componentName"], "Path": row["filePath"]}
            for row in self.manifest
        ]
        poses = [
            {
                "Name": row["componentName"],
                "Translation": row["translation"],
                "XAxis": row["xAxis"],
                "YAxis": row["yAxis"],
                "ZAxis": row["zAxis"],
            }
            for row in self.manifest
        ]
        self.assertTrue(MODULE.audit_top_level_components(components, self.manifest)["success"])
        self.assertTrue(MODULE.audit_poses(poses, self.manifest)["success"])

    def test_incremental_reuse_rejects_orientation_change(self) -> None:
        poses = [
            {
                "Name": row["componentName"],
                "XAxis": row["xAxis"],
                "YAxis": row["yAxis"],
                "ZAxis": row["zAxis"],
            }
            for row in self.manifest
        ]
        poses[1]["XAxis"] = [-value for value in poses[1]["XAxis"]]
        audit = MODULE.audit_source_orientation_compatibility(poses, self.manifest)
        self.assertFalse(audit["success"])
        self.assertEqual([self.manifest[1]["componentName"]], audit["orientationMismatchComponents"])

    def test_body_envelope_audit_detects_flexible_child_drift(self) -> None:
        poses = [
            {
                "Name": row["componentName"],
                "BoundingBoxWorld": list(row["boundingBoxWorld"]),
            }
            for row in self.manifest
        ]
        poses[1]["BoundingBoxWorld"][3] += 0.02
        audit = MODULE.audit_bounding_box_extents(poses, self.manifest)
        self.assertFalse(audit["success"])
        self.assertEqual([self.manifest[1]["componentName"]], audit["mismatchComponents"])

    def test_fixed_a600_insertion_uses_target_box_center(self) -> None:
        insertions = MODULE.insertion_components(self.manifest)
        a600 = self.manifest[0]
        box = a600["boundingBoxWorld"]
        expected = [(box[index] + box[index + 3]) / 2.0 for index in range(3)]
        self.assertEqual(expected, [insertions[0][key] for key in ("x", "y", "z")])

    def test_free_component_translation_is_corrected_from_actual_pose(self) -> None:
        current = []
        for row in self.manifest:
            translation = list(row["translation"])
            if not row["fixedEnvironment"]:
                translation[0] += 0.01
            current.append({"Name": row["componentName"], "Translation": translation})
        moves = MODULE.movement_deltas(current, self.manifest)
        self.assertEqual(8, len(moves))
        self.assertTrue(all(item["requiresMove"] for item in moves))
        self.assertTrue(all(abs(item["delta"][0] + 0.01) < 1e-12 for item in moves))

    def test_incremental_source_switches_to_target_before_mutation(self) -> None:
        source = ROOT / "demo/source-independent-v3.SLDASM"
        target = ROOT / "demo/source-independent-v4.SLDASM"
        arguments = MODULE.source_direct_save_as_arguments(source, target)
        self.assertEqual(str(source.resolve()), arguments["sourcePath"])
        self.assertEqual(str(target.resolve()), arguments["outputPath"])
        self.assertFalse(arguments["saveAsCopy"])

    def test_rigid_component_selectors_accept_code_and_exact_name(self) -> None:
        selected = MODULE.resolve_component_selectors(
            self.manifest,
            ["A100", "FL9A24D062A700.001-1", "A100"],
        )
        self.assertEqual(
            ["FL9A24D062A100.001-1", "FL9A24D062A700.001-1"],
            selected,
        )

    def test_rigid_component_selector_rejects_unknown_code(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.resolve_component_selectors(self.manifest, ["A999"])

    def test_pose_drift_is_rejected(self) -> None:
        poses = [
            {
                "Name": row["componentName"],
                "Translation": list(row["translation"]),
                "XAxis": row["xAxis"],
                "YAxis": row["yAxis"],
                "ZAxis": row["zAxis"],
            }
            for row in self.manifest
        ]
        poses[1]["Translation"][0] += 0.001
        audit = MODULE.audit_poses(poses, self.manifest)
        self.assertFalse(audit["success"])


if __name__ == "__main__":
    unittest.main()

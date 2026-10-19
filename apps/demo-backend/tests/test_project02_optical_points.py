import json
import unittest
from pathlib import Path

from demo_backend.project02_optical_points import (
    Project02OpticalPointError,
    apply_evidence_to_request,
    capture_entry_from_probe,
    evidence_readiness,
    infer_optical_axis_from_symmetric_faces,
    rank_optical_face_candidates,
    rebase_world_geometry_between_component_transforms,
    world_point_from_request,
)


ROOT = Path(__file__).resolve().parents[3]
GEOMETRY_PATH = ROOT / "demo" / "FL9A24D062A000_8components_real_geometry.json"


class Project02OpticalPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = json.loads(GEOMETRY_PATH.read_text(encoding="utf-8-sig"))

    def test_scanner_face_center_is_converted_to_module_local_point(self):
        expected_u, expected_v, expected_height = 0.041, -0.032, 0.217
        world_center = self._world_from_local(
            "FL9A24D062A180.001-1", expected_u, expected_v, expected_height
        )
        frame = self.capture["baseFrame"]
        probe = {
            "success": True,
            "leafComponentFullName": (
                "FL9A24D062A180.001-1/248004电气-sr-x100-0801A-1"
            ),
            "worldCenter": world_center,
            "worldNormal": frame["vAxis"],
            "localCenter": [0.0, 0.0, 0.0],
            "localNormal": [0.0, 0.0, 1.0],
            "area": 0.0004,
            "mappingPath": "face_mappings.json",
        }

        entry = capture_entry_from_probe(self.capture, "scanner", probe)

        self.assertAlmostEqual(entry["moduleLocalPointMeters"]["u"], expected_u)
        self.assertAlmostEqual(entry["moduleLocalPointMeters"]["v"], expected_v)
        self.assertAlmostEqual(
            entry["heightAboveModuleBottomMeters"], expected_height
        )
        self.assertAlmostEqual(entry["geometryFingerprint"]["areaSquareMeters"], 0.0004)
        self.assertEqual(entry["mappingPath"], "face_mappings.json")

    def test_scanner_selection_must_belong_to_identified_sr_x100_leaf(self):
        component = self._component("FL9A24D062A180.001-1")
        probe = {
            "success": True,
            "leafComponentFullName": "FL9A24D062A180.001-1/bracket-1",
            "worldCenter": component["bottomCenterWorld"],
            "worldNormal": self.capture["baseFrame"]["vAxis"],
        }
        with self.assertRaisesRegex(Project02OpticalPointError, "SR-X100"):
            capture_entry_from_probe(self.capture, "scanner", probe)

    def test_two_captured_points_update_request_without_false_engineering_confirmation(self):
        evidence = {
            "entries": {
                "scanner": {
                    "moduleLocalPointMeters": {"u": 0.01, "v": 0.02},
                    "heightAboveModuleBottomMeters": 0.21,
                },
                "barcode": {
                    "moduleLocalPointMeters": {"u": -0.03, "v": -0.04},
                    "heightAboveModuleBottomMeters": 0.19,
                },
            }
        }
        request = {
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {
                    "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
                    "parameters": {
                        "workingDistanceConfirmed": False,
                        "opticalAxisConfirmed": False,
                    },
                },
                "FL9A24D062A800.001-1": {
                    "points": {"barcode": {"u": 0.0, "v": 0.35}},
                    "parameters": {},
                },
            }
        }

        updated = apply_evidence_to_request(
            request, evidence, evidence_path="evidence.json"
        )
        scanner = updated["moduleSemantics"]["FL9A24D062A180.001-1"]
        transport = updated["moduleSemantics"]["FL9A24D062A800.001-1"]
        self.assertEqual(scanner["points"]["scanOrigin"], {"u": 0.01, "v": 0.02})
        self.assertTrue(scanner["parameters"]["scanOriginMeasured"])
        self.assertFalse(scanner["parameters"]["workingDistanceConfirmed"])
        self.assertFalse(scanner["parameters"]["opticalAxisConfirmed"])
        self.assertEqual(transport["points"]["barcode"], {"u": -0.03, "v": -0.04})
        self.assertTrue(transport["parameters"]["barcodeMeasured"])
        self.assertEqual(transport["parameters"]["barcodeSide"], "low")
        self.assertTrue(evidence_readiness(evidence)["pointCaptureComplete"])

    def test_cad_inferred_scanner_point_is_not_marked_directly_measured(self):
        evidence = {
            "entries": {
                "scanner": {
                    "moduleLocalPointMeters": {"u": -0.0365, "v": -0.2214},
                    "heightAboveModuleBottomMeters": 0.2368,
                    "measurementStatus": "cad-inferred-symmetric-windows",
                }
            }
        }
        request = {
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {"points": {}, "parameters": {}}
            }
        }

        updated = apply_evidence_to_request(
            request, evidence, evidence_path="scanner-evidence.json"
        )
        parameters = updated["moduleSemantics"]["FL9A24D062A180.001-1"][
            "parameters"
        ]
        self.assertFalse(parameters["scanOriginMeasured"])
        self.assertTrue(parameters["scanOriginCadInferred"])
        self.assertEqual(
            parameters["scanOriginMeasurementStatus"],
            "cad-inferred-symmetric-windows",
        )
        self.assertEqual(
            parameters["scanOriginHeightSource"],
            "cad-inferred-symmetric-windows",
        )
        self.assertNotIn("scanOriginHeightMetersSource", parameters)

    def test_world_point_from_request_uses_source_layout_frame(self):
        request = {
            "moduleSemantics": {
                "FL9A24D062A800.001-1": {
                    "points": {"barcode": {"u": 0.03, "v": -0.04}},
                    "parameters": {"barcodeHeightMeters": 0.2},
                }
            }
        }
        expected = self._world_from_local(
            "FL9A24D062A800.001-1", 0.03, -0.04, 0.2
        )
        actual = world_point_from_request(
            self.capture,
            request,
            "FL9A24D062A800.001-1",
            "barcode",
            "barcodeHeightMeters",
        )
        for actual_item, expected_item in zip(actual, expected):
            self.assertAlmostEqual(actual_item, expected_item)

    def test_optical_candidate_ranking_prefers_aligned_in_range_face(self):
        faces = [
            {
                "index": 4,
                "worldCenter": [0.0, 0.0, 0.0],
                "worldNormal": [1.0, 0.0, 0.0],
                "area": 0.0005,
            },
            {
                "index": 7,
                "worldCenter": [0.02, 0.0, 0.0],
                "worldNormal": [0.0, 1.0, 0.0],
                "area": 0.0005,
            },
            {
                "index": 9,
                "worldCenter": [0.0, 0.0, 0.0],
                "worldNormal": [1.0, 0.0, 0.0],
                "area": 0.02,
            },
        ]
        ranked = rank_optical_face_candidates(faces, [0.3, 0.0, 0.0])
        self.assertEqual(ranked[0]["source"]["index"], 4)
        self.assertAlmostEqual(ranked[0]["normalAlignment"], 1.0)
        self.assertTrue(ranked[0]["workingDistanceInRange"])
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])

    def test_reviewed_local_direction_prefers_face_on_confirmed_optical_side(self):
        faces = [
            {
                "index": 0,
                "worldCenter": [0.0, 0.0, 0.0],
                "worldNormal": [0.0, 1.0, 0.0],
                "localCenter": [0.0, 0.001, 0.0],
                "localNormal": [0.0, 1.0, 0.0],
                "area": 0.0012,
            },
            {
                "index": 1,
                "worldCenter": [0.0, 0.03, 0.0],
                "worldNormal": [0.0, 1.0, 0.0],
                "localCenter": [0.0, 0.04, 0.0],
                "localNormal": [0.0, 1.0, 0.0],
                "area": 0.0012,
            },
        ]

        ranked = rank_optical_face_candidates(
            faces,
            [0.0, 0.3, 0.0],
            expected_local_direction=[0.0, 1.0, 0.0],
            expected_local_side_direction=[0.0, -1.0, 0.0],
        )

        self.assertEqual(ranked[0]["source"]["index"], 0)
        self.assertAlmostEqual(ranked[0]["reviewedAxisAlignment"], 1.0)
        self.assertAlmostEqual(ranked[0]["reviewedSideScore"], 1.0)

    def test_symmetric_window_faces_infer_central_optical_axis(self):
        left = {
            "LocalCenter": [-0.010884848484847772, 0.0003, -0.0206],
            "LocalNormal": [0.0, 1.0, 0.0],
            "Area": 4.502226568421519e-05,
        }
        right = {
            "LocalCenter": [0.008484848484849605, 0.0003, -0.0206],
            "LocalNormal": [0.0, 1.0, 0.0],
            "Area": 4.502226568420328e-05,
        }

        inferred = infer_optical_axis_from_symmetric_faces(left, right)

        self.assertAlmostEqual(inferred["localCenterMeters"][0], -0.0012)
        self.assertAlmostEqual(inferred["localCenterMeters"][1], 0.0003)
        self.assertAlmostEqual(inferred["localCenterMeters"][2], -0.0206)
        self.assertEqual(inferred["localOpticalAxisLine"], [0.0, 1.0, 0.0])
        self.assertFalse(inferred["opticalAxisSignResolved"])
        self.assertAlmostEqual(
            inferred["anchorSeparationMeters"], 0.019369696969697377
        )
        self.assertLess(inferred["relativeAreaDifference"], 1e-12)

    def test_world_optical_point_is_rebased_between_two_module_poses(self):
        source_pose = [
            1.0, 0.0, 0.0,
            0.0, 1.0, 0.0,
            0.0, 0.0, 1.0,
            10.0, 20.0, 30.0,
            1.0, 0.0, 0.0, 0.0,
        ]
        target_pose = [
            0.0, 1.0, 0.0,
            -1.0, 0.0, 0.0,
            0.0, 0.0, 1.0,
            2.0, 3.0, 4.0,
            1.0, 0.0, 0.0, 0.0,
        ]

        rebased = rebase_world_geometry_between_component_transforms(
            [11.0, 22.0, 33.0], [0.0, 1.0, 0.0], source_pose, target_pose
        )

        self.assertEqual(rebased["componentLocalPoint"], [1.0, 2.0, 3.0])
        self.assertEqual(rebased["worldPoint"], [0.0, 4.0, 7.0])
        self.assertEqual(rebased["worldDirection"], [-1.0, 0.0, 0.0])

    def _world_from_local(
        self, component_name: str, local_u: float, local_v: float, height: float
    ) -> list[float]:
        component = self._component(component_name)
        frame = self.capture["baseFrame"]
        bottom = component["bottomCenterWorld"]
        return [
            bottom[index]
            + local_u * frame["uAxis"][index]
            + local_v * frame["vAxis"][index]
            + height * frame["normal"][index]
            for index in range(3)
        ]

    def _component(self, name: str) -> dict:
        return next(
            item for item in self.capture["components"] if item["componentName"] == name
        )


if __name__ == "__main__":
    unittest.main()

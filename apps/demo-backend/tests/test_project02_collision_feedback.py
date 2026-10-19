from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project02_collision_feedback import (
    apply_collision_feedback,
    build_collision_feedback,
    evaluate_feedback_gate,
)


def _batch() -> dict:
    return {
        "assemblyPath": "candidate.SLDASM",
        "requestedPairCount": 2,
        "completedPairCount": 2,
        "hardFailureCount": 0,
        "pairs": [
            {
                "pair": ["FL9A24D062A180.001-1", "FL9A24D062A200.001-1"],
                "hasInterference": True,
                "interferingBodyPairCount": 5,
                "failedBodyPairCount": 0,
                "exactCheckComplete": True,
                "outputPath": "a180_a200.json",
            },
            {
                "pair": ["FL9A24D062A200.001-1", "FL9A24D062A300.001-1"],
                "hasInterference": False,
                "interferingBodyPairCount": 0,
                "failedBodyPairCount": 0,
                "exactCheckComplete": True,
                "outputPath": "a200_a300.json",
            },
        ],
    }


class Project02CollisionFeedbackTests(unittest.TestCase):
    def _write_batch(self, payload: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "batch.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_only_complete_exact_interference_is_promoted(self) -> None:
        feedback = build_collision_feedback(self._write_batch(_batch()))
        self.assertEqual(len(feedback["confirmedCollisionPairs"]), 1)
        self.assertEqual(
            [feedback["confirmedCollisionPairs"][0]["firstCode"], feedback["confirmedCollisionPairs"][0]["secondCode"]],
            ["A180", "A200"],
        )

    def test_incomplete_batch_is_rejected(self) -> None:
        batch = _batch()
        batch["completedPairCount"] = 1
        with self.assertRaisesRegex(ValueError, "incomplete"):
            build_collision_feedback(self._write_batch(batch))

    def test_feedback_adds_symmetric_hard_pairs_and_removes_orientation(self) -> None:
        feedback = build_collision_feedback(
            self._write_batch(_batch()), forbidden_rotations_by_code={"A700": [180]}
        )
        request = {
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {"parameters": {}},
                "FL9A24D062A200.001-1": {"parameters": {}},
                "FL9A24D062A300.001-1": {"parameters": {}},
                "FL9A24D062A700.001-1": {
                    "allowedRotationDegrees": [0, 180],
                    "parameters": {},
                },
            }
        }
        original = copy.deepcopy(request)
        hardened, metadata = apply_collision_feedback(request, feedback)
        self.assertEqual(request, original)
        self.assertEqual(
            hardened["moduleSemantics"]["FL9A24D062A700.001-1"]["allowedRotationDegrees"],
            [0],
        )
        self.assertIn(
            "FL9A24D062A200.001-1",
            hardened["moduleSemantics"]["FL9A24D062A180.001-1"]["parameters"]["hardOccupancyClearanceWith"],
        )
        self.assertEqual(metadata["confirmedHardOccupancyPairs"], [["A180", "A200"]])

    def test_gate_rejects_forbidden_orientation_and_confirmed_pair_risk(self) -> None:
        feedback = build_collision_feedback(
            self._write_batch(_batch()), forbidden_rotations_by_code={"A700": [180]}
        )
        preview = {
            "solutions": [
                {
                    "rank": 1,
                    "modules": [
                        {
                            "componentName": "FL9A24D062A700.001-1",
                            "center": [0, 0],
                            "rotationQuarters": 2,
                        }
                    ],
                    "conditionalLeafAabbRisks": [
                        {"firstCode": "A180", "secondCode": "A200"}
                    ],
                }
            ]
        }
        result = evaluate_feedback_gate(preview, feedback)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["solutions"][0]["orientationViolations"]), 1)
        self.assertEqual(result["solutions"][0]["confirmedPairRisks"], [["A180", "A200"]])

    def test_collision_in_forbidden_orientation_is_not_globalized(self) -> None:
        batch = _batch()
        batch["pairs"].append(
            {
                "pair": ["FL9A24D062A300.001-1", "FL9A24D062A700.001-1"],
                "hasInterference": True,
                "interferingBodyPairCount": 7,
                "failedBodyPairCount": 0,
                "exactCheckComplete": True,
                "outputPath": "a300_a700.json",
            }
        )
        batch["requestedPairCount"] = 3
        batch["completedPairCount"] = 3
        rejected = {
            "solutions": [
                {
                    "modules": [
                        {"componentName": "FL9A24D062A300.001-1", "center": [0, 0], "rotationQuarters": 0},
                        {"componentName": "FL9A24D062A700.001-1", "center": [0, 0], "rotationQuarters": 2},
                    ]
                }
            ],
        }
        feedback = build_collision_feedback(
            self._write_batch(batch),
            rejected_preview=rejected,
            forbidden_rotations_by_code={"A700": [180]},
        )
        scoped = next(
            row for row in feedback["confirmedCollisionPairs"] if row["secondCode"] == "A700"
        )
        self.assertFalse(scoped["globalHardeningEligible"])
        request = {
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {"parameters": {}},
                "FL9A24D062A200.001-1": {"parameters": {}},
                "FL9A24D062A300.001-1": {"parameters": {}},
                "FL9A24D062A700.001-1": {"allowedRotationDegrees": [0, 180], "parameters": {}},
            }
        }
        hardened, metadata = apply_collision_feedback(request, feedback)
        self.assertEqual([["A300", "A700"]], metadata["orientationScopedCollisionPairs"])
        self.assertNotIn(
            "hardOccupancyClearanceWith",
            hardened["moduleSemantics"]["FL9A24D062A300.001-1"]["parameters"],
        )

    def test_conditional_brep_collision_excludes_failed_relative_pose_only(self) -> None:
        batch = _batch()
        rejected = {
            "solutions": [
                {
                    "modules": [
                        {
                            "componentName": "FL9A24D062A180.001-1",
                            "center": [1.0, 2.0],
                            "rotationQuarters": 0,
                        },
                        {
                            "componentName": "FL9A24D062A200.001-1",
                            "center": [0.25, 0.5],
                            "rotationQuarters": 0,
                        },
                    ]
                }
            ],
        }
        request = {
            "staticCollisionPolicy": {
                "brepOnAabbOverlapPairs": [
                    ["FL9A24D062A180.001-1", "FL9A24D062A200.001-1"]
                ]
            },
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {"parameters": {}},
                "FL9A24D062A200.001-1": {"parameters": {}},
                "FL9A24D062A300.001-1": {"parameters": {}},
            },
        }
        feedback = build_collision_feedback(
            self._write_batch(batch), rejected_preview=rejected, request=request
        )
        row = feedback["confirmedCollisionPairs"][0]
        self.assertFalse(row["globalHardeningEligible"])
        self.assertTrue(row["poseLocalExclusionEligible"])
        hardened, metadata = apply_collision_feedback(request, feedback)
        self.assertEqual([], metadata["confirmedHardOccupancyPairs"])
        self.assertEqual(1, len(metadata["relativePoseExclusions"]))
        constraint = hardened["processConstraints"][0]
        self.assertEqual("relativeAnchorExclusionWindow", constraint["type"])
        self.assertTrue(constraint["retainInReducedPrototype"])
        self.assertAlmostEqual(0.745, constraint["minDeltaU"])
        self.assertAlmostEqual(1.505, constraint["maxDeltaV"])
        offsets = hardened["moduleSemantics"]["FL9A24D062A180.001-1"][
            "parameters"
        ]["candidateDirectionalOffsetsMeters"]
        self.assertIn([0.0051, 0.0], offsets)
        self.assertIn([0.0, -0.0051], offsets)

        failed = evaluate_feedback_gate(rejected, feedback)
        self.assertFalse(failed["passed"])
        shifted = copy.deepcopy(rejected)
        shifted["solutions"][0]["modules"][0]["center"] = [1.02, 2.0]
        passed = evaluate_feedback_gate(shifted, feedback)
        self.assertTrue(passed["passed"])

    def test_installation_contact_collision_excludes_failed_relative_pose_only(self) -> None:
        batch = _batch()
        batch["requestedPairCount"] = 1
        batch["completedPairCount"] = 1
        batch["pairs"] = [batch["pairs"][0]]
        batch["pairs"][0]["pair"] = [
            "FL9A24D062A500.001-1",
            "FL9A24D062A600.001-1",
        ]
        rejected = {
            "staticCollisionPolicy": {
                "installationContactPairs": [
                    ["FL9A24D062A500.001-1", "FL9A24D062A600.001-1"]
                ]
            },
            "solutions": [
                {
                    "modules": [
                        {
                            "componentName": "FL9A24D062A500.001-1",
                            "center": [0.6, 0.4],
                            "rotationQuarters": 0,
                        },
                        {
                            "componentName": "FL9A24D062A600.001-1",
                            "center": [0.1, 0.2],
                            "rotationQuarters": 0,
                        },
                    ]
                }
            ],
            "caseAnchor": {"appliedTranslation": [0.3, -0.2]},
        }
        request = {
            "staticCollisionPolicy": {
                "brepOnAabbOverlapPairs": [
                    ["FL9A24D062A500.001-1", "FL9A24D062A700.001-1"]
                ]
            },
            "fixedEnvironment": {"enabled": True, "componentCode": "A600"},
            "moduleSemantics": {
                "FL9A24D062A500.001-1": {
                    "parameters": {
                        "fixedEnvironmentClearAnchor": [0.0, 0.0],
                        "serviceClusterId": "service-cluster",
                    }
                },
                "FL9A24D062A700.001-1": {
                    "parameters": {"serviceClusterId": "service-cluster"}
                },
                "FL9A24D062A300.001-1": {
                    "parameters": {"serviceClusterId": "service-cluster"}
                },
            },
        }

        feedback = build_collision_feedback(
            self._write_batch(batch), rejected_preview=rejected, request=request
        )
        row = feedback["confirmedCollisionPairs"][0]

        self.assertTrue(row["poseLocalExclusionEligible"])
        self.assertFalse(row["globalHardeningEligible"])
        hardened, metadata = apply_collision_feedback(request, feedback)
        self.assertEqual([], metadata["confirmedHardOccupancyPairs"])
        self.assertEqual(1, len(metadata["relativePoseExclusions"]))
        self.assertEqual(
            "anchorExclusionWindow",
            hardened["processConstraints"][0]["type"],
        )
        constraint = hardened["processConstraints"][0]
        self.assertEqual("A600", constraint["fixedReferenceCode"])
        self.assertAlmostEqual(0.295, constraint["minU"])
        self.assertAlmostEqual(0.605, constraint["maxV"])
        self.assertEqual("pre-case-anchor-solver", constraint["coordinateFrame"])
        self.assertEqual([0.3, -0.2], constraint["caseAnchorAppliedTranslation"])
        self.assertAlmostEqual(0.595, constraint["postCaseAnchorWindow"]["minU"])
        self.assertAlmostEqual(0.605, constraint["postCaseAnchorWindow"]["maxU"])
        self.assertAlmostEqual(0.395, constraint["postCaseAnchorWindow"]["minV"])
        self.assertAlmostEqual(0.405, constraint["postCaseAnchorWindow"]["maxV"])
        self.assertEqual([0.0, 0.0], constraint["prototypeClearAnchor"])
        self.assertEqual(
            "prototype-validated-fixed-environment-clear-anchor",
            constraint["escapeStrategy"],
        )
        self.assertEqual(
            [[-0.6, -0.4]],
            hardened["moduleSemantics"]["FL9A24D062A500.001-1"]["parameters"][
                "candidateDirectionalOffsetsMeters"
            ],
        )
        for coupled_name in (
            "FL9A24D062A700.001-1",
            "FL9A24D062A300.001-1",
        ):
            coupled_parameters = hardened["moduleSemantics"][coupled_name][
                "parameters"
            ]
            self.assertEqual(
                [[-0.6, -0.4]],
                coupled_parameters["candidateDirectionalOffsetsMeters"],
            )
            self.assertEqual(
                "FL9A24D062A500.001-1",
                coupled_parameters["collisionFeedbackCoupledSourceComponent"],
            )
            self.assertEqual(
                "service-cluster",
                coupled_parameters["collisionFeedbackCoupledServiceClusterId"],
            )
        self.assertEqual(
            ["FL9A24D062A300.001-1", "FL9A24D062A700.001-1"],
            constraint["coupledCandidateComponents"],
        )

        self.assertFalse(evaluate_feedback_gate(rejected, feedback)["passed"])
        shifted = copy.deepcopy(rejected)
        shifted["solutions"][0]["modules"][0]["center"] = [0.62, 0.4]
        self.assertTrue(evaluate_feedback_gate(shifted, feedback)["passed"])

    def test_close_validated_clear_anchor_shrinks_installation_exclusion(self) -> None:
        batch = _batch()
        batch["requestedPairCount"] = 1
        batch["completedPairCount"] = 1
        batch["pairs"] = [batch["pairs"][0]]
        batch["pairs"][0]["pair"] = [
            "FL9A24D062A100.001-1",
            "FL9A24D062A600.001-1",
        ]
        rejected = {
            "solutions": [
                {
                    "modules": [
                        {
                            "componentName": "FL9A24D062A100.001-1",
                            "center": [0.6, 0.4],
                            "rotationQuarters": 0,
                        },
                        {
                            "componentName": "FL9A24D062A600.001-1",
                            "center": [0.1, 0.2],
                            "rotationQuarters": 0,
                        },
                    ]
                }
            ]
        }
        request = {
            "fixedEnvironment": {"enabled": True, "componentCode": "A600"},
            "staticCollisionPolicy": {
                "installationContactPairs": [
                    ["FL9A24D062A100.001-1", "FL9A24D062A600.001-1"]
                ]
            },
            "moduleSemantics": {
                "FL9A24D062A100.001-1": {
                    "parameters": {"fixedEnvironmentClearAnchor": [0.6025, 0.4]}
                },
                "FL9A24D062A600.001-1": {"parameters": {}},
            },
        }

        feedback = build_collision_feedback(
            self._write_batch(batch), rejected_preview=rejected, request=request
        )
        exclusion = feedback["confirmedCollisionPairs"][0][
            "relativePoseExclusion"
        ]
        self.assertAlmostEqual(0.001125, exclusion["effectiveHalfWidthMeters"][0])
        self.assertAlmostEqual(0.005, exclusion["effectiveHalfWidthMeters"][1])
        self.assertAlmostEqual(0.498875, exclusion["minDeltaU"])
        self.assertAlmostEqual(0.501125, exclusion["maxDeltaU"])
        self.assertFalse(evaluate_feedback_gate(rejected, feedback)["passed"])

        clear = copy.deepcopy(rejected)
        clear["solutions"][0]["modules"][0]["center"] = [0.6025, 0.4]
        self.assertTrue(evaluate_feedback_gate(clear, feedback)["passed"])

    def test_repeated_conditional_collision_escalates_candidate_escape(self) -> None:
        batch = _batch()
        rejected = {
            "solutions": [
                {
                    "modules": [
                        {
                            "componentName": "FL9A24D062A180.001-1",
                            "center": [1.0, 2.0],
                            "rotationQuarters": 0,
                        },
                        {
                            "componentName": "FL9A24D062A200.001-1",
                            "center": [0.25, 0.5],
                            "rotationQuarters": 0,
                        },
                    ]
                }
            ]
        }
        request = {
            "staticCollisionPolicy": {
                "brepOnAabbOverlapPairs": [
                    ["FL9A24D062A180.001-1", "FL9A24D062A200.001-1"]
                ]
            },
            "processConstraints": [
                {
                    "id": "previous-exclusion",
                    "type": "relativeAnchorExclusionWindow",
                    "component": "FL9A24D062A180.001-1",
                    "referenceComponent": "FL9A24D062A200.001-1",
                    "minDeltaU": 0.70,
                    "maxDeltaU": 0.71,
                    "minDeltaV": 1.45,
                    "maxDeltaV": 1.46,
                    "hard": True,
                }
            ],
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {"parameters": {}},
                "FL9A24D062A200.001-1": {"parameters": {}},
                "FL9A24D062A300.001-1": {"parameters": {}},
            },
        }
        feedback = build_collision_feedback(
            self._write_batch(batch), rejected_preview=rejected, request=request
        )

        hardened, metadata = apply_collision_feedback(request, feedback)

        constraint = metadata["relativePoseExclusions"][0]
        self.assertEqual(2, constraint["escapeEscalationIndex"])
        offsets = hardened["moduleSemantics"]["FL9A24D062A180.001-1"][
            "parameters"
        ]["candidateDirectionalOffsetsMeters"]
        self.assertIn([0.0102, 0.0], offsets)
        self.assertNotIn([0.0051, 0.0], offsets)

    def test_exact_leaf_aabbs_expand_relative_pose_exclusion(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        detail_path = root / "a180_a200.json"
        detail_path.write_text(
            json.dumps(
                {
                    "InterferingBodyPairs": [
                        {
                            "FirstComponent": {
                                "Name": "FL9A24D062A180.001-1/leaf-a"
                            },
                            "SecondComponent": {
                                "Name": "FL9A24D062A200.001-1/leaf-b"
                            },
                            "FirstBoundingBoxWorld": [0.0, 0.0, 0.0, 0.2, 0.2, 0.2],
                            "SecondBoundingBoxWorld": [0.1, 0.1, 0.0, 0.3, 0.3, 0.2],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        batch = _batch()
        batch["requestedPairCount"] = 1
        batch["completedPairCount"] = 1
        batch["pairs"] = [batch["pairs"][0]]
        batch["pairs"][0]["outputPath"] = str(detail_path)
        base_frame = {
            "origin": [0.0, 0.0, 0.0],
            "uAxis": [1.0, 0.0, 0.0],
            "vAxis": [0.0, 1.0, 0.0],
        }
        rejected = {
            "solutions": [
                {
                    "modules": [
                        {
                            "componentName": "FL9A24D062A180.001-1",
                            "center": [1.0, 2.0],
                            "rotationQuarters": 0,
                        },
                        {
                            "componentName": "FL9A24D062A200.001-1",
                            "center": [0.25, 0.5],
                            "rotationQuarters": 0,
                        },
                    ]
                }
            ],
        }
        request = {
            "minimumClearanceMeters": 0.01,
            "staticCollisionPolicy": {
                "brepOnAabbOverlapPairs": [
                    ["FL9A24D062A180.001-1", "FL9A24D062A200.001-1"]
                ]
            },
            "moduleSemantics": {
                "FL9A24D062A180.001-1": {"parameters": {}},
                "FL9A24D062A200.001-1": {"parameters": {}},
            },
        }

        feedback = build_collision_feedback(
            self._write_batch(batch),
            rejected_preview=rejected,
            request=request,
            base_frame=base_frame,
        )
        exclusion = feedback["confirmedCollisionPairs"][0]["relativePoseExclusion"]

        self.assertEqual(
            "exact-leaf-aabb-common-axis-clearance", exclusion["derivation"]
        )
        self.assertAlmostEqual(0.639999, exclusion["minDeltaU"])
        self.assertAlmostEqual(1.060001, exclusion["maxDeltaU"])
        self.assertAlmostEqual(1.389999, exclusion["minDeltaV"])
        self.assertAlmostEqual(1.810001, exclusion["maxDeltaV"])
        hardened, metadata = apply_collision_feedback(request, feedback)
        offsets = hardened["moduleSemantics"]["FL9A24D062A180.001-1"][
            "parameters"
        ]["candidateDirectionalOffsetsMeters"]
        self.assertEqual(4, len(offsets))
        self.assertEqual(
            4,
            hardened["moduleSemantics"]["FL9A24D062A180.001-1"][
                "parameters"
            ]["collisionFeedbackPriorityCandidateCount"],
        )
        for raw, escaped in zip(exclusion["candidateEscapeOffsetsMeters"], offsets):
            for raw_axis, escaped_axis in zip(raw, escaped):
                if abs(raw_axis) <= 1e-12:
                    self.assertEqual(0.0, escaped_axis)
                else:
                    self.assertGreater(abs(escaped_axis), abs(raw_axis))
        self.assertEqual(
            exclusion["candidateEscapeOffsetsMeters"],
            metadata["relativePoseExclusions"][0]["rawCandidateEscapeOffsetsMeters"],
        )
        self.assertAlmostEqual(
            0.0001,
            metadata["relativePoseExclusions"][0]["escapeBoundaryMarginMeters"],
        )
        self.assertEqual(
            "exact-leaf-aabb-common-axis-clearance",
            metadata["relativePoseExclusions"][0]["escapeStrategy"],
        )


if __name__ == "__main__":
    unittest.main()

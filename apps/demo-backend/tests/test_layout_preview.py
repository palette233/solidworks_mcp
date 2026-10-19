from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from demo_backend.constraint_layout import generate_constraint_layout
from demo_backend.layout_preview import (
    _load_solver_warm_start,
    approve_case_preview,
    build_source_independent_options,
    load_case_preview,
    load_case_verification_plan,
    solve_case_preview,
)


ROOT = Path(__file__).resolve().parents[3]


class LayoutPreviewTests(unittest.TestCase):
    def test_solver_warm_start_reverses_post_solve_bias(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solution.json"
            path.write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "componentName": "GANTRY",
                                "layout2d": {"x": 10.0, "y": 20.0, "thetaDegrees": 0.0},
                            },
                            {
                                "componentName": "CCD",
                                "layout2d": {"x": 11.0, "y": 22.0, "thetaDegrees": 90.0},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            request = {
                "sourceIndependentPolicy": {
                    "warmStartReplayResultPath": str(path),
                    "warmStartKind": "previousSolverReplayResult",
                },
                "roleOverrides": {"GANTRY": "gantry"},
                "moduleSemantics": {
                    "GANTRY": {"parameters": {}},
                    "CCD": {"parameters": {"postSolveAnchorBiasV": 0.014}},
                },
            }
            placements = _load_solver_warm_start(request, ROOT)
        ccd = next(item for item in placements if item["componentName"] == "CCD")
        self.assertAlmostEqual(1.0, ccd["x"])
        self.assertAlmostEqual(1.986, ccd["y"])

    def test_project02_preview_uses_a800_installation_frame_anchor(self):
        preview = solve_case_preview(ROOT, "project02", persist=False)

        self.assertEqual(preview["caseId"], "project02")
        self.assertFalse(preview["sourceIndependent"])
        self.assertTrue(preview["relativeConstraintsSourceIndependent"])
        self.assertTrue(preview["prototypePoseUsedForSolving"])
        self.assertEqual(
            preview["caseAnchor"]["componentName"],
            "FL9A24D062A800.001-1",
        )
        self.assertEqual(preview["caseAnchor"]["targetKind"], "installationFramePoint")
        self.assertFalse(preview["caseAnchor"]["exactSourcePoseReuse"])
        self.assertFalse(preview["caseAnchor"]["sourceCapturePoseReadForAnchor"])
        self.assertAlmostEqual(preview["caseAnchor"]["achievedAnchor"][0], 0.72)
        self.assertAlmostEqual(preview["caseAnchor"]["achievedAnchor"][1], -0.405)
        for solution in preview["solutions"]:
            transport = next(
                item for item in solution["modules"] if item["code"] == "A800"
            )
            self.assertAlmostEqual(transport["center"][0], 0.72)
            self.assertAlmostEqual(transport["center"][1], -0.405)
        self.assertTrue(preview["inverseGantryCoverage"]["selectedInside"])
        # A700 now contributes separate cleaning and A730 weighing service points.
        self.assertEqual(preview["inverseGantryCoverage"]["targetPointCount"], 7)
        self.assertEqual(preview["solverMode"], "bounded-joint-backtracking-top-k")
        self.assertEqual(len(preview["solutions"]), 3)
        self.assertTrue(
            all("predictedConditionalBrepPairCount" in item for item in preview["solutions"])
        )
        self.assertTrue(
            all("predictedConditionalLeafAabbHitCount" in item for item in preview["solutions"])
        )
        self.assertEqual(
            preview["solutions"][0]["predictedConditionalBrepPairCount"],
            17,
        )
        self.assertEqual(preview["jointSearchSummary"]["solutionCount"], 3)
        self.assertGreater(preview["jointSearchSummary"]["exploredNodeCount"], 0)
        self.assertIsInstance(preview["jointSearchSummary"]["collisionMatrix"], dict)
        self.assertTrue(all(len(item["modules"]) == 9 for item in preview["solutions"]))
        self.assertEqual(preview["metrics"]["componentCount"], 9)
        self.assertEqual(preview["fixedEnvironment"]["componentCode"], "A600")
        self.assertEqual(preview["fixedEnvironment"]["degreesOfFreedom"], 0)
        self.assertTrue(preview["fixedEnvironmentValidation"]["hardFeasible"])
        self.assertEqual(preview["metrics"]["fixedEnvironmentPassed"], 8)
        self.assertEqual(preview["metrics"]["fixedEnvironmentTotal"], 8)
        self.assertEqual(preview["metrics"]["processPassed"], 32)
        self.assertEqual(preview["metrics"]["processTotal"], 32)
        self.assertEqual(preview["metrics"]["spatialPassed"], 13)
        self.assertEqual(preview["metrics"]["spatialTotal"], 13)
        self.assertEqual(preview["metrics"]["interactionPassed"], 65)
        self.assertEqual(preview["metrics"]["interactionTotal"], 65)
        self.assertEqual(preview["metrics"]["strictAabbPairCount"], 10)
        self.assertEqual(preview["metrics"]["conditionalBrepPairCount"], 18)
        self.assertEqual(preview["metrics"]["installationContactPairCount"], 8)
        self.assertEqual(preview["metrics"]["solverBrepCallCount"], 0)
        self.assertEqual(preview["metrics"]["predictedConditionalLeafAabbHitCount"], 30)
        sequence = preview["assemblySequencePlan"]
        self.assertTrue(sequence["operationSideCapacityEstimated"])
        self.assertTrue(sequence["serviceAccessEstimated"])
        self.assertTrue(sequence["dualValveReachEstimated"])
        self.assertEqual(sequence["selectedServiceSide"], "front")
        capacity = sequence["operationSideCapacity"]
        self.assertLess(
            capacity["operationSideGrossBand"]["grossDepthMeters"],
            capacity["prototypeServiceCluster"]["requiredDepthFromSafeFrontMeters"],
        )
        self.assertTrue(
            capacity["capacityDecision"]["prototypeDemonstratesNonConvexFit"]
        )
        self.assertEqual(
            [
                (item["firstCode"], item["secondCode"], item["hitCount"])
                for item in preview["conditionalLeafAabbRisks"]
            ],
            [("A500", "A700", 28), ("A700", "A800", 2)],
        )
        self.assertTrue(preview["metrics"]["hardFeasible"])
        self.assertFalse(preview["metrics"]["productionReady"])

    def test_project02_preview_exposes_layout_review_risks(self):
        preview = solve_case_preview(ROOT, "project02", persist=False)
        review_titles = {item["title"] for item in preview["reviewItems"]}
        module_codes = {item["code"] for item in preview["modules"]}
        gantry = next(item for item in preview["modules"] if item["code"] == "A100")

        self.assertEqual(
            module_codes,
            {"A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"},
        )
        self.assertIn("传输模组中心性", review_titles)
        self.assertIn("CCD工艺轴线与有限越界", review_titles)
        self.assertIn("A300/A700相对工艺窗口", review_titles)
        self.assertIn("粗AABB重叠复核", review_titles)
        self.assertIn("2.5D交互复核", review_titles)
        self.assertIn("临时估算参数", review_titles)
        self.assertIn("A100逆向覆盖门禁", review_titles)
        self.assertLessEqual(preview["metrics"]["transportCenterOffsetMeters"], 0.05)
        self.assertGreaterEqual(preview["metrics"]["portalGantryOverlapRatio"], 0.85)
        self.assertLessEqual(preview["metrics"]["portalCenterOffsetMeters"], 0.18)
        self.assertLessEqual(preview["metrics"]["portalMaximumOverhangMeters"], 0.16)
        self.assertGreaterEqual(preview["metrics"]["serviceClusterDeltaUMeters"], -0.020001)
        self.assertLessEqual(preview["metrics"]["serviceClusterDeltaUMeters"], 0.020001)
        self.assertGreaterEqual(preview["metrics"]["serviceClusterDeltaVMeters"], 0.079999)
        self.assertLessEqual(preview["metrics"]["serviceClusterDeltaVMeters"], 0.140001)
        self.assertLessEqual(preview["metrics"]["allowedOverlapReviewCount"], 18)
        self.assertEqual(gantry["regions"][0]["name"], "dualValveReach")
        a200 = next(item for item in preview["modules"] if item["code"] == "A200")
        a500 = next(item for item in preview["modules"] if item["code"] == "A500")
        a800 = next(item for item in preview["modules"] if item["code"] == "A800")
        self.assertIn("portalOpening", {item["name"] for item in a200["regions"]})
        self.assertEqual(a500["interactionEnvelope"]["source"], "semanticInteractionBounds")
        self.assertEqual(a500["hardBodyEnvelope"]["source"], "fullAabbBody")
        self.assertEqual(
            {item["id"] for item in a500["protectedSpaces"]},
            {"valve-vertical-approach", "operator-maintenance-side"},
        )
        self.assertEqual(
            a800["transportSweepEnvelope"]["source"],
            "semanticTransportSweepBounds",
        )
        self.assertEqual(
            a800["transportStaticKeepoutEnvelope"]["source"],
            "semanticTransportStaticKeepoutBounds",
        )
        sweep_diagnostics = [
            item
            for item in preview["diagnostics"]
            if item["type"] == "transportSweepClearance"
        ]
        self.assertEqual(len(sweep_diagnostics), 3)
        self.assertTrue(all(item["success"] for item in sweep_diagnostics))
        static_keepout_diagnostics = [
            item
            for item in preview["diagnostics"]
            if item["type"] == "transportStaticKeepoutClearance"
        ]
        self.assertEqual(len(static_keepout_diagnostics), 3)
        self.assertTrue(all(item["success"] for item in static_keepout_diagnostics))
        multi_box_diagnostics = [
            item
            for item in preview["diagnostics"]
            if item["type"] == "multiBoxClearance"
        ]
        self.assertEqual(len(multi_box_diagnostics), 10)
        self.assertTrue(all(item["success"] for item in multi_box_diagnostics))
        a300_a700 = next(
            item
            for item in multi_box_diagnostics
            if {
                item.get("firstComponent"),
                item.get("secondComponent"),
            }
            == {
                "FL9A24D062A300.001-1",
                "FL9A24D062A700.001-1",
            }
        )
        self.assertEqual(a300_a700["resolution"], "separatedLeafBodyOccupancyBoxes")
        self.assertFalse(a300_a700["hard"])
        self.assertTrue(a300_a700["conditionalBrepPair"])
        self.assertTrue(a300_a700["requiresCadInterferenceValidation"])
        structure_channels = [
            item
            for item in preview["diagnostics"]
            if item["type"] == "structureChannelContainment"
        ]
        self.assertEqual(len(structure_channels), 1)
        self.assertTrue(structure_channels[0]["success"])
        self.assertEqual(
            structure_channels[0]["portalCheck"]["channelName"],
            "scannerStructureChannel",
        )
        post_solve_diagnostics = [
            item
            for item in preview["diagnostics"]
            if item["type"] == "postSolveProjectionOverlap"
        ]
        self.assertEqual(len(post_solve_diagnostics), 0)
        deferred_leaf_overlaps = [
            item
            for item in multi_box_diagnostics
            if item.get("resolution") == "approximateLeafBodyOverlapDeferredToCad"
        ]
        self.assertEqual(len(deferred_leaf_overlaps), 0)
        self.assertTrue(all(item["success"] for item in deferred_leaf_overlaps))
        self.assertTrue(all(not item["hard"] for item in deferred_leaf_overlaps))
        self.assertTrue(
            all(item["requiresCadInterferenceValidation"] for item in deferred_leaf_overlaps)
        )
        self.assertEqual(
            len(preview["postSolveAllowedProjectedOverlapPairs"]),
            2,
        )
        strict_aabb_diagnostics = [
            item
            for item in preview["diagnostics"]
            if item["type"] == "strictInflatedAabbSeparation"
        ]
        self.assertEqual(len(strict_aabb_diagnostics), 10)
        self.assertTrue(all(item["success"] for item in strict_aabb_diagnostics))
        self.assertTrue(
            all(not item["requiresCadInterferenceValidation"] for item in strict_aabb_diagnostics)
        )

    def test_reduced_prototype_profile_removes_layout_copy_dependencies(self):
        preview = solve_case_preview(
            ROOT,
            "project02",
            persist=False,
            profile="reduced-prototype",
        )

        profile = preview["solveProfile"]
        self.assertEqual(profile["name"], "reduced-prototype")
        self.assertTrue(profile["removedWarmStart"])
        self.assertEqual(len(profile["removedConstraintIds"]), 6)
        self.assertNotIn(
            "a180-a200-scanner-ccd-channel-window",
            profile["removedConstraintIds"],
        )
        self.assertEqual(len(preview["solutions"]), 3)
        self.assertTrue(preview["metrics"]["hardFeasible"])
        self.assertEqual(preview["metrics"]["processPassed"], 26)
        self.assertEqual(preview["metrics"]["processTotal"], 26)
        self.assertFalse(preview["sourceCapturePoseUsedForAnchoring"])
        self.assertGreater(preview["timing"]["durationSeconds"], 0.0)
        self.assertIn(
            "constraint-layout-solve",
            {item["name"] for item in preview["timing"]["stages"]},
        )

    def test_shared_option_builder_forces_source_independent_mode(self):
        request = json.loads(
            (ROOT / "demo" / "FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8"
            )
        )
        options = build_source_independent_options(request)

        self.assertTrue(options.source_position_independent)
        self.assertFalse(options.prefer_source_layout)
        self.assertEqual(options.minimum_functional_gantry_overlap_ratio, 1.0)
        self.assertEqual(options.minimum_functional_gantry_boundary_clearance_meters, 0.01)
        self.assertEqual(options.maximum_transport_gantry_center_offset_meters, 0.05)
        self.assertEqual(options.maximum_portal_gantry_center_offset_meters, 0.18)
        self.assertEqual(options.maximum_portal_gantry_overhang_meters, 0.162)
        self.assertEqual(options.allowed_projected_overlap_pairs, ())
        self.assertTrue(options.joint_candidate_search)
        self.assertEqual(options.joint_candidate_limit, 24)
        self.assertEqual(options.maximum_layout_solutions, 3)
        self.assertEqual(len(options.warm_start_placements), 8)
        self.assertEqual(options.joint_search_time_limit_seconds, 90.0)
        self.assertEqual(options.warm_start_locked_components, ())
        self.assertEqual(
            options.case_anchor_component_name,
            "FL9A24D062A800.001-1",
        )
        self.assertEqual(
            options.module_semantics["T401AA-07388-0-1"]["preferredSide"],
            "low",
        )

    def test_service_side_branch_uses_operation_side_or_opposite_from_capacity(self):
        request = json.loads(
            (ROOT / "demo" / "FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8"
            )
        )
        sequence = request["assemblySequencePolicy"]
        sequence["operationFace"]["legacySolverSide"] = "low"
        sequence["operationSideCapacity"] = {
            "availableWidthMeters": 0.4,
            "requiredWidthMeters": 0.5,
            "confirmed": True,
        }

        options = build_source_independent_options(request)

        for component_name in (
            "FL9A24D062A700.001-1",
            "FL9A24D062A500.001-1",
            "FL9A24D062A300.001-1",
        ):
            semantic = options.module_semantics[component_name]
            self.assertEqual(semantic["preferredSide"], "high")
            self.assertEqual(
                semantic["parameters"]["serviceSideSelectionSource"],
                "operationFaceCapacityBranch",
            )

    def test_service_side_branch_accepts_nonconvex_project02_estimate(self):
        request = json.loads(
            (ROOT / "demo" / "FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8"
            )
        )
        sequence = request["assemblySequencePolicy"]
        sequence["operationFace"]["legacySolverSide"] = "high"
        sequence["operationSideCapacity"] = {
            "confirmed": False,
            "estimateAcceptedForCoarseLayout": True,
            "estimatedSelectedSide": "front",
            "legacySolverSide": "high",
        }

        options = build_source_independent_options(request)

        for component_name in (
            "FL9A24D062A700.001-1",
            "FL9A24D062A500.001-1",
            "FL9A24D062A300.001-1",
        ):
            semantic = options.module_semantics[component_name]
            self.assertEqual(semantic["preferredSide"], "high")
            self.assertEqual(
                semantic["parameters"]["serviceSideSelectionSource"],
                "operationFaceNonConvexCapacityEstimate",
            )
            self.assertTrue(
                semantic["parameters"]["serviceSideSelectionProvisional"]
            )

    def test_locked_warm_start_is_not_expanded_by_collision_repair(self):
        request = json.loads(
            (ROOT / "demo" / "FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8"
            )
        )
        # This test covers the collision-repair lock contract, not the newly
        # introduced Project02 optical-axis calibration.  Allow the historical
        # seed's direction so it remains a valid fixture for this isolated test.
        request["moduleSemantics"]["FL9A24D062A180.001-1"]["parameters"][
            "maxOpticalAxisDeviationDegrees"
        ] = 180.0
        request["moduleSemantics"]["FL9A24D062A180.001-1"]["parameters"].update(
            {
                "minWorkingDistanceMeters": 0.0,
                "maxWorkingDistanceMeters": 10.0,
            }
        )
        seed_path = (
            ROOT
            / "demo/layout_previews/a100_a200_repair_candidates_v2/seed_03.json"
        )
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        locked = [
            "FL9A24D062A180.001-1",
            "FL9A24D062A200.001-1",
            "FL9A24D062A300.001-1",
            "FL9A24D062A500.001-1",
            "FL9A24D062A700.001-1",
        ]
        policy = request["sourceIndependentPolicy"]
        policy["warmStartReplayResultPath"] = str(seed_path)
        policy["warmStartLockedComponents"] = locked
        policy["maximumLayoutSolutions"] = 1
        # This test isolates the warm-start lock contract.  The historical seed
        # intentionally predates the CCD centerline/overhang gates and is not a
        # valid production candidate under the current project02 policy.
        policy.pop("maximumPortalGantryCenterOffsetMeters", None)
        policy.pop("maximumPortalGantryOverhangMeters", None)
        request["minimumPortalGantryOverlapRatio"] = 0.75
        request["processConstraints"] = [
            item
            for item in request["processConstraints"]
            if item.get("type") != "relativeAnchorWindow"
            and item.get("id") not in {"coarse-left-drain-reach", "coarse-right-drain-reach"}
        ]
        ccd_name = "FL9A24D062A200.001-1"
        scanner_name = "FL9A24D062A180.001-1"
        request["portalPassThrough"][ccd_name] = ["FL9A24D062A800.001-1"]
        request["moduleSemantics"][ccd_name]["parameters"][
            "portalPassModeByComponent"
        ].pop(scanner_name, None)
        request["moduleSemantics"][ccd_name]["parameters"][
            "portalChannelByComponent"
        ].pop(scanner_name, None)
        # The historical lock seed also predates the dedicated A500 service
        # zone.  Remove only that newer process gate so this test continues to
        # isolate the warm-start lock contract rather than candidate validity.
        request["moduleSemantics"]["FL9A24D062A500.001-1"]["parameters"].pop(
            "serviceRegion", None
        )
        capture_path = ROOT / request["geometryCapturePath"]
        capture = json.loads(capture_path.read_text(encoding="utf-8"))

        generated = generate_constraint_layout(
            capture,
            build_source_independent_options(request, ROOT),
        )
        selected = generated["constraintPlan"]["jointSearch"]["solutions"][0]
        placements = {
            item["componentName"]: item for item in selected["placements"]
        }
        seed_a200 = next(
            item["layout2d"]
            for item in seed["components"]
            if item["componentName"] == "FL9A24D062A200.001-1"
        )
        relative_u = (
            placements["FL9A24D062A200.001-1"]["x"]
            - placements["FL9A24D062A100.001-1"]["x"]
        )
        relative_v = (
            placements["FL9A24D062A200.001-1"]["y"]
            - placements["FL9A24D062A100.001-1"]["y"]
        )

        self.assertAlmostEqual(relative_u, seed_a200["x"])
        # The solver reports the physical footprint anchor, while this legacy
        # warm-start stores the component origin. Their fixed V offset is 2.5 mm.
        self.assertLessEqual(abs(relative_v - seed_a200["y"]), 0.0025 + 1e-9)
        self.assertEqual(
            generated["constraintPlan"]["jointSearch"]["warmStartLockedComponents"],
            sorted(locked),
        )

    def test_locked_transport_uses_its_warm_start_pose(self):
        request = json.loads(
            (ROOT / "demo" / "FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8"
            )
        )
        source_seed = json.loads(
            (
                ROOT
                / "demo/layout_previews/project02_solution.json"
            ).read_text(encoding="utf-8")
        )
        a800_name = "FL9A24D062A800.001-1"
        seed_a800 = next(
            item["layout2d"]
            for item in source_seed["components"]
            if item["componentName"] == a800_name
        )
        # Keep the known-feasible historical transport pose. The lock contract
        # does not require perturbing it into a search-space corner.

        with tempfile.TemporaryDirectory() as temporary_directory:
            seed_path = Path(temporary_directory) / "locked_transport_seed.json"
            seed_path.write_text(
                json.dumps(source_seed, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            policy = request["sourceIndependentPolicy"]
            policy["warmStartReplayResultPath"] = str(seed_path)
            policy["warmStartLockedComponents"] = [a800_name]
            policy["maximumLayoutSolutions"] = 1
            # This test isolates the lock contract. A single locked transport
            # pose can need more than the production preview's interactive budget.
            policy["jointSearchTimeLimitSeconds"] = 180
            capture = json.loads(
                (ROOT / request["geometryCapturePath"]).read_text(encoding="utf-8")
            )
            generated = generate_constraint_layout(
                capture,
                build_source_independent_options(request, ROOT),
            )

        selected = generated["constraintPlan"]["jointSearch"]["solutions"][0]
        placements = {
            item["componentName"]: item for item in selected["placements"]
        }
        a100 = placements["FL9A24D062A100.001-1"]
        a800 = placements[a800_name]
        seed_a100 = next(
            item["layout2d"]
            for item in source_seed["components"]
            if item["componentName"] == "FL9A24D062A100.001-1"
        )
        self.assertAlmostEqual(
            a800["x"] - a100["x"], seed_a800["x"] - seed_a100["x"]
        )
        self.assertLessEqual(
            abs(
                (a800["y"] - a100["y"])
                - (seed_a800["y"] - seed_a100["y"])
            ),
            0.0025 + 1e-9,
        )

    def test_locked_glue_uses_its_warm_start_pose(self):
        request = json.loads(
            (ROOT / "demo" / "FL9A24D062A000_real_process_request.json").read_text(
                encoding="utf-8"
            )
        )
        source_seed = json.loads(
            (
                ROOT
                / "demo/layout_previews/project02_v34_glue_cross_search_m050/seed_01.json"
            ).read_text(encoding="utf-8")
        )
        glue_name = "T401AA-07388-0-1"
        seed_glue = next(
            item["layout2d"]
            for item in source_seed["components"]
            if item["componentName"] == glue_name
        )
        # The v34 fixture predates the v45 CCD/glue clearance window by 2 mm.
        # Put the copied fixture inside the safe window without changing the
        # production constraint or the exact warm-start-lock assertion.
        seed_glue["y"] = float(seed_glue["y"]) - 0.01

        with tempfile.TemporaryDirectory() as temporary_directory:
            seed_path = Path(temporary_directory) / "locked_glue_seed.json"
            seed_path.write_text(
                json.dumps(source_seed, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            policy = request["sourceIndependentPolicy"]
            policy["warmStartReplayResultPath"] = str(seed_path)
            policy["warmStartLockedComponents"] = [glue_name]
            policy["maximumPortalGantryCenterOffsetMeters"] = 0.18
            policy["maximumLayoutSolutions"] = 1
            capture = json.loads(
                (ROOT / request["geometryCapturePath"]).read_text(encoding="utf-8")
            )
            generated = generate_constraint_layout(
                capture,
                build_source_independent_options(request, ROOT),
            )

        selected = generated["constraintPlan"]["jointSearch"]["solutions"][0]
        placements = {
            item["componentName"]: item for item in selected["placements"]
        }
        a100 = placements["FL9A24D062A100.001-1"]
        glue = placements[glue_name]
        self.assertAlmostEqual(glue["x"] - a100["x"], seed_glue["x"])
        self.assertLessEqual(
            abs((glue["y"] - a100["y"]) - seed_glue["y"]),
            0.0025 + 1e-9,
        )

    def test_visual_approval_materializes_selected_top_k_solution(self):
        preview = solve_case_preview(ROOT, "project02", persist=True)
        invalidated_selection = json.loads(
            (ROOT / "demo/layout_previews/project02_selected_solution.json").read_text(
                encoding="utf-8"
            )
        )
        selected_solution = preview["solutions"][0]
        expected_a300 = next(
            item for item in selected_solution["modules"] if item["code"] == "A300"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            for relative_path in (
                "demo/layout_previews/project02_solution.json",
                "demo/layout_previews/project02_preview.json",
            ):
                target = temporary_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative_path, target)
            plan = approve_case_preview(
                temporary_root,
                "project02",
                int(selected_solution["rank"]),
                reviewer_note="automated visual-gate test",
            )
            loaded_plan = load_case_verification_plan(temporary_root, "project02")
            loaded_preview = load_case_preview(temporary_root, "project02")
            selected = json.loads(
                Path(plan["selectedSolutionPath"]).read_text(encoding="utf-8")
            )
            verification_plan_exists = (
                temporary_root
                / "demo/layout_previews/project02_verification_plan.json"
            ).is_file()
        selected_a300 = next(
            item
            for item in selected["components"]
            if item["componentName"] == "FL9A24D062A300.001-1"
        )

        self.assertEqual(plan["status"], "visual_review_approved")
        self.assertEqual(
            invalidated_selection["status"], "awaiting_visual_selection"
        )
        self.assertEqual(
            invalidated_selection["solveProfile"]["name"], "calibrated"
        )
        self.assertEqual(loaded_plan, plan)
        self.assertEqual(loaded_preview["generatedAt"], preview["generatedAt"])
        self.assertTrue(verification_plan_exists)
        self.assertEqual(plan["selectedSolutionRank"], selected_solution["rank"])
        self.assertEqual(plan["stages"][0]["status"], "completed")
        self.assertEqual(plan["stages"][1]["status"], "pending")
        self.assertEqual(plan["stages"][2]["status"], "blocked")
        self.assertEqual(plan["stages"][3]["status"], "blocked")
        self.assertFalse(plan["policy"]["manualModuleMoveAfterFailure"])
        self.assertFalse(plan["policy"]["solverInvokesBrep"])
        self.assertEqual(plan["stages"][3]["maximumPairCount"], 18)
        self.assertEqual(plan["stages"][3]["allPairBaselineCount"], 36)
        self.assertEqual(plan["stages"][4]["id"], "installation_contact_review")
        self.assertEqual(plan["stages"][4]["pairCount"], 8)
        self.assertAlmostEqual(
            selected_a300["layout2d"]["x"], expected_a300["center"][0]
        )
        self.assertAlmostEqual(
            selected_a300["layout2d"]["y"], expected_a300["center"][1]
        )
        self.assertEqual(
            selected_a300["constraintPlacement"]["selectedTopKSolutionRank"],
            selected_solution["rank"],
        )
        self.assertEqual(
            selected["visualApproval"]["selectedSolutionRank"],
            selected_solution["rank"],
        )
        self.assertGreater(plan["timing"]["durationSeconds"], 0.0)
        self.assertEqual(
            selected["visualApproval"]["timing"]["runId"],
            plan["timing"]["runId"],
        )


if __name__ == "__main__":
    unittest.main()

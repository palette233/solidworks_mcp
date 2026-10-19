import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.assembly_sequence import build_assembly_sequence_plan


class AssemblySequencePlanTests(unittest.TestCase):
    def _write_graph(self, workspace: Path) -> Path:
        codes = ["A100", "A180", "A300", "A500", "A600", "A700", "A800"]
        modules = []
        for index, code in enumerate(codes):
            transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, float(index), 0.0, 0.0, 1, 0, 0, 0]
            modules.append({"ModuleToken": code, "SourceTransform": transform})
        pairs = [
            ("A600", "A100"),
            ("A600", "A180"),
            ("A600", "A300"),
            ("A600", "A500"),
            ("A600", "A700"),
            ("A600", "A800"),
        ]
        bundles = [
            {
                "FirstModuleToken": first,
                "SecondModuleToken": second,
                "MateCount": 2,
                "MateNames": ["重合", "距离"],
                "InstallationRelationAssessment": "POSITION_AND_ORIENTATION_BUNDLE_CANDIDATE",
            }
            for first, second in pairs
        ]
        path = workspace / "graph.json"
        path.write_text(
            json.dumps(
                {
                    "SourceAssemblyPath": "prototype.SLDASM",
                    "Modules": modules,
                    "MateBundles": bundles,
                }
            ),
            encoding="utf-8",
        )
        return path

    def _generated(self, *, include_a600: bool, provisional: bool) -> dict:
        names = {
            code: f"FL9A24D062{code}.001-1"
            for code in ("A100", "A180", "A300", "A500", "A600", "A700", "A800")
        }
        if not include_a600:
            names.pop("A600")
        semantics = {
            names["A100"]: {
                "moduleType": "gantry",
                "regions": {"dualValveReach": {"minU": 0, "minV": 0, "maxU": 1, "maxV": 1}},
                "parameters": {"provisional": provisional},
            },
            names["A180"]: {
                "moduleType": "scanner",
                "points": {"scanOrigin": {"u": 0, "v": 0}},
                "parameters": {
                    "maxWorkingDistanceMeters": 0.3,
                    "barcodeSide": "high",
                    "provisional": provisional,
                },
            },
            names["A800"]: {
                "moduleType": "transport",
                "points": {
                    "barcode": {"u": 0, "v": 0},
                    "workPosition1": {"u": 0, "v": 0},
                    "workPosition2": {"u": 0, "v": 0.2},
                },
                "parameters": {"provisional": provisional},
            },
            names["A300"]: {
                "moduleType": "functional",
                "points": {"leftDrainPoint": {"u": 0, "v": 0}},
                "parameters": {"provisional": provisional},
            },
            names["A500"]: {
                "moduleType": "calibration",
                "points": {"servicePoint": {"u": 0, "v": 0}},
                "parameters": {"provisional": provisional},
            },
            names["A700"]: {
                "moduleType": "cleaning",
                "points": {"servicePoint": {"u": 0, "v": 0}},
                "parameters": {"provisional": provisional},
            },
        }
        if include_a600:
            semantics[names["A600"]] = {"moduleType": "enclosure", "parameters": {}}
        return {
            "components": [{"componentName": name} for name in names.values()],
            "constraintPlan": {
                "moduleSemantics": semantics,
                "processConstraints": [{"id": "auto-scanner-los-A180"}],
            },
        }

    def test_current_project02_state_is_explicitly_not_sequence_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            graph = self._write_graph(workspace)
            request = {
                "moduleMateGraphPath": str(graph),
                "assemblySequencePolicy": {
                    "enabled": True,
                    "operationFace": {"side": "unknown", "confirmed": False},
                    "vendorTransportInterface": {"xyzMeters": None, "confirmed": False},
                    "operationSideCapacity": {"confirmed": False},
                },
            }
            plan = build_assembly_sequence_plan(
                workspace, request, self._generated(include_a600=False, provisional=True)
            )

        self.assertIsNotNone(plan)
        self.assertFalse(plan["sequentialSolverReady"])
        self.assertIn("A600整体几何接入求解器", plan["nextRequiredInputs"])
        self.assertIn("A800相对A600的厂商XYZ距离", plan["nextRequiredInputs"])
        transport = next(stage for stage in plan["stages"] if stage["id"] == "02-transport-interface")
        self.assertEqual(transport["status"], "blocked")
        self.assertEqual(transport["measured"]["prototypeWorldTranslationDeltaMeters"], [2.0, 0.0, 0.0])

    def test_confirmed_inputs_make_all_five_stages_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            graph = self._write_graph(workspace)
            request = {
                "moduleMateGraphPath": str(graph),
                "assemblySequencePolicy": {
                    "enabled": True,
                    "operationFace": {"side": "high", "confirmed": True},
                    "servicePlacementRule": {
                        "confirmed": True,
                        "preferredLocation": "nearOperationFace",
                        "fallbackLocation": "oppositeFace",
                    },
                    "vendorTransportInterface": {"xyzMeters": [0.1, 0.2, 0.3], "confirmed": True},
                    "operationSideCapacity": {
                        "availableWidthMeters": 0.8,
                        "requiredWidthMeters": 0.6,
                        "confirmed": True,
                    },
                },
            }
            plan = build_assembly_sequence_plan(
                workspace, request, self._generated(include_a600=True, provisional=False)
            )

        self.assertIsNotNone(plan)
        self.assertTrue(plan["sequentialSolverReady"])
        self.assertEqual(plan["summary"]["readyCount"], 5)
        self.assertEqual(plan["selectedServiceSide"], "high")
        self.assertEqual(plan["nextRequiredInputs"], [])

    def test_scanner_stage_reports_each_missing_capture_or_engineering_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            graph = self._write_graph(workspace)
            generated = self._generated(include_a600=True, provisional=False)
            semantics = generated["constraintPlan"]["moduleSemantics"]
            semantics["FL9A24D062A180.001-1"]["parameters"].update(
                {
                    "scanOriginMeasured": False,
                    "scanOriginCadInferred": True,
                    "workingDistanceConfirmed": False,
                    "opticalAxisConfirmed": False,
                }
            )
            semantics["FL9A24D062A800.001-1"]["parameters"]["barcodeMeasured"] = False
            request = {
                "moduleMateGraphPath": str(graph),
                "assemblySequencePolicy": {
                    "enabled": True,
                    "operationFace": {"side": "high", "confirmed": True},
                    "vendorTransportInterface": {
                        "xyzMeters": [0.1, 0.2, 0.3],
                        "confirmed": True,
                    },
                    "operationSideCapacity": {"confirmed": False},
                },
            }

            plan = build_assembly_sequence_plan(workspace, request, generated)

        stage = next(item for item in plan["stages"] if item["id"] == "03-scanner-visibility")
        self.assertEqual(stage["status"], "blocked")
        self.assertEqual(len(stage["blockedBy"]), 4)
        self.assertTrue(any("SR-X100扫描出光面" in item for item in stage["blockedBy"]))
        self.assertTrue(any("A800条码面" in item for item in stage["blockedBy"]))
        self.assertTrue(any("工作距离" in item for item in stage["blockedBy"]))
        self.assertTrue(any("光轴方向" in item for item in stage["blockedBy"]))
        self.assertTrue(any("CAD对称特征推断" in item for item in stage["blockedBy"]))

    def test_confirmed_front_operation_face_uses_a600_installation_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            graph = self._write_graph(workspace)
            frame = workspace / "a600_frame.json"
            frame.write_text(
                json.dumps(
                    {
                        "success": True,
                        "status": "PASS_A600_INSTALLATION_FRAME",
                        "moduleCode": "A600",
                        "frameName": "A600_ENGINEERING_INSTALLATION_FRAME",
                        "originWorldMeters": [0.0, 0.0, 0.0],
                        "axesWorld": {
                            "xIntoMachine": [1.0, 0.0, 0.0],
                            "yTransportLateral": [0.0, 1.0, 0.0],
                            "zUp": [0.0, 0.0, 1.0],
                        },
                    }
                ),
                encoding="utf-8",
            )
            request = {
                "moduleMateGraphPath": str(graph),
                "assemblySequencePolicy": {
                    "enabled": True,
                    "operationFace": {"side": "front", "confirmed": True},
                    "installationFrame": {
                        "confirmed": True,
                        "evidencePath": str(frame),
                    },
                    "operationSideCapacity": {"confirmed": False},
                },
            }
            plan = build_assembly_sequence_plan(
                workspace, request, self._generated(include_a600=False, provisional=True)
            )

        self.assertIsNotNone(plan)
        self.assertTrue(plan["installationFrameResolved"])
        self.assertEqual(plan["operationSide"], "front")
        self.assertEqual(plan["installationFrame"]["originWorldMeters"], [0.0, 0.0, 0.0])
        self.assertNotIn("A600安装坐标系", plan["nextRequiredInputs"])
        self.assertFalse(
            any("操作面工程侧别" in item for item in plan["nextRequiredInputs"])
        )

    def test_a600_surface_and_prototype_transport_interface_advance_first_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            graph = self._write_graph(workspace)
            frame = workspace / "a600_frame.json"
            surface = workspace / "a600_surface.json"
            interface = workspace / "a600_a800_interface.json"
            frame.write_text(
                json.dumps(
                    {
                        "success": True,
                        "moduleCode": "A600",
                        "status": "PASS_A600_INSTALLATION_FRAME",
                        "frameName": "A600_INSTALLATION_FRAME",
                        "originWorldMeters": [0.0, 0.0, 0.0],
                        "axesWorld": {},
                    }
                ),
                encoding="utf-8",
            )
            surface.write_text(
                json.dumps(
                    {
                        "success": True,
                        "usableForCoarseLayout": True,
                        "moduleCode": "A600",
                        "status": "PASS_COARSE_A600_INSTALLATION_SURFACE_WITH_CONDITIONAL_STRUCTURE",
                        "installationPlatform": {"safeBoundary": {}},
                        "transportSupportRegion": {},
                        "hardKeepoutRegions": [{}, {}],
                        "conditionalStructuralBodies": [{}],
                        "captureCoverage": {"coverageRatio": 0.997},
                        "authoritativeForFinalCollision": False,
                    }
                ),
                encoding="utf-8",
            )
            interface.write_text(
                json.dumps(
                    {
                        "success": True,
                        "usableAsPrototypeSeed": True,
                        "baseModuleCode": "A600",
                        "transportModuleCode": "A800",
                        "prototypeTranslationFrameMeters": [1.0, 2.0, 3.0],
                        "prototypeBoundingBoxCenterFrameMeters": [0.5, 0.0, 0.1],
                        "transportCenterPlaneOffsetMeters": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            request = {
                "moduleMateGraphPath": str(graph),
                "assemblySequencePolicy": {
                    "enabled": True,
                    "operationFace": {"side": "front", "confirmed": True},
                    "installationFrame": {"confirmed": True, "evidencePath": str(frame)},
                    "installationGeometry": {
                        "confirmed": True,
                        "evidencePath": str(surface),
                    },
                    "vendorTransportInterface": {
                        "xyzMeters": None,
                        "confirmed": False,
                        "prototypeEvidencePath": str(interface),
                        "prototypeSeedAcceptedForCoarseLayout": True,
                    },
                    "operationSideCapacity": {"confirmed": False},
                },
            }
            plan = build_assembly_sequence_plan(
                workspace, request, self._generated(include_a600=False, provisional=True)
            )

        enclosure = next(stage for stage in plan["stages"] if stage["id"] == "01-enclosure-frame")
        transport = next(stage for stage in plan["stages"] if stage["id"] == "02-transport-interface")
        self.assertEqual(enclosure["status"], "ready")
        self.assertTrue(plan["installationGeometryResolved"])
        self.assertEqual(plan["installationGeometry"]["hardKeepoutRegionCount"], 2)
        self.assertNotIn("A600整体几何接入求解器", plan["nextRequiredInputs"])
        self.assertTrue(plan["prototypeTransportInterfaceResolved"])
        self.assertEqual(transport["status"], "blocked")
        self.assertEqual(transport["measured"]["prototypeTranslationFrameMeters"], [1.0, 2.0, 3.0])
        self.assertIn("A800相对A600的厂商XYZ距离", plan["nextRequiredInputs"])

    def test_mate_interface_resolves_yz_but_keeps_longitudinal_x_blocker(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            graph = self._write_graph(workspace)
            interface = workspace / "a600_a800_mate_interface.json"
            interface.write_text(
                json.dumps(
                    {
                        "success": True,
                        "usableAsMateDerivedCoarseInterface": True,
                        "baseModuleCode": "A600",
                        "transportModuleCode": "A800",
                        "status": "PASS_MATE_DERIVED_PARTIAL_INTERFACE",
                        "mateDerivedInstallationDatumFrameMeters": [0.3763, 0.0, 0.0],
                        "constraintInterpretation": {
                            "fixedTranslationAxes": ["Y", "Z"],
                            "freeTranslationAxes": ["X"],
                            "orientationFullyConstrained": True,
                        },
                        "axisConfidence": {
                            "xIntoMachine": "medium-prototype-feature-station-not-mate-constrained",
                            "yTransportLateral": "high-width9-mate-constrained",
                            "zUp": "high-coincident35-mate-constrained",
                        },
                        "confirmedAsVendorInterface": False,
                        "remainingRequiredConfirmation": "Confirm X.",
                    }
                ),
                encoding="utf-8",
            )
            request = {
                "moduleMateGraphPath": str(graph),
                "assemblySequencePolicy": {
                    "enabled": True,
                    "operationFace": {"side": "unknown", "confirmed": False},
                    "vendorTransportInterface": {
                        "xyzMeters": None,
                        "confirmed": False,
                        "mateDerivedEvidencePath": str(interface),
                        "mateDerivedSeedAcceptedForCoarseLayout": True,
                    },
                    "operationSideCapacity": {"confirmed": False},
                },
            }
            plan = build_assembly_sequence_plan(
                workspace, request, self._generated(include_a600=False, provisional=True)
            )

        transport = next(stage for stage in plan["stages"] if stage["id"] == "02-transport-interface")
        self.assertTrue(plan["mateDerivedTransportInterfaceResolved"])
        self.assertEqual(transport["status"], "blocked")
        self.assertTrue(
            next(
                item["available"]
                for item in transport["evidence"]
                if "配合面已恢复Y/Z" in item["label"]
            )
        )
        self.assertEqual(
            transport["measured"]["mateDerivedInstallationDatumFrameMeters"],
            [0.3763, 0.0, 0.0],
        )
        self.assertEqual(
            transport["measured"]["mateConstraintInterpretation"]["freeTranslationAxes"],
            ["X"],
        )
        self.assertIn(
            "A800沿传输长轴X的厂商定位尺寸或端面/销孔基准确认",
            plan["nextRequiredInputs"],
        )
        self.assertNotIn("A800相对A600的厂商XYZ距离", plan["nextRequiredInputs"])


if __name__ == "__main__":
    unittest.main()

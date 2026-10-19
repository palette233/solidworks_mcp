from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from demo_backend.face_mappings import FaceMappingStore
from demo_backend.models import (
    CaptureProjectLayoutRequest,
    DemoComponent,
    DemoState,
    GenerateConstraintLayoutRequest,
    OperationResult,
)
from demo_backend.services.demo_service import DemoService
from demo_backend.state_store import DemoStateStore


class CapturingMcpClient:
    mode = "bridge"

    def __init__(self) -> None:
        self.last_plan = []

    async def run_plan(self, plan):
        self.last_plan = plan
        output_path = Path(plan[0].arguments["outputPath"])
        payload = {
            "success": True,
            "message": "Capture completed.",
            "outputPath": str(output_path),
            "baseComponentName": "Component-1",
            "components": [
                {
                    "componentName": "Component-1",
                    "filePath": "Component-1.SLDASM",
                    "bottomFaceName": "底面",
                    "layout2d": {
                        "x": 0.0,
                        "y": 0.0,
                        "thetaDegrees": 0.0,
                        "thetaAxis": "z",
                    },
                }
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return OperationResult(
            status="ok",
            message="MCP execution completed.",
            plan=plan,
            toolResults=[{"text": [json.dumps(payload, ensure_ascii=False)]}],
        )


class MissingOutputMcpClient(CapturingMcpClient):
    async def run_plan(self, plan):
        self.last_plan = plan
        payload = {
            "success": True,
            "message": "Capture completed without writing the requested file.",
            "outputPath": plan[0].arguments["outputPath"],
            "components": [],
        }
        return OperationResult(
            status="ok",
            message="MCP execution completed.",
            plan=plan,
            toolResults=[{"text": [json.dumps(payload)]}],
        )


class ConstraintGeometryMcpClient(CapturingMcpClient):
    async def run_plan(self, plan):
        self.last_plan = plan
        output_path = Path(plan[0].arguments["outputPath"])
        payload = {
            "success": True,
            "message": "Constraint geometry captured.",
            "baseComponentName": "gantry",
            "baseFrame": {
                "origin": [0.0, 0.0, 0.0],
                "uAxis": [1.0, 0.0, 0.0],
                "vAxis": [0.0, 0.0, 1.0],
                "normal": [0.0, 1.0, 0.0],
            },
            "components": [
                {
                    "componentName": "gantry",
                    "filePath": "gantry.SLDASM",
                    "bottomFaceName": "底面",
                    "boundingBoxWorld": [-5.0, 0.0, -3.0, 5.0, 1.0, 3.0],
                    "layout2d": {"x": 0.0, "y": 0.0, "thetaDegrees": 0.0, "thetaAxis": "x"},
                },
                {
                    "componentName": "transport",
                    "filePath": "transport.SLDASM",
                    "bottomFaceName": "底面",
                    "boundingBoxWorld": [-5.2, 0.0, -0.45, 5.2, 0.5, 0.45],
                    "layout2d": {"x": 0.0, "y": 0.0, "thetaDegrees": 0.0, "thetaAxis": "x"},
                },
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return OperationResult(
            status="ok",
            message="MCP execution completed.",
            plan=plan,
            toolResults=[{"text": [json.dumps(payload, ensure_ascii=False)]}],
        )


class DemoServicePathTests(unittest.IsolatedAsyncioTestCase):
    def _create_service(self, workspace: Path, mcp, component_names=("Component-1",)) -> DemoService:
        state_path = workspace / "demo" / "state.json"
        asset_dir = workspace / "assets"
        mapping_path = workspace / "artifacts" / "face_mappings.json"
        store = DemoStateStore(state_path, asset_dir)
        store.save(
            DemoState(
                components=[
                    DemoComponent(
                        id=component_name.lower(),
                        displayName=component_name,
                        componentName=component_name,
                        filePath=str(asset_dir / f"{component_name}.SLDASM"),
                        bottomFaceName="底面",
                    )
                    for component_name in component_names
                ]
            )
        )
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_path.write_text(
            json.dumps(
                {component_name: {"底面": {}} for component_name in component_names},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return DemoService(
            store=store,
            face_mappings=FaceMappingStore(mapping_path),
            llm=object(),
            mcp=mcp,
            target_assembly_path=workspace / "demo" / "target.SLDASM",
        )

    async def test_relative_capture_paths_are_resolved_against_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir).resolve()
            mcp = CapturingMcpClient()
            with patch.object(DemoService, "_workspace", return_value=workspace):
                service = self._create_service(workspace, mcp)
                result = await service.capture_project_layout(
                    CaptureProjectLayoutRequest(
                        sourceAssemblyPath=str(workspace / "source.SLDASM"),
                        outputPath="demo/layout.json",
                        projectConfigPath="demo/project.json",
                    )
                )

            expected_layout = (workspace / "demo" / "layout.json").resolve()
            expected_config = (workspace / "demo" / "project.json").resolve()
            self.assertEqual(result.status, "ok")
            self.assertEqual(
                Path(mcp.last_plan[0].arguments["outputPath"]),
                expected_layout,
            )
            self.assertTrue(expected_layout.is_file())
            self.assertTrue(expected_config.is_file())

            project = json.loads(expected_config.read_text(encoding="utf-8"))
            self.assertEqual(Path(project["layoutJsonPath"]), expected_layout)

    async def test_success_without_expected_output_file_is_reported_as_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir).resolve()
            mcp = MissingOutputMcpClient()
            with patch.object(DemoService, "_workspace", return_value=workspace):
                service = self._create_service(workspace, mcp)
                result = await service.capture_project_layout(
                    CaptureProjectLayoutRequest(
                        sourceAssemblyPath=str(workspace / "source.SLDASM"),
                        outputPath="demo/missing-layout.json",
                        projectConfigPath="demo/project.json",
                    )
                )

            self.assertEqual(result.status, "error")
            self.assertIn("expected output file was not created", result.message)
            self.assertFalse((workspace / "demo" / "project.json").exists())
            self.assertIsNone(result.state.layout_json_path)

    def test_replay_plan_skips_portal_interference_validation_by_default(self):
        state = DemoState(
            assemblyPath=r"D:\demo\target.SLDASM",
            layoutJsonPath=r"D:\demo\layout.json",
            components=[],
        )

        plan = DemoService._apply_captured_layout_plan(state)

        self.assertEqual(len(plan), 1)
        self.assertFalse(plan[0].arguments["validatePortalInterference"])

    async def test_constraint_service_writes_semantic_validation_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir).resolve()
            mcp = ConstraintGeometryMcpClient()
            with patch.object(DemoService, "_workspace", return_value=workspace):
                service = self._create_service(workspace, mcp, ("gantry", "transport"))
                result = await service.generate_constraint_layout(
                    GenerateConstraintLayoutRequest(
                        outputPath="demo/semantic-layout.json",
                        geometryCapturePath="demo/semantic-geometry.json",
                        moduleSemantics={
                            "gantry": {
                                "moduleType": "gantry",
                                "regions": {
                                    "dualValveReach": {
                                        "minU": -4.9,
                                        "minV": -2.9,
                                        "maxU": 4.9,
                                        "maxV": 2.9,
                                    }
                                },
                            },
                            "transport": {
                                "moduleType": "transport",
                                "points": {"workPosition1": {"u": 0.0, "v": 0.0}},
                            },
                            "PROVISIONAL_WEIGHING_PLACEHOLDER-1": {
                                "moduleType": "weighing",
                                "points": {"servicePoint": {"u": 0.0, "v": 0.0}},
                            },
                        },
                        provisionalComponents=[
                            {
                                "componentName": "PROVISIONAL_WEIGHING_PLACEHOLDER-1",
                                "widthMeters": 0.22,
                                "depthMeters": 0.22,
                                "heightMeters": 0.20,
                                "anchorU": 0.0,
                                "anchorV": -2.0,
                                "reason": "No verified WKC204C CAD.",
                                "replayable": False,
                            }
                        ],
                        syncLayout=False,
                    )
                )

            self.assertEqual(result.status, "ok")
            self.assertTrue((workspace / "demo" / "semantic-layout.json").is_file())
            self.assertTrue(result.constraint_layout["processValidation"]["hardFeasible"])
            self.assertEqual(result.constraint_layout["processValidation"]["constraintCount"], 2)
            self.assertEqual(result.constraint_layout["provisionalPlaceholderCount"], 1)
            self.assertTrue(result.constraint_layout["assumptionWarnings"])
            self.assertFalse(result.constraint_layout["validation"]["productionReady"])


if __name__ == "__main__":
    unittest.main()

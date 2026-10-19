from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.semantic_port_workbench import (
    DEFAULT_CLOSURE_SUMMARY,
    SemanticPortWorkbenchError,
    load_semantic_port_workbench,
    prepare_semantic_connection_application,
    preview_semantic_connection,
)


class SemanticPortWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        endpoints = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "Endpoints": [
                {
                    "EndpointId": "face:a500:one",
                    "GeometryClass": "Plane",
                    "RecoveryConfidence": "TEST",
                    "Endpoint": {
                        "ModuleToken": "A500",
                        "ModuleHierarchyPath": "A500-1",
                        "RelativeLeafHierarchyPath": "A500-leaf",
                        "GeometryType": "Face",
                        "BodyIndex": 0,
                        "FaceIndexInBody": 1,
                        "FaceArea": 0.01,
                        "FaceCenterLocal": [0, 0, 0],
                        "FaceNormalLocal": [0, 0, 1],
                    },
                },
                {
                    "EndpointId": "face:a700:two",
                    "GeometryClass": "Plane",
                    "RecoveryConfidence": "TEST",
                    "Endpoint": {
                        "ModuleToken": "A700",
                        "ModuleHierarchyPath": "A700-1",
                        "RelativeLeafHierarchyPath": "A700-leaf",
                        "GeometryType": "Face",
                        "BodyIndex": 0,
                        "FaceIndexInBody": 2,
                        "FaceArea": 0.02,
                        "FaceCenterLocal": [0, 0, 0.05],
                        "FaceNormalLocal": [0, 0, -1],
                    },
                },
            ],
        }
        semantic = {
            "schemaVersion": "semantic-port-catalog/v1",
            "projectId": "project02",
            "ports": [
                {
                    "portId": "A500.reference",
                    "displayName": "A500原型间距基准",
                    "moduleToken": "A500",
                    "moduleHierarchyPath": "A500-1",
                    "category": "mechanical",
                    "interfaceType": "planar_spacing_reference",
                    "status": "confirmed",
                    "endpointBindings": [{"role": "primary", "endpointId": "face:a500:one"}],
                },
                {
                    "portId": "A700.reference",
                    "displayName": "A700原型间距基准",
                    "moduleToken": "A700",
                    "moduleHierarchyPath": "A700-1",
                    "category": "mechanical",
                    "interfaceType": "planar_spacing_reference",
                    "status": "provisional",
                    "endpointBindings": [{"role": "primary", "endpointId": "face:a700:two"}],
                },
            ],
            "connectionTemplates": [
                {
                    "templateId": "distance",
                    "interfaceTypeA": "planar_spacing_reference",
                    "interfaceTypeB": "planar_spacing_reference",
                    "constraintEffect": {
                        "estimatedRemovedScalarDof": 1,
                        "fullyLocatesAddedComponent": False,
                        "assessment": "DEMO_PARTIAL_RELATION_ONLY",
                    },
                    "mateSteps": [
                        {
                            "mateName": "距离8",
                            "mateType": 5,
                            "alignment": 1,
                            "endpointRoleA": "primary",
                            "endpointRoleB": "primary",
                            "distanceMeters": 0.05,
                        }
                    ],
                }
            ],
        }
        source = {
            "SchemaVersion": "solidworks-module-mate-graph/v1.3",
            "SourceAssemblyPath": "D:/prototype.SLDASM",
            "Modules": [
                {
                    "ModuleToken": "A700",
                    "Name": "A700-1",
                    "Path": "D:/A700.SLDASM",
                    "HierarchyPath": "A700-1",
                }
            ],
            "Mates": [],
        }
        request = {
            "schemaVersion": "semantic-connection-request/v1",
            "connectionId": "add-A500",
            "portAId": "A500.reference",
            "portBId": "A700.reference",
            "templateId": "distance",
            "baseModuleToken": "A700",
            "componentToAdd": {
                "ModuleToken": "A500",
                "Name": "A500-1",
                "Path": "D:/A500.SLDASM",
                "HierarchyPath": "A500-1",
            },
            "parameters": {"distanceMeters": 0.05},
        }
        for name, value in {
            "endpoints.json": endpoints,
            "semantic.json": semantic,
            "source.json": source,
            "request.json": request,
        }.items():
            (self.workspace / name).write_text(json.dumps(value), encoding="utf-8")
        self.request = request

    def tearDown(self) -> None:
        self.temp.cleanup()

    def payload(self) -> dict:
        return {
            "semanticCatalogPath": "semantic.json",
            "endpointCatalogPath": "endpoints.json",
            "sourceGraphPath": "source.json",
            "connectionRequest": self.request,
        }

    def test_loads_ports_with_face_registry_bindings(self) -> None:
        result = load_semantic_port_workbench(
            self.workspace,
            "semantic.json",
            "endpoints.json",
            "source.json",
            "request.json",
        )
        self.assertEqual(len(result["ports"]), 2)
        self.assertEqual(result["ports"][0]["endpointBindings"][0]["faceIndex"], 1)
        self.assertEqual(result["demoRequest"], self.request)
        self.assertIsNone(result["latestClosurePath"])
        self.assertIsNone(result["latestClosure"])

    def test_loads_latest_release_closure_when_available(self) -> None:
        closure_path = self.workspace / DEFAULT_CLOSURE_SUMMARY
        closure_path.parent.mkdir(parents=True, exist_ok=True)
        closure = {
            "schemaVersion": "semantic-context-incremental-release-closure/v1",
            "success": True,
            "status": "RELEASE_ALLOWED",
            "cacheReused": True,
            "instancesByModuleToken": {"A500": "A500-2"},
            "releaseGate": {
                "releaseAllowed": True,
                "status": "RELEASE_ALLOWED",
                "interferenceSummary": {
                    "completedExactPairCount": 3,
                    "newInterferenceCount": 0,
                },
            },
            "timing": {"durationSeconds": 0.1},
        }
        closure_path.write_text(json.dumps(closure), encoding="utf-8")

        result = load_semantic_port_workbench(
            self.workspace,
            "semantic.json",
            "endpoints.json",
            "source.json",
            "request.json",
        )

        self.assertEqual(result["latestClosurePath"], str(closure_path.resolve()))
        self.assertEqual(result["latestClosure"], closure)

    def test_preview_is_read_only_and_reports_partial_constraint(self) -> None:
        before = sorted(path.name for path in self.workspace.iterdir())
        result = preview_semantic_connection(self.workspace, self.payload())
        self.assertEqual(result["effectiveSummary"]["effectiveModuleCount"], 2)
        self.assertEqual(result["effectiveSummary"]["generatedMateCount"], 1)
        self.assertFalse(result["executionBoundary"]["modifiesPrototype"])
        self.assertEqual(result["executionBoundary"]["mode"], "context_incremental")
        self.assertTrue(result["executionBoundary"]["preservesExistingParentContext"])
        self.assertFalse(result["executionBoundary"]["fullyLocatesAddedComponent"])
        self.assertEqual(len(result["previewDigest"]), 64)
        self.assertEqual(before, sorted(path.name for path in self.workspace.iterdir()))

    def test_apply_requires_confirmation_and_current_digest(self) -> None:
        payload = self.payload()
        preview = preview_semantic_connection(self.workspace, payload)
        payload.update(
            {
                "previewDigest": preview["previewDigest"],
                "outputAssemblyPath": "demo/semantic_ports/ui_runs/result.SLDASM",
                "confirmed": False,
            }
        )
        with self.assertRaisesRegex(SemanticPortWorkbenchError, "Explicit confirmation"):
            prepare_semantic_connection_application(self.workspace, payload)
        payload["confirmed"] = True
        payload["previewDigest"] = "0" * 64
        with self.assertRaisesRegex(SemanticPortWorkbenchError, "stale"):
            prepare_semantic_connection_application(self.workspace, payload)

    def test_apply_writes_audit_inputs_only_inside_ui_runs(self) -> None:
        payload = self.payload()
        preview = preview_semantic_connection(self.workspace, payload)
        payload.update(
            {
                "previewDigest": preview["previewDigest"],
                "outputAssemblyPath": "demo/semantic_ports/ui_runs/result.SLDASM",
                "confirmed": True,
            }
        )
        prepared = prepare_semantic_connection_application(self.workspace, payload)
        self.assertTrue(Path(prepared["requestPath"]).is_file())
        self.assertTrue(Path(prepared["patchPath"]).is_file())
        self.assertTrue(Path(prepared["effectiveGraphPath"]).is_file())
        self.assertFalse(Path(prepared["outputAssemblyPath"]).exists())
        self.assertEqual(prepared["executionMode"], "context_incremental")
        self.assertEqual(prepared["sourceAssemblyPath"], "D:/prototype.SLDASM")
        self.assertEqual(prepared["targetModuleToken"], "A500")

    def test_blank_rebuild_remains_explicitly_selectable(self) -> None:
        payload = self.payload()
        payload["executionMode"] = "blank_rebuild"
        preview = preview_semantic_connection(self.workspace, payload)
        self.assertEqual(preview["executionBoundary"]["mode"], "blank_rebuild")
        self.assertFalse(preview["executionBoundary"]["preservesExistingParentContext"])

    def test_apply_rejects_output_outside_isolated_run_directory(self) -> None:
        payload = self.payload()
        preview = preview_semantic_connection(self.workspace, payload)
        payload.update(
            {
                "previewDigest": preview["previewDigest"],
                "outputAssemblyPath": "unsafe.SLDASM",
                "confirmed": True,
            }
        )
        with self.assertRaisesRegex(SemanticPortWorkbenchError, "ui_runs"):
            prepare_semantic_connection_application(self.workspace, payload)


if __name__ == "__main__":
    unittest.main()

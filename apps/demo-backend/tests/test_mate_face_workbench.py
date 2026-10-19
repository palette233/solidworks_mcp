from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.mate_face_workbench import (
    MateFaceWorkbenchError,
    build_face_mate_patch_preview,
    finalize_face_mate_patch_application,
    load_face_endpoint_workbench,
    prepare_face_mate_patch_application,
)


def endpoint(endpoint_id: str, token: str, hierarchy: str, face_index: int) -> dict:
    return {
        "EndpointId": endpoint_id,
        "ModulePath": f"D:/{token}.SLDASM",
        "ModuleReferencedConfiguration": "Default",
        "LeafReferencedConfiguration": "Default",
        "GeometryClass": "Plane",
        "RecoveryConfidence": "TEST",
        "Endpoint": {
            "Index": face_index,
            "ModuleToken": token,
            "ModuleHierarchyPath": hierarchy,
            "LeafHierarchyPath": f"{hierarchy}/{token}-Leaf-1",
            "RelativeLeafHierarchyPath": f"{token}-Leaf-1",
            "LeafComponentName": f"{token}-Leaf-1",
            "LeafComponentPath": f"D:/{token}.SLDPRT",
            "GeometryType": "Face",
            "BodyIndex": 0,
            "FaceIndexInBody": face_index,
            "FaceArea": 0.01,
            "FaceCenterLocal": [0, 0, face_index],
            "FaceCenterWorld": [1, 2, face_index],
            "FaceNormalLocal": [0, 0, 1],
            "FaceNormalWorld": [0, 0, 1],
            "SourceAssemblyPersistentReferenceBase64": "secret-large-value",
        },
    }


class MateFaceWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        catalog_path = self.workspace / "catalog.json"
        catalog_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
                    "SourceAssemblyPath": "D:/source.SLDASM",
                    "CatalogMode": "seed_plus_leaf_scans",
                    "Endpoints": [
                        endpoint("face:a500:one", "A500", "A500-1", 1),
                        endpoint("face:a700:two", "A700", "A700-1", 2),
                    ],
                }
            ),
            encoding="utf-8",
        )
        source_graph_path = self.workspace / "source.json"
        source_graph_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "solidworks-module-mate-graph/v1.3",
                    "SourceAssemblyPath": "D:/source.SLDASM",
                    "Modules": [
                        {"ModuleToken": "A500", "HierarchyPath": "A500-1", "Path": "D:/A500.SLDASM"},
                        {"ModuleToken": "A700", "HierarchyPath": "A700-1", "Path": "D:/A700.SLDASM"},
                    ],
                    "Mates": [],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_catalog_view_omits_persistent_reference(self) -> None:
        result = load_face_endpoint_workbench(self.workspace, "catalog.json")
        self.assertEqual(result["endpointCount"], 2)
        self.assertEqual(result["modules"], ["A500", "A700"])
        self.assertNotIn("SourceAssemblyPersistentReferenceBase64", result["endpoints"][0])

    def test_patch_preview_compiles_without_writing_files(self) -> None:
        before = sorted(path.name for path in self.workspace.iterdir())
        result = build_face_mate_patch_preview(
            self.workspace,
            {
                "catalogPath": "catalog.json",
                "sourceGraphPath": "source.json",
                "faceAEndpointId": "face:a500:one",
                "faceBEndpointId": "face:a700:two",
                "mateType": 3,
                "mateName": "界面平行1",
            },
        )
        self.assertTrue(result["compatible"])
        self.assertEqual(result["effectiveSummary"]["mateCount"], 1)
        self.assertEqual(result["patch"]["operations"][0]["endpointIds"], ["face:a500:one", "face:a700:two"])
        self.assertEqual(len(result["previewDigest"]), 64)
        self.assertEqual(before, sorted(path.name for path in self.workspace.iterdir()))

    def test_patch_preview_rejects_same_module(self) -> None:
        catalog = json.loads((self.workspace / "catalog.json").read_text(encoding="utf-8"))
        catalog["Endpoints"][1]["Endpoint"]["ModuleHierarchyPath"] = "A500-1"
        (self.workspace / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
        with self.assertRaisesRegex(MateFaceWorkbenchError, "two different modules"):
            build_face_mate_patch_preview(
                self.workspace,
                {
                    "catalogPath": "catalog.json",
                    "sourceGraphPath": "source.json",
                    "faceAEndpointId": "face:a500:one",
                    "faceBEndpointId": "face:a700:two",
                    "mateType": 3,
                },
            )

    def application_payload(self) -> dict:
        preview = build_face_mate_patch_preview(
            self.workspace,
            {
                "catalogPath": "catalog.json",
                "sourceGraphPath": "source.json",
                "faceAEndpointId": "face:a500:one",
                "faceBEndpointId": "face:a700:two",
                "mateType": 3,
                "mateName": "界面平行1",
            },
        )
        return {
            "catalogPath": "catalog.json",
            "sourceGraphPath": "source.json",
            "faceAEndpointId": "face:a500:one",
            "faceBEndpointId": "face:a700:two",
            "mateType": 3,
            "mateName": "界面平行1",
            "previewDigest": preview["previewDigest"],
            "outputAssemblyPath": "demo/mate_graph_edit/ui_runs/test_rebuild.SLDASM",
            "confirmed": True,
        }

    def test_application_requires_explicit_confirmation(self) -> None:
        payload = self.application_payload()
        payload["confirmed"] = False
        with self.assertRaisesRegex(MateFaceWorkbenchError, "Explicit confirmation"):
            prepare_face_mate_patch_application(self.workspace, payload)

    def test_application_rejects_stale_preview_digest(self) -> None:
        payload = self.application_payload()
        payload["previewDigest"] = "0" * 64
        with self.assertRaisesRegex(MateFaceWorkbenchError, "stale"):
            prepare_face_mate_patch_application(self.workspace, payload)

    def test_application_materializes_audit_files_and_never_overwrites(self) -> None:
        payload = self.application_payload()
        prepared = prepare_face_mate_patch_application(self.workspace, payload)
        self.assertTrue(Path(prepared["patchPath"]).is_file())
        self.assertTrue(Path(prepared["effectiveGraphPath"]).is_file())
        self.assertFalse(Path(prepared["outputAssemblyPath"]).exists())
        with self.assertRaisesRegex(MateFaceWorkbenchError, "Refusing to overwrite"):
            prepare_face_mate_patch_application(self.workspace, payload)

    def test_finalize_requires_real_output_and_records_reopen_summary(self) -> None:
        prepared = prepare_face_mate_patch_application(self.workspace, self.application_payload())
        Path(prepared["outputAssemblyPath"]).write_bytes(b"SLDASM-test")
        operation = {
            "status": "ok",
            "message": "MCP execution completed.",
            "plan": [],
            "toolResults": [
                {
                    "text": [
                        json.dumps(
                            {
                                "Success": True,
                                "RequestedActiveMateCount": 1,
                                "CreatedMateCount": 1,
                                "ReopenedMateCount": 1,
                                "ReopenedMateParametersMatch": True,
                                "MateCreationErrorsClear": True,
                                "ReopenedComponentsNotOverConstrained": True,
                                "ReopenedComponentSemanticsMatch": True,
                            }
                        )
                    ]
                }
            ],
        }
        result = finalize_face_mate_patch_application(prepared, operation)
        self.assertTrue(result["success"])
        self.assertEqual(result["rebuildSummary"]["reopenedMateCount"], 1)
        self.assertTrue(result["rebuildSummary"]["mateCreationErrorsClear"])
        self.assertTrue(result["rebuildSummary"]["componentsNotOverConstrained"])
        self.assertTrue(result["rebuildSummary"]["componentSemanticsMatch"])
        self.assertTrue(Path(prepared["resultPath"]).is_file())


if __name__ == "__main__":
    unittest.main()

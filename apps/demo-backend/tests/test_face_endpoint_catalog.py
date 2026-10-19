from __future__ import annotations

import unittest

from demo_backend.face_endpoint_catalog import (
    append_face_endpoint,
    build_face_endpoint_catalog_from_source_mates,
    FaceEndpointCatalogError,
    list_face_candidates,
    match_exported_face_endpoint,
    merge_face_endpoint_catalogs,
    select_face_endpoint,
    validate_mate_endpoint_pair,
)


def entry(endpoint_id: str, token: str, path: str, face: int, area: float) -> dict:
    return {
        "EndpointId": endpoint_id,
        "GeometryClass": "Plane",
        "Endpoint": {
            "ModuleToken": token,
            "ModuleHierarchyPath": path,
            "RelativeLeafHierarchyPath": f"{token}-leaf",
            "BodyIndex": 0,
            "FaceIndexInBody": face,
            "FaceArea": area,
            "GeometryType": "Face",
        },
    }


class FaceEndpointCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "Endpoints": [
                entry("face:a500:one", "A500", "A500-1", 11, 0.001602),
                entry("face:a700:two", "A700", "A700-1", 2, 0.00108),
            ],
        }

    def test_selects_unique_endpoint_id(self) -> None:
        self.assertEqual(select_face_endpoint(self.catalog, "face:a500:one")["Endpoint"]["ModuleToken"], "A500")

    def test_filters_candidates_by_module_and_area(self) -> None:
        candidates = list_face_candidates(self.catalog, module_token="A700", minimum_area=0.001)
        self.assertEqual([item["EndpointId"] for item in candidates], ["face:a700:two"])

    def test_validates_two_module_planar_pair(self) -> None:
        pair = validate_mate_endpoint_pair(self.catalog, ["face:a500:one", "face:a700:two"], 5)
        self.assertEqual(len(pair), 2)

    def test_rejects_same_module_pair(self) -> None:
        self.catalog["Endpoints"][1]["Endpoint"]["ModuleHierarchyPath"] = "A500-1"
        with self.assertRaisesRegex(FaceEndpointCatalogError, "two different modules"):
            validate_mate_endpoint_pair(self.catalog, ["face:a500:one", "face:a700:two"], 5)

    def test_matches_exported_endpoint(self) -> None:
        exported = dict(self.catalog["Endpoints"][0]["Endpoint"])
        self.assertEqual(match_exported_face_endpoint(self.catalog, exported)["EndpointId"], "face:a500:one")

    def test_append_selected_endpoint_is_immutable(self) -> None:
        selected = entry("face:a500:selected", "A500", "A500-1", 12, 0.002)
        result = append_face_endpoint(self.catalog, selected)
        self.assertEqual(len(self.catalog["Endpoints"]), 2)
        self.assertEqual(result["EndpointCount"], 3)
        self.assertEqual(result["CatalogMode"], "seed_plus_selected_faces")

    def test_merge_leaf_catalog_is_immutable_and_deduplicates(self) -> None:
        self.catalog["SourceAssemblyPath"] = r"D:\source.SLDASM"
        extension = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "SourceAssemblyPath": r"d:\SOURCE.SLDASM",
            "CatalogMode": "leaf_scoped",
            "RequestedLeafSelectors": ["Leaf-9"],
            "Endpoints": [
                {
                    **self.catalog["Endpoints"][1],
                    "RecoveryConfidence": "LEAF_SCOPED_FINGERPRINT",
                    "Endpoint": {
                        **self.catalog["Endpoints"][1]["Endpoint"],
                        "FaceCenterWorld": [1.0, 2.0, 3.0],
                    },
                },
                entry("face:a700:new", "A700", "A700-1", 9, 0.02),
            ],
        }

        result = merge_face_endpoint_catalogs(self.catalog, extension)

        self.assertEqual(len(self.catalog["Endpoints"]), 2)
        self.assertEqual(result["EndpointCount"], 3)
        self.assertEqual(result["MergedLeafSelectors"], ["Leaf-9"])
        self.assertEqual(result["LastMerge"]["addedEndpointIds"], ["face:a700:new"])
        self.assertEqual(result["LastMerge"]["duplicateEndpointIds"], ["face:a700:two"])
        self.assertEqual(
            result["LastMerge"]["duplicateRecoveryEvidence"]["face:a700:two"],
            ["", "LEAF_SCOPED_FINGERPRINT"],
        )

    def test_merge_rejects_different_source_assemblies(self) -> None:
        self.catalog["SourceAssemblyPath"] = r"D:\first.SLDASM"
        extension = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "SourceAssemblyPath": r"D:\second.SLDASM",
            "Endpoints": [],
        }
        with self.assertRaisesRegex(FaceEndpointCatalogError, "same source assembly"):
            merge_face_endpoint_catalogs(self.catalog, extension)

    def test_builds_bounded_catalog_and_reuses_persistent_endpoint_id(self) -> None:
        self.catalog["Endpoints"][0]["Endpoint"][
            "SourceAssemblyPersistentReferenceBase64"
        ] = "persistent-a500"
        source = {
            "SourceAssemblyPath": r"D:\source.SLDASM",
            "Modules": [
                {
                    "ModuleToken": "A500",
                    "HierarchyPath": "A500-1",
                    "Path": r"D:\A500.SLDASM",
                    "ReferencedConfiguration": "Default",
                },
                {
                    "ModuleToken": "A600",
                    "HierarchyPath": "A600-1",
                    "Path": r"D:\A600.SLDASM",
                    "ReferencedConfiguration": "Default",
                },
            ],
            "Mates": [
                {
                    "MateName": "install",
                    "Endpoints": [
                        {
                            **self.catalog["Endpoints"][0]["Endpoint"],
                            "FaceCenterLocal": [0, 0, 0],
                            "FaceNormalLocal": [0, 0, 1],
                        },
                        {
                            "ModuleToken": "A600",
                            "ModuleHierarchyPath": "A600-1",
                            "RelativeLeafHierarchyPath": "A600-leaf",
                            "LeafComponentPath": r"D:\part.SLDPRT",
                            "GeometryType": "Face",
                            "BodyIndex": 1,
                            "FaceIndexInBody": 4,
                            "FaceArea": 0.02,
                            "FaceCenterLocal": [1, 2, 3],
                            "FaceNormalLocal": [0, 1, 0],
                            "SourceAssemblyPersistentReferenceBase64": "persistent-a600",
                        },
                    ],
                }
            ],
        }
        result = build_face_endpoint_catalog_from_source_mates(
            source, ["install"], self.catalog
        )
        self.assertEqual(result["EndpointCount"], 2)
        self.assertIn(
            "face:a500:one",
            result["SourceMateEndpointAudit"]["reusedEndpointIds"],
        )
        generated = result["SourceMateEndpointAudit"]["generatedEndpointIds"]
        self.assertEqual(len(generated), 1)
        self.assertTrue(generated[0].startswith("face:a600:"))


if __name__ == "__main__":
    unittest.main()

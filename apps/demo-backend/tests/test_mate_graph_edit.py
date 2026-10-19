from __future__ import annotations

import copy
import unittest

from demo_backend.mate_graph_edit import MateGraphEditError, compile_mate_graph_patch


def endpoint(module: str, face: int) -> dict:
    return {
        "Index": face,
        "ModuleHierarchyPath": module,
        "RelativeLeafHierarchyPath": f"leaf-{module}",
        "GeometryType": "Face",
        "BodyIndex": 0,
        "FaceIndexInBody": face,
    }


class MateGraphEditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = {
            "SchemaVersion": "assembly-module-mate-graph/v2",
            "Modules": [
                {"ModuleToken": "A500", "HierarchyPath": "A500-1", "Path": "A500.SLDASM"},
                {"ModuleToken": "A700", "HierarchyPath": "A700-1", "Path": "A700.SLDASM"},
                {"ModuleToken": "A600", "HierarchyPath": "A600-1", "Path": "A600.SLDASM"},
            ],
            "Mates": [
                {
                    "MateName": "距离8",
                    "MateType": 5,
                    "MateTypeName": "swMateDISTANCE",
                    "Alignment": 1,
                    "AlignmentName": "swMateAlignANTI_ALIGNED",
                    "Distance": 0.05,
                    "Angle": None,
                    "IsSuppressed": False,
                    "ModuleTokens": ["A500", "A700"],
                    "ModuleHierarchyPaths": ["A500-1", "A700-1"],
                    "Endpoints": [endpoint("A500-1", 1), endpoint("A700-1", 2)],
                }
            ],
        }

    def test_remove_does_not_mutate_source(self) -> None:
        original = copy.deepcopy(self.graph)
        result = compile_mate_graph_patch(
            self.graph,
            {
                "schemaVersion": "mate-graph-patch/v1",
                "includeModuleTokens": ["A500", "A700"],
                "baseModuleToken": "A500",
                "operations": [{"operation": "removeMate", "mateName": "距离8"}],
            },
        )
        self.assertEqual(self.graph, original)
        self.assertEqual(result["ModuleCount"], 2)
        self.assertEqual(result["InterModuleMateCount"], 0)
        self.assertEqual(len(result["SourceGraphProvenance"]["sha256"]), 64)
        self.assertEqual(len(result["PatchAudit"]["patchSha256"]), 64)

    def test_update_distance_records_before_and_after(self) -> None:
        result = compile_mate_graph_patch(
            self.graph,
            {"schemaVersion": "mate-graph-patch/v1", "operations": [{"operation": "updateMate", "mateName": "距离8", "changes": {"Distance": 0.06}}]},
        )
        self.assertEqual(result["Mates"][0]["Distance"], 0.06)
        audit = result["PatchAudit"]["operations"][0]
        self.assertEqual(audit["before"]["Distance"], 0.05)
        self.assertEqual(audit["after"]["Distance"], 0.06)

    def test_add_can_reuse_exported_endpoints(self) -> None:
        result = compile_mate_graph_patch(
            self.graph,
            {
                "schemaVersion": "mate-graph-patch/v1",
                "operations": [
                    {
                        "operation": "addMate",
                        "copyEndpointsFromMate": "距离8",
                        "mate": {
                            "MateName": "人工平行1",
                            "MateType": 3,
                            "MateTypeName": "swMatePARALLEL",
                            "Alignment": 0,
                            "AlignmentName": "swMateAlignALIGNED",
                            "Distance": None,
                            "Angle": None,
                        },
                    }
                ]
            },
        )
        self.assertEqual(result["InterModuleMateCount"], 2)
        self.assertEqual(result["Mates"][1]["Endpoints"], self.graph["Mates"][0]["Endpoints"])

    def test_conflicting_distances_are_rejected(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "Conflicting distance mates"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "operations": [
                        {
                            "operation": "addMate",
                            "copyEndpointsFromMate": "距离8",
                            "mate": {
                                "MateName": "冲突距离",
                                "MateType": 5,
                                "MateTypeName": "swMateDISTANCE",
                                "Alignment": 1,
                                "AlignmentName": "swMateAlignANTI_ALIGNED",
                                "Distance": 0.06,
                                "Angle": None,
                            },
                        }
                    ]
                },
            )

    def test_coincident_and_nonzero_distance_on_same_faces_are_rejected(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "Coincident and non-zero distance"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "operations": [
                        {
                            "operation": "addMate",
                            "copyEndpointsFromMate": "距离8",
                            "mate": {
                                "MateName": "冲突重合",
                                "MateType": 0,
                                "MateTypeName": "swMateCOINCIDENT",
                                "Alignment": 1,
                                "AlignmentName": "swMateAlignANTI_ALIGNED",
                                "Distance": None,
                                "Angle": None,
                            },
                        }
                    ],
                },
            )

    def test_parallel_and_perpendicular_on_same_faces_are_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["Mates"][0].update(
            {"MateType": 3, "MateTypeName": "swMatePARALLEL", "Distance": None}
        )
        with self.assertRaisesRegex(MateGraphEditError, "Contradictory planar orientation"):
            compile_mate_graph_patch(
                graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "operations": [
                        {
                            "operation": "addMate",
                            "copyEndpointsFromMate": "距离8",
                            "mate": {
                                "MateName": "冲突垂直",
                                "MateType": 2,
                                "MateTypeName": "swMatePERPENDICULAR",
                                "Alignment": 0,
                                "AlignmentName": "swMateAlignALIGNED",
                                "Distance": None,
                                "Angle": None,
                            },
                        }
                    ],
                },
            )

    def test_unknown_selected_mate_is_rejected(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "Unknown includeMateNames"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "includeMateNames": ["不存在"],
                    "operations": [],
                },
            )

    def test_base_must_remain_in_effective_module_set(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "outside the effective Modules"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "includeModuleTokens": ["A500", "A700"],
                    "operations": [],
                },
            )

    def test_add_can_expand_two_endpoint_ids_from_catalog(self) -> None:
        catalog = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "SourceAssemblyPath": "prototype.SLDASM",
            "Endpoints": [
                {"EndpointId": "face:a500:one", "Endpoint": endpoint("A500-1", 3) | {"ModuleToken": "A500"}},
                {"EndpointId": "face:a700:two", "Endpoint": endpoint("A700-1", 4) | {"ModuleToken": "A700"}},
            ],
        }
        result = compile_mate_graph_patch(
            self.graph,
            {
                "schemaVersion": "mate-graph-patch/v1",
                "operations": [
                    {
                        "operation": "addMate",
                        "endpointIds": ["face:a500:one", "face:a700:two"],
                        "mate": {
                            "MateName": "目录平行1",
                            "MateType": 3,
                            "MateTypeName": "swMatePARALLEL",
                            "Alignment": 0,
                            "AlignmentName": "swMateAlignALIGNED",
                            "Distance": None,
                            "Angle": None,
                        },
                    }
                ],
            },
            catalog,
        )
        added = result["Mates"][1]
        self.assertEqual([item["Index"] for item in added["Endpoints"]], [0, 1])
        self.assertEqual(added["ModuleTokens"], ["A500", "A700"])
        self.assertEqual(result["PatchAudit"]["operations"][0]["endpointIds"], ["face:a500:one", "face:a700:two"])
        self.assertEqual(len(result["EndpointCatalogProvenance"]["sha256"]), 64)

    def test_endpoint_ids_require_catalog(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "require an endpoint catalog"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "operations": [
                        {
                            "operation": "addMate",
                            "endpointIds": ["face:a500:one", "face:a700:two"],
                            "mate": {
                                "MateName": "目录距离1",
                                "MateType": 5,
                                "MateTypeName": "swMateDISTANCE",
                                "Alignment": 1,
                                "AlignmentName": "swMateAlignANTI_ALIGNED",
                                "Distance": 0.06,
                                "Angle": None,
                            },
                        }
                    ],
                },
            )

    def test_add_module_then_add_mate(self) -> None:
        source = copy.deepcopy(self.graph)
        source["Modules"] = [item for item in source["Modules"] if item["ModuleToken"] != "A500"]
        source["Mates"] = []
        catalog = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "Endpoints": [
                {"EndpointId": "face:a500:one", "Endpoint": endpoint("A500-1", 3) | {"ModuleToken": "A500"}},
                {"EndpointId": "face:a700:two", "Endpoint": endpoint("A700-1", 4) | {"ModuleToken": "A700"}},
            ],
        }
        added_module = next(item for item in self.graph["Modules"] if item["ModuleToken"] == "A500")

        result = compile_mate_graph_patch(
            source,
            {
                "schemaVersion": "mate-graph-patch/v1",
                "baseModuleToken": "A700",
                "operations": [
                    {"operation": "addModule", "module": added_module},
                    {
                        "operation": "addMate",
                        "endpointIds": ["face:a500:one", "face:a700:two"],
                        "mate": {
                            "MateName": "新增组件距离",
                            "MateType": 5,
                            "MateTypeName": "swMateDISTANCE",
                            "Alignment": 1,
                            "AlignmentName": "swMateAlignANTI_ALIGNED",
                            "Distance": 0.05,
                            "Angle": None,
                        },
                    },
                ],
            },
            catalog,
        )

        self.assertEqual(result["ModuleCount"], 3)
        self.assertEqual(result["InterModuleMateCount"], 1)
        self.assertEqual(result["PatchAudit"]["operations"][0]["operation"], "addModule")

    def test_source_mate_suppression_policy_rejects_new_mate_name(self) -> None:
        with self.assertRaisesRegex(
            MateGraphEditError, "outside the immutable source graph"
        ):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "sourceMateNamesToSuppress": ["not-in-source"],
                    "operations": [],
                },
            )

    def test_target_leaf_pose_anchor_requires_finite_transform(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "16 finite transform"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "targetLeafPoseAnchors": [
                        {
                            "relativeLeafHierarchyPath": "moving-branch-1",
                            "transform": [1.0, 2.0],
                        }
                    ],
                    "operations": [],
                },
            )

    def test_add_module_rejects_duplicate_hierarchy_path(self) -> None:
        with self.assertRaisesRegex(MateGraphEditError, "HierarchyPath already exists"):
            compile_mate_graph_patch(
                self.graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "operations": [
                        {"operation": "addModule", "module": self.graph["Modules"][0]}
                    ],
                },
            )

    def test_preserves_imported_width_mate_advanced_options(self) -> None:
        width = {
            "MateName": "宽度10",
            "MateType": 11,
            "MateTypeName": "swMateWIDTH",
            "Alignment": 0,
            "AlignmentName": "swMateAlignALIGNED",
            "Distance": None,
            "Angle": None,
            "IsSuppressed": False,
            "ModuleTokens": ["A600", "A700"],
            "ModuleHierarchyPaths": ["A600-1", "A700-1"],
            "Endpoints": [
                endpoint("A600-1", 0),
                endpoint("A600-1", 1),
                endpoint("A700-1", 2),
                endpoint("A700-1", 3),
            ],
            "AdvancedOptions": {
                "WidthConstraintType": 0,
                "WidthPercentDistanceFromEnd": -1.0,
                "WidthDistanceFromEnd": -1.0,
                "WidthFlipDimension": False,
                "WidthEndpointIndices": [0, 1],
                "TabEndpointIndices": [2, 3],
            },
        }
        graph = copy.deepcopy(self.graph)
        graph["Mates"] = [width]

        result = compile_mate_graph_patch(
            graph,
            {
                "schemaVersion": "mate-graph-patch/v1",
                "includeModuleTokens": ["A600", "A700"],
                "baseModuleToken": "A600",
                "operations": [],
            },
        )

        self.assertEqual(result["InterModuleMateCount"], 1)
        self.assertEqual(result["Mates"][0]["AdvancedOptions"], width["AdvancedOptions"])

    def test_width_mate_requires_explicit_width_and_tab_groups(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["Mates"] = [
            {
                "MateName": "宽度10",
                "MateType": 11,
                "MateTypeName": "swMateWIDTH",
                "ModuleTokens": ["A600", "A700"],
                "ModuleHierarchyPaths": ["A600-1", "A700-1"],
                "Endpoints": [
                    endpoint("A600-1", 0),
                    endpoint("A600-1", 1),
                    endpoint("A700-1", 2),
                    endpoint("A700-1", 3),
                ],
            }
        ]
        with self.assertRaisesRegex(MateGraphEditError, "requires two width faces"):
            compile_mate_graph_patch(
                graph,
                {
                    "schemaVersion": "mate-graph-patch/v1",
                    "includeModuleTokens": ["A600", "A700"],
                    "baseModuleToken": "A600",
                    "operations": [],
                },
            )


if __name__ == "__main__":
    unittest.main()

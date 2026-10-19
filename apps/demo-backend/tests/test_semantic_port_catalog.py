from __future__ import annotations

import unittest

from demo_backend.semantic_port_catalog import (
    SemanticPortCatalogError,
    build_semantic_assembly_plan,
    build_semantic_connection_patch,
    select_semantic_port,
    validate_semantic_port_catalog,
)


def endpoint(endpoint_id: str, token: str, path: str, face: int) -> dict:
    return {
        "EndpointId": endpoint_id,
        "GeometryClass": "Plane",
        "Endpoint": {
            "ModuleToken": token,
            "ModuleHierarchyPath": path,
            "RelativeLeafHierarchyPath": f"{token}-leaf",
            "GeometryType": "Face",
            "BodyIndex": 0,
            "FaceIndexInBody": face,
        },
    }


class SemanticPortCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoints = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "Endpoints": [
                endpoint("face:a500:reference", "A500", "A500-1", 11),
                endpoint("face:a700:reference", "A700", "A700-1", 3),
            ],
        }
        self.catalog = {
            "schemaVersion": "semantic-port-catalog/v1",
            "projectId": "project02",
            "ports": [
                {
                    "portId": "A500.spacing_reference",
                    "displayName": "A500间距基准",
                    "moduleToken": "A500",
                    "moduleHierarchyPath": "A500-1",
                    "category": "mechanical",
                    "interfaceType": "planar_spacing_reference",
                    "status": "confirmed",
                    "endpointBindings": [
                        {"role": "primary", "endpointId": "face:a500:reference"}
                    ],
                },
                {
                    "portId": "A700.spacing_reference",
                    "displayName": "A700间距基准",
                    "moduleToken": "A700",
                    "moduleHierarchyPath": "A700-1",
                    "category": "mechanical",
                    "interfaceType": "planar_spacing_reference",
                    "status": "provisional",
                    "endpointBindings": [
                        {"role": "primary", "endpointId": "face:a700:reference"}
                    ],
                },
            ],
            "connectionTemplates": [
                {
                    "templateId": "planar_distance",
                    "interfaceTypeA": "planar_spacing_reference",
                    "interfaceTypeB": "planar_spacing_reference",
                    "mateSteps": [
                        {
                            "mateName": "语义端口距离1",
                            "mateType": 5,
                            "mateTypeName": "swMateDISTANCE",
                            "alignment": 1,
                            "alignmentName": "swMateAlignANTI_ALIGNED",
                            "endpointRoleA": "primary",
                            "endpointRoleB": "primary",
                            "distanceMeters": 0.05,
                        }
                    ],
                }
            ],
        }
        self.source = {
            "SchemaVersion": "assembly-module-mate-graph/v2",
            "Modules": [
                {
                    "ModuleToken": "A700",
                    "Name": "A700-1",
                    "Path": "A700.SLDASM",
                    "HierarchyPath": "A700-1",
                }
            ],
            "Mates": [],
        }
        self.a500 = {
            "ModuleToken": "A500",
            "Name": "A500-1",
            "Path": "A500.SLDASM",
            "HierarchyPath": "A500-1",
        }

    def test_validates_and_reports_provisional_port(self) -> None:
        result = validate_semantic_port_catalog(self.catalog, self.endpoints)
        self.assertTrue(result["success"])
        self.assertEqual(result["portCount"], 2)
        self.assertEqual(len(result["warnings"]), 1)

    def test_selects_port_by_stable_id(self) -> None:
        self.assertEqual(
            select_semantic_port(self.catalog, "A500.spacing_reference")["moduleToken"],
            "A500",
        )

    def test_compiles_new_component_and_port_connection(self) -> None:
        result = build_semantic_connection_patch(
            self.source,
            self.catalog,
            self.endpoints,
            {
                "schemaVersion": "semantic-connection-request/v1",
                "connectionId": "A500-to-A700",
                "portAId": "A500.spacing_reference",
                "portBId": "A700.spacing_reference",
                "templateId": "planar_distance",
                "baseModuleToken": "A700",
                "componentToAdd": self.a500,
                "parameters": {"distanceMeters": 0.06},
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["effectiveModuleCount"], 2)
        self.assertEqual(result["summary"]["generatedMateCount"], 1)
        self.assertEqual(result["summary"]["portAId"], "A500.spacing_reference")
        self.assertEqual(result["summary"]["portBId"], "A700.spacing_reference")
        effective = result["effectiveGraph"]
        self.assertEqual(effective["Mates"][0]["Distance"], 0.06)
        self.assertEqual(
            effective["SemanticConnectionAudit"]["executionMode"],
            "isolated_rebuild_from_augmented_graph",
        )

    def test_rejects_endpoint_from_wrong_module(self) -> None:
        self.catalog["ports"][0]["moduleToken"] = "A700"
        with self.assertRaisesRegex(SemanticPortCatalogError, "different module"):
            validate_semantic_port_catalog(self.catalog, self.endpoints)

    def test_rejects_incompatible_interface_types(self) -> None:
        self.catalog["ports"][1]["interfaceType"] = "optical_target"
        with self.assertRaisesRegex(SemanticPortCatalogError, "incompatible"):
            build_semantic_connection_patch(
                self.source,
                self.catalog,
                self.endpoints,
                {
                    "schemaVersion": "semantic-connection-request/v1",
                    "connectionId": "bad",
                    "portAId": "A500.spacing_reference",
                    "portBId": "A700.spacing_reference",
                    "templateId": "planar_distance",
                    "baseModuleToken": "A700",
                },
            )

    def test_validate_only_relation_is_audited_without_creating_a_mate(self) -> None:
        self.catalog["connectionTemplates"][0]["mateSteps"][0][
            "applicationMode"
        ] = "validate_only"
        self.catalog["connectionTemplates"][0]["mateSteps"][0]["tolerance"] = {
            "distanceMeters": 0.0001
        }
        result = build_semantic_connection_patch(
            self.source,
            self.catalog,
            self.endpoints,
            {
                "schemaVersion": "semantic-connection-request/v1",
                "connectionId": "A500-to-A700-check",
                "portAId": "A500.spacing_reference",
                "portBId": "A700.spacing_reference",
                "templateId": "planar_distance",
                "baseModuleToken": "A700",
                "componentToAdd": self.a500,
            },
        )
        self.assertEqual(result["summary"]["generatedMateCount"], 0)
        self.assertEqual(result["effectiveGraph"]["Mates"], [])
        validations = result["effectiveGraph"]["SemanticConnectionAudit"][
            "validationRelations"
        ]
        self.assertEqual(len(validations), 1)
        self.assertEqual(validations[0]["expectedDistanceMeters"], 0.05)
        self.assertEqual(
            [item["ModuleToken"] for item in validations[0]["endpoints"]],
            ["A500", "A700"],
        )
        self.assertEqual(
            [item["Index"] for item in validations[0]["endpoints"]],
            [0, 1],
        )

    def test_compiles_multi_connection_plan_with_four_face_width_mate(self) -> None:
        endpoints = {
            "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
            "Endpoints": [
                endpoint("a500-mount", "A500", "A500-1", 0),
                endpoint("a500-tab-a", "A500", "A500-1", 11),
                endpoint("a500-tab-b", "A500", "A500-1", 10),
                endpoint("a500-offset", "A500", "A500-1", 61),
                endpoint("a600-mount", "A600", "A600-1", 4),
                endpoint("a600-width-a", "A600", "A600-1", 0),
                endpoint("a600-width-b", "A600", "A600-1", 2),
                endpoint("a600-offset", "A600", "A600-1", 3),
                endpoint("a700-spacing", "A700", "A700-1", 3),
            ],
        }
        catalog = {
            "schemaVersion": "semantic-port-catalog/v1",
            "projectId": "project02",
            "ports": [
                {
                    "portId": "A500.install",
                    "moduleToken": "A500",
                    "moduleHierarchyPath": "A500-1",
                    "category": "mechanical",
                    "interfaceType": "a500_installation",
                    "status": "confirmed",
                    "endpointBindings": [
                        {"role": "mount", "endpointId": "a500-mount"},
                        {"role": "tab_a", "endpointId": "a500-tab-a"},
                        {"role": "tab_b", "endpointId": "a500-tab-b"},
                        {"role": "offset", "endpointId": "a500-offset"},
                    ],
                },
                {
                    "portId": "A600.install",
                    "moduleToken": "A600",
                    "moduleHierarchyPath": "A600-1",
                    "category": "mechanical",
                    "interfaceType": "a600_installation",
                    "status": "confirmed",
                    "endpointBindings": [
                        {"role": "mount", "endpointId": "a600-mount"},
                        {"role": "width_a", "endpointId": "a600-width-a"},
                        {"role": "width_b", "endpointId": "a600-width-b"},
                        {"role": "offset", "endpointId": "a600-offset"},
                    ],
                },
                {
                    "portId": "A500.spacing",
                    "moduleToken": "A500",
                    "moduleHierarchyPath": "A500-1",
                    "category": "spatial",
                    "interfaceType": "spacing",
                    "status": "confirmed",
                    "endpointBindings": [
                        {"role": "primary", "endpointId": "a500-tab-a"}
                    ],
                },
                {
                    "portId": "A700.spacing",
                    "moduleToken": "A700",
                    "moduleHierarchyPath": "A700-1",
                    "category": "spatial",
                    "interfaceType": "spacing",
                    "status": "confirmed",
                    "endpointBindings": [
                        {"role": "primary", "endpointId": "a700-spacing"}
                    ],
                },
            ],
            "connectionTemplates": [
                {
                    "templateId": "install",
                    "interfaceTypeA": "a500_installation",
                    "interfaceTypeB": "a600_installation",
                    "mateSteps": [
                        {
                            "mateName": "coincident",
                            "mateType": 0,
                            "mateTypeName": "swMateCOINCIDENT",
                            "endpointRoleA": "mount",
                            "endpointRoleB": "mount",
                        },
                        {
                            "mateName": "width",
                            "mateType": 11,
                            "mateTypeName": "swMateWIDTH",
                            "endpointRoles": [
                                {"side": "B", "role": "width_a"},
                                {"side": "B", "role": "width_b"},
                                {"side": "A", "role": "tab_a"},
                                {"side": "A", "role": "tab_b"},
                            ],
                            "advancedOptions": {
                                "WidthConstraintType": 0,
                                "WidthPercentDistanceFromEnd": -1,
                                "WidthDistanceFromEnd": -1,
                                "WidthFlipDimension": False,
                                "WidthEndpointIndices": [0, 1],
                                "TabEndpointIndices": [2, 3],
                            },
                        },
                        {
                            "mateName": "offset",
                            "mateType": 5,
                            "mateTypeName": "swMateDISTANCE",
                            "endpointRoleA": "offset",
                            "endpointRoleB": "offset",
                            "distanceMeters": 0.06,
                        },
                    ],
                },
                {
                    "templateId": "spacing",
                    "interfaceTypeA": "spacing",
                    "interfaceTypeB": "spacing",
                    "mateSteps": [
                        {
                            "mateName": "spacing",
                            "mateType": 5,
                            "mateTypeName": "swMateDISTANCE",
                            "endpointRoleA": "primary",
                            "endpointRoleB": "primary",
                            "distanceMeters": 0.05,
                        }
                    ],
                },
            ],
        }
        source = {
            "SchemaVersion": "assembly-module-mate-graph/v2",
            "Modules": [
                {"ModuleToken": "A600", "Name": "A600-1", "Path": "A600.SLDASM", "HierarchyPath": "A600-1"},
                {"ModuleToken": "A700", "Name": "A700-1", "Path": "A700.SLDASM", "HierarchyPath": "A700-1"},
            ],
            "Mates": [],
        }
        result = build_semantic_assembly_plan(
            source,
            catalog,
            endpoints,
            {
                "schemaVersion": "semantic-assembly-plan/v1",
                "planId": "add-A500",
                "baseModuleToken": "A600",
                "initialPlacementMode": "deterministic",
                "caseAnchoredModuleTokens": ["A500"],
                "componentToAdd": self.a500,
                "connections": [
                    {
                        "connectionId": "A500-A600",
                        "portAId": "A500.install",
                        "portBId": "A600.install",
                        "templateId": "install",
                    },
                    {
                        "connectionId": "A500-A700",
                        "portAId": "A500.spacing",
                        "portBId": "A700.spacing",
                        "templateId": "spacing",
                    },
                ],
            },
        )
        self.assertEqual(result["summary"]["generatedMateCount"], 4)
        self.assertEqual(result["summary"]["effectiveModuleCount"], 3)
        self.assertEqual(result["summary"]["initialPlacementMode"], "deterministic")
        self.assertEqual(result["summary"]["caseAnchoredModuleTokens"], ["A500"])
        self.assertEqual(
            result["summary"]["constraintAssessment"]["fullyLocatesAddedComponent"],
            "case_anchor_requires_cad_verification",
        )
        width = next(item for item in result["effectiveGraph"]["Mates"] if item["MateName"] == "width")
        self.assertEqual([item["ModuleToken"] for item in width["Endpoints"]], ["A600", "A600", "A500", "A500"])
        self.assertEqual(width["AdvancedOptions"]["WidthEndpointIndices"], [0, 1])


if __name__ == "__main__":
    unittest.main()

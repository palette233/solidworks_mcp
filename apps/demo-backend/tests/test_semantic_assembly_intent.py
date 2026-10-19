from __future__ import annotations

import copy
import unittest

from demo_backend.semantic_assembly_intent import (
    SemanticAssemblyIntentError,
    parse_project02_semantic_assembly_intent,
    resolve_semantic_assembly_intent,
)


REQUIREMENT = (
    "在项目02中，以A600和A700作为固定上下文，新增A500。"
    "A500保持刚性，A700保持柔性。将A500安装到A600，"
    "并验证A500与A700保持50 mm间距，不要将该间距作为驱动配合。"
    "另存为独立装配体。"
)


def port(port_id: str, token: str, interface_type: str, purpose: str) -> dict:
    return {
        "portId": port_id,
        "moduleToken": token,
        "interfaceType": interface_type,
        "capabilities": [purpose],
        "status": "confirmed",
        "evidence": ["test evidence"],
    }


class SemanticAssemblyIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {
            "projectId": "project02",
            "ports": [
                port("A500.install", "A500", "a500-install", "installation"),
                port("A600.install", "A600", "a600-install", "installation"),
                port("A500.spacing", "A500", "spacing", "spacing"),
                port("A700.spacing", "A700", "spacing", "spacing"),
            ],
            "connectionTemplates": [
                {
                    "templateId": "install",
                    "purposes": ["installation"],
                    "interfaceTypeA": "a500-install",
                    "interfaceTypeB": "a600-install",
                    "mateSteps": [{"mateName": "install", "mateType": 0}],
                },
                {
                    "templateId": "spacing-check",
                    "purposes": ["spacing"],
                    "interfaceTypeA": "spacing",
                    "interfaceTypeB": "spacing",
                    "mateSteps": [
                        {
                            "mateName": "spacing",
                            "mateType": 5,
                            "applicationMode": "validate_only",
                        }
                    ],
                },
            ],
        }
        self.source = {
            "Modules": [
                {"ModuleToken": "A600", "SolvingState": 0},
                {"ModuleToken": "A700", "SolvingState": 1},
            ]
        }
        self.plan_template = {
            "baseModuleToken": "A600",
            "initialPlacementMode": "deterministic",
            "componentToAdd": {
                "ModuleToken": "A500",
                "HierarchyPath": "A500-1",
                "Path": "A500.SLDASM",
                "SolvingState": 0,
            },
        }

    def test_parses_controlled_requirement_without_geometric_entities(self) -> None:
        intent = parse_project02_semantic_assembly_intent(REQUIREMENT)
        self.assertEqual(intent["moduleToAdd"], "A500")
        self.assertEqual(intent["fixedContextModules"], ["A600", "A700"])
        self.assertEqual(
            intent["componentSolvingStates"],
            {"A500": "rigid", "A700": "flexible"},
        )
        self.assertEqual(
            [item["applicationMode"] for item in intent["relationships"]],
            ["driving", "validate_only"],
        )
        self.assertFalse(intent["parser"]["geometricEntitiesGenerated"])

    def test_resolves_unique_ports_and_builds_plan(self) -> None:
        intent = parse_project02_semantic_assembly_intent(REQUIREMENT)
        result = resolve_semantic_assembly_intent(
            intent, self.catalog, self.source, self.plan_template
        )
        plan = result["assemblyPlan"]
        self.assertEqual(plan["fixedContextModuleTokens"], ["A600", "A700"])
        self.assertEqual(len(plan["connections"]), 2)
        self.assertEqual(plan["connections"][0]["portAId"], "A500.install")
        self.assertEqual(plan["connections"][1]["templateId"], "spacing-check")
        self.assertEqual(plan["connections"][1]["parameters"]["distanceMeters"], 0.05)
        self.assertTrue(result["requiresHumanConfirmation"])
        self.assertTrue(all(item["matched"] for item in result["solvingStateChecks"]))

    def test_rejects_request_that_turns_validation_spacing_into_driver(self) -> None:
        requirement = REQUIREMENT.replace(
            "验证A500与A700保持50 mm间距，不要将该间距作为驱动配合",
            "将A500与A700的50 mm间距作为驱动配合",
        )
        intent = parse_project02_semantic_assembly_intent(requirement)
        with self.assertRaisesRegex(SemanticAssemblyIntentError, "过约束"):
            resolve_semantic_assembly_intent(
                intent, self.catalog, self.source, self.plan_template
            )

    def test_rejects_ambiguous_top_scoring_ports(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        duplicate = copy.deepcopy(catalog["ports"][0])
        duplicate["portId"] = "A500.install.alternative"
        catalog["ports"].append(duplicate)
        intent = parse_project02_semantic_assembly_intent(REQUIREMENT)
        with self.assertRaisesRegex(SemanticAssemblyIntentError, "人工消歧"):
            resolve_semantic_assembly_intent(
                intent, catalog, self.source, self.plan_template
            )

    def test_rejects_solving_state_mismatch(self) -> None:
        source = copy.deepcopy(self.source)
        source["Modules"][1]["SolvingState"] = 0
        intent = parse_project02_semantic_assembly_intent(REQUIREMENT)
        with self.assertRaisesRegex(SemanticAssemblyIntentError, "A700要求flexible"):
            resolve_semantic_assembly_intent(
                intent, self.catalog, source, self.plan_template
            )

    def test_rejects_unknown_project_or_module(self) -> None:
        with self.assertRaisesRegex(SemanticAssemblyIntentError, "项目02"):
            parse_project02_semantic_assembly_intent(REQUIREMENT.replace("项目02", "项目03"))
        with self.assertRaisesRegex(SemanticAssemblyIntentError, "尚不支持"):
            parse_project02_semantic_assembly_intent(REQUIREMENT + "并连接A800。")


if __name__ == "__main__":
    unittest.main()

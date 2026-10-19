from __future__ import annotations

import unittest
from pathlib import Path

from demo_backend.mate_reconstruction_pipeline import (
    apply_graph_audit,
    audit_full_graph_semantics,
    audit_rebuild_closure,
    analyze_project02_top_level_dof,
    new_pipeline_status,
    update_pipeline_stage,
)


def endpoint(token: str, index: int = 0) -> dict:
    return {
        "Index": index,
        "ModuleToken": token,
        "ModuleHierarchyPath": f"{token}-{index + 1}",
        "LeafHierarchyPath": f"{token}-{index + 1}",
        "GeometryType": "Face",
        "BodyIndex": 0,
        "FaceIndexInBody": index,
        "FaceArea": 0.01,
        "FaceCenterLocal": [0.0, 0.0, 0.0],
        "FaceNormalLocal": [0.0, 0.0, 1.0],
        "SourceAssemblyPersistentReferenceBase64": "cGVyc2lzdGVudA==",
    }


def graph_fixture() -> dict:
    tokens = ["A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401", "T401"]
    modules = [
        {
            "ModuleToken": token,
            "HierarchyPath": f"{token}-{index + 1}",
            "ReferencedConfiguration": "Default",
            "SolvingState": 0,
            "SolvingStateName": "swComponentRigidSolving",
        }
        for index, token in enumerate(tokens)
    ]
    mates = []
    for index in range(24):
        mates.append(
            {
                "MateName": f"重合{index}",
                "MateTypeName": "swMateCOINCIDENT",
                "Endpoints": [endpoint("A600", 0), endpoint("A700", 1)],
            }
        )
    for name, other, instance in (("重合14", "A600", 1), ("距离10", "A600", 1), ("距离28", "A200", 2)):
        t401 = endpoint("T401", 0)
        t401["ModuleHierarchyPath"] = f"T401-{instance}"
        mate = {
            "MateName": name,
            "MateTypeName": "swMateCOINCIDENT" if name == "重合14" else "swMateDISTANCE",
            "Endpoints": [t401, endpoint(other, 1)],
        }
        if mate["MateTypeName"] == "swMateDISTANCE":
            mate["AdvancedOptions"] = {"DistanceFlipDimension": False}
        mates.append(mate)
    return {"SchemaVersion": "solidworks-module-mate-graph/v1.4", "Modules": modules, "Mates": mates}


class MateReconstructionPipelineTests(unittest.TestCase):
    def test_complete_v14_graph_passes_stage_one_audit(self) -> None:
        audit = audit_full_graph_semantics(graph_fixture())
        self.assertTrue(audit["success"])
        self.assertTrue(audit["t401RecoveryReadiness"]["readyForTargetedLiveRecovery"])

    def test_v13_graph_without_solving_state_fails(self) -> None:
        graph = graph_fixture()
        graph["SchemaVersion"] = "solidworks-module-mate-graph/v1.3"
        for module in graph["Modules"]:
            module.pop("SolvingState")
            module.pop("SolvingStateName")
        audit = audit_full_graph_semantics(graph)
        failed = {item["name"] for item in audit["checks"] if not item["passed"]}
        self.assertIn("schema_is_v1_4", failed)
        self.assertIn("all_module_solving_states_recorded", failed)

    def test_passing_audit_advances_monitor_to_t401(self) -> None:
        audit = audit_full_graph_semantics(graph_fixture())
        status = apply_graph_audit(new_pipeline_status(), audit, Path("graph.json"), Path("audit.json"))
        self.assertEqual(status["stages"][0]["status"], "PASSED")
        self.assertEqual(status["stages"][1]["status"], "IN_PROGRESS")
        self.assertEqual(status["activeStage"], "t401_face_recovery")

    def test_passing_stage_advances_to_next_stage(self) -> None:
        status = update_pipeline_stage(
            new_pipeline_status(),
            "t401_face_recovery",
            "PASSED",
            evidence=["result.json"],
        )
        self.assertEqual(status["stages"][1]["status"], "PASSED")
        self.assertEqual(status["stages"][2]["status"], "IN_PROGRESS")
        self.assertEqual(status["activeStage"], "mates_27_rebuild")

    def test_final_reopen_health_can_clear_one_transient_creation_error(self) -> None:
        run = {
            "toolResult": {
                "Success": False,
                "RequestedModuleCount": 10,
                "CreatedMateCount": 27,
                "ReopenedModuleCount": 10,
                "ReopenedMateCount": 27,
                "ReopenedMateParametersMatch": True,
                "ReopenedComponentsNotOverConstrained": True,
                "ReopenedComponentSemanticsMatch": True,
                "MateResults": [{"MateName": "m1", "ErrorName": "swAddMateError_OverDefinedAssembly", "ErrorStatus": 3}],
                "ComponentStatuses": [],
            }
        }
        reopened = {"Mates": [{"MateName": f"m{index}"} for index in range(27)]}
        audit = audit_rebuild_closure(run, reopened)
        self.assertTrue(audit["success"])
        self.assertTrue(audit["transientErrorsAccepted"])

    def test_project02_dof_classifies_a800_and_two_t401_instances(self) -> None:
        graph = {
            "Mates": [
                {"MateName": "c1", "MateTypeName": "swMateCOINCIDENT", "Endpoints": [{"ModuleHierarchyPath": "T401-1", "FaceNormalWorld": [0, 1, 0]}]},
                {"MateName": "d1", "MateTypeName": "swMateDISTANCE", "Endpoints": [{"ModuleHierarchyPath": "T401-1", "FaceNormalWorld": [1, 0, 0]}]},
                {"MateName": "d2", "MateTypeName": "swMateDISTANCE", "Endpoints": [{"ModuleHierarchyPath": "T401-2", "FaceNormalWorld": [0, 0, 1]}]},
            ]
        }
        statuses = [
            {"ModuleToken": "A800", "SourceHierarchyPath": "A800-1", "ConstrainedStatusName": "swUnderConstrained"},
            {"ModuleToken": "T401", "SourceHierarchyPath": "T401-1", "ConstrainedStatusName": "swUnderConstrained"},
            {"ModuleToken": "T401", "SourceHierarchyPath": "T401-2", "ConstrainedStatusName": "swUnderConstrained"},
        ]
        result = analyze_project02_top_level_dof(graph, {"toolResult": {"ComponentStatuses": statuses}}, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["totalResidualTopLevelRigidPoseDof"], 5)
        self.assertEqual(len(result["minimalScalarAnchors"]), 5)


if __name__ == "__main__":
    unittest.main()

from demo_backend.relation_validation_state_audit import (
    analyze_relation_validation_state_dependency,
)


def test_failed_nested_flexible_endpoint_without_anchor_is_diagnosed():
    graph = {
        "Modules": [
            {
                "ModuleToken": "A700",
                "SolvingState": 1,
                "SolvingStateName": "swComponentFlexibleSolving",
            },
            {"ModuleToken": "A500", "SolvingState": 0},
        ],
        "SemanticAssemblyPlanAudit": {
            "ValidationRelations": [
                {
                    "RelationName": "距离8",
                    "ExpectedDistanceMeters": 0.05,
                    "Endpoints": [
                        {
                            "Index": 0,
                            "ModuleToken": "A500",
                            "RelativeLeafHierarchyPath": "A510/leaf",
                        },
                        {
                            "Index": 1,
                            "ModuleToken": "A700",
                            "RelativeLeafHierarchyPath": "A710/moving-leaf",
                        },
                    ],
                }
            ]
        },
    }
    result = {
        "validationResults": [
            {
                "RelationName": "距离8",
                "Passed": False,
                "ExpectedDistanceMeters": 0.05,
                "MeasuredDistanceMeters": 1.1,
                "AbsoluteErrorMeters": 1.05,
            }
        ]
    }
    installation = {
        "Mates": [
            {
                "MateName": "距离6",
                "IsSuppressed": False,
                "Endpoints": [
                    {
                        "ModuleToken": "A700",
                        "RelativeLeafHierarchyPath": "A710/moving-leaf",
                    }
                ],
            }
        ],
        "EditPolicy": {"TargetLeafPoseAnchors": []},
    }

    audit = analyze_relation_validation_state_dependency(
        graph, result, installation_graphs={"A700": installation}
    )

    assert audit["success"] is True
    assert audit["diagnosedFlexibleStateFailureCount"] == 1
    endpoint = audit["relations"][0]["endpoints"][1]
    assert endpoint["stateDependent"] is True
    assert endpoint["installationDrivingMateNamesUsingLeaf"] == ["距离6"]


def test_external_pose_mismatch_takes_precedence_over_internal_state_diagnosis():
    graph = {
        "Modules": [
            {"ModuleToken": "A700", "SolvingState": 1},
            {"ModuleToken": "A500", "SolvingState": 0},
        ],
        "SemanticAssemblyPlanAudit": {
            "ValidationRelations": [
                {
                    "RelationName": "距离8",
                    "Endpoints": [
                        {
                            "Index": 0,
                            "ModuleToken": "A500",
                            "RelativeLeafHierarchyPath": "A510/leaf",
                        },
                        {
                            "Index": 1,
                            "ModuleToken": "A700",
                            "RelativeLeafHierarchyPath": "A710/moving-leaf",
                        },
                    ],
                }
            ]
        },
    }
    result = {
        "validationResults": [{"RelationName": "距离8", "Passed": False}],
        "toolResult": {
            "ModulePoses": [
                {"ModuleToken": "A500", "MaximumTransformElementDelta": 0.0},
                {
                    "ModuleToken": "A700",
                    "MaximumTransformElementDelta": 1.17773302749,
                    "SourceTransform": [0.0, 0.0, 0.0],
                    "CurrentTransform": [0.0, 0.0, 1.17773302749],
                },
            ]
        },
    }

    audit = analyze_relation_validation_state_dependency(graph, result)

    assert audit["success"] is True
    assert audit["diagnosedExternalPoseFailureCount"] == 1
    assert audit["diagnosedFlexibleStateFailureCount"] == 0
    relation = audit["relations"][0]
    assert relation["diagnosis"] == (
        "failed_with_external_module_pose_branch_mismatch"
    )
    assert relation["externalPoseMismatches"][0]["moduleToken"] == "A700"

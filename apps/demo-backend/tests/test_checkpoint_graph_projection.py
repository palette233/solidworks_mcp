from scripts.run_context_mate_graph_insert import project_target_context_graph


def test_checkpoint_projection_removes_unrelated_prototype_modules():
    graph = {
        "ModuleCount": 4,
        "InterModuleMateCount": 2,
        "Modules": [
            {"ModuleToken": "AA00"},
            {"ModuleToken": "AG00"},
            {"ModuleToken": "AH00"},
            {"ModuleToken": "OTHER"},
        ],
        "Mates": [
            {"MateName": "AH-on-AA", "ModuleTokens": ["AH00", "AA00"]},
            {"MateName": "AG-on-AA", "ModuleTokens": ["AG00", "AA00"]},
        ],
    }

    projected = project_target_context_graph(graph, "ah00")

    assert projected["ModuleCount"] == 2
    assert projected["InterModuleMateCount"] == 1
    assert {row["ModuleToken"] for row in projected["Modules"]} == {"AA00", "AH00"}
    assert [row["MateName"] for row in projected["Mates"]] == ["AH-on-AA"]
    assert projected["CheckpointExecutionProjection"]["moduleTokens"] == [
        "AA00",
        "AH00",
    ]

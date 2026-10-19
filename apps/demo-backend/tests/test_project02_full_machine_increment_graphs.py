from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_full_machine_increment_graphs.py"
SOURCE = ROOT / "demo/mate_reconstruction_pipeline/project02_full27_source_pose_v1.effective.json"


def load_module():
    spec = importlib.util.spec_from_file_location("full_machine_graphs", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builds_a200_and_two_distinct_t401_instance_graphs():
    module = load_module()
    graphs = module.build_all(module.read_json(SOURCE))

    assert set(graphs) == {"A200", "T401-1", "T401-2"}
    assert len(graphs["A200"]["Mates"]) == 3
    assert len(graphs["T401-1"]["Mates"]) == 2
    assert len(graphs["T401-2"]["Mates"]) == 1
    assert graphs["T401-1"]["SemanticAssemblyPlanAudit"]["targetHierarchyPath"].endswith("-1")
    assert graphs["T401-2"]["SemanticAssemblyPlanAudit"]["targetHierarchyPath"].endswith("-2")


def test_every_graph_is_count_consistent_and_target_scoped():
    module = load_module()
    graphs = module.build_all(module.read_json(SOURCE))

    for graph in graphs.values():
        assert graph["SchemaVersion"] == "editable-module-mate-graph/v1"
        assert graph["ModuleCount"] == len(graph["Modules"])
        assert graph["InterModuleMateCount"] == len(graph["Mates"])
        target = graph["SemanticAssemblyPlanAudit"]["targetHierarchyPath"]
        assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == [target]
        for mate in graph["Mates"]:
            endpoint_hierarchies = {
                item["ModuleHierarchyPath"] for item in mate["Endpoints"]
            }
            assert target in endpoint_hierarchies


def test_t401_second_instance_uses_a200_as_context():
    module = load_module()
    graph = module.build_all(module.read_json(SOURCE))["T401-2"]

    context = graph["Modules"][0]
    assert context["ModuleToken"] == "A200"
    assert graph["EditPolicy"]["baseModuleToken"] == "A200"
    assert graph["Mates"][0]["Distance"] == 0.059

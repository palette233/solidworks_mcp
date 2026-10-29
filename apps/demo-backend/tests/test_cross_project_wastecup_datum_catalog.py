from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from demo_backend.cross_project_wastecup_datum_catalog import (
    CrossProjectWasteCupDatumCatalogError,
    build_wastecup_datum_catalog_package,
)


ROOT = Path(__file__).resolve().parents[3]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _support_inputs() -> dict:
    """Use immutable source fixtures; no live CAD or generated new-run fixture."""

    source = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
    graph = _read(source / "candidate_effective_mate_graph.json")
    audit = _read(source / "candidate_audit.json")
    policy = {
        "mode": "support_position_demo",
        "holePatternMatchRequired": False,
        "actualFixationMethod": "not_verified",
        "actualFixationNotice": "实际固定方式暂未验证",
        "directMechanicalCompatibilityClaim": False,
        "positionParametersMeters": {
            "longitudinal": 0.08,
            "lateral": 0.39,
            "supportGap": 0,
        },
        "targetSourceTransformMeaning": "identity_placeholder_not_final_pose_witness",
    }
    graph["SupportPositionDemoPolicy"] = copy.deepcopy(policy)
    audit.update(copy.deepcopy(policy))
    next(row for row in graph["Modules"] if row["ModuleToken"] == "P000")[
        "SourceTransform"
    ] = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    graph["EditPolicy"] = {
        "baseModuleToken": "A600",
        "initialPlacementMode": "deterministic",
        "initialPlacementVariant": 1,
        "sourceGraphImmutable": True,
        "fixedModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": [],
        "targetLeafPoseAnchors": [],
        "fixCaseAnchorBeforeMates": False,
    }
    return {
        "base_global_catalog": _read(
            ROOT / "demo/cross_project_substitution/expanded-project03-v1/"
            "relation-v62-project03-expanded-cross-project-chain-driving-20261014.catalog-preview.json"
        ),
        "candidate_graph": graph,
        "candidate_audit": audit,
        "a600_endpoint_catalog": _read(
            ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/"
            "project02-seven-addon-driving-v6/A300/face_endpoint_catalog.json"
        ),
        "p000_endpoint_catalog": _read(
            ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/"
            "project05-nonanchor-driving-v6/P000/face_endpoint_catalog.json"
        ),
        "semantic_catalog_path": "demo/test-support-position/semantic_port_catalog.json",
        "endpoint_catalog_path": "demo/test-support-position/face_endpoint_catalog.json",
        "base_graph_path": "demo/test-support-position/base_wastecup_datum_graph.json",
    }


def test_support_position_package_preserves_nonprototype_policy() -> None:
    inputs = _support_inputs()
    before = copy.deepcopy(inputs)
    package = build_wastecup_datum_catalog_package(**inputs)
    graph = package["baseGraph"]
    target = next(row for row in graph["Modules"] if row["ModuleToken"] == "P000")
    assert target["SourceTransform"] == [
        1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0
    ]
    assert graph["EditPolicy"] == inputs["candidate_graph"]["EditPolicy"]
    assert graph["EditPolicy"]["initialPlacementVariant"] == 1
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["A600"]
    assert graph["CaseAnchor"] is None
    assert graph["TargetLeafPoseAnchors"] == []
    policy = inputs["candidate_graph"]["SupportPositionDemoPolicy"]
    assert graph["SupportPositionDemoPolicy"] == policy
    assert package["semanticCatalog"]["supportPositionDemoPolicy"] == policy
    template = package["semanticCatalog"]["connectionTemplates"][0]
    assert template["constraintEffect"]["supportPositionDemoPolicy"] == policy
    assert template["purposes"] == ["installation", "datum_placement_demo"]
    assert template["constraintEffect"]["directMechanicalInterfaceCompatible"] is False
    global_template = next(
        row for row in package["candidateGlobalCatalog"]["connectionTemplates"]
        if row["globalTemplateId"] == package["globalTemplateId"]
    )
    assert global_template["constraintEffect"]["supportPositionDemoPolicy"] == policy
    assert global_template["provenance"]["effectiveMateGraphPath"] == inputs["base_graph_path"]
    assert inputs == before  # Published source dictionaries must not be mutated.


def test_support_position_parameters_propagate_and_change_template_identity() -> None:
    original_inputs = _support_inputs()
    original = build_wastecup_datum_catalog_package(**original_inputs)
    edited_inputs = copy.deepcopy(original_inputs)
    edited_graph = edited_inputs["candidate_graph"]
    for name, distance in (
        ("P000_A600_DATUM_DISTANCE_1", 0.09),
        ("P000_A600_DATUM_DISTANCE_2", 0.38),
    ):
        next(row for row in edited_graph["Mates"] if row["MateName"] == name)[
            "Distance"
        ] = distance
    parameters = {"longitudinal": 0.09, "lateral": 0.38, "supportGap": 0}
    edited_graph["SupportPositionDemoPolicy"]["positionParametersMeters"] = parameters
    edited_inputs["candidate_audit"]["positionParametersMeters"] = copy.deepcopy(parameters)
    edited = build_wastecup_datum_catalog_package(**edited_inputs)
    semantic_template = edited["semanticCatalog"]["connectionTemplates"][0]
    assert [step.get("distanceMeters") for step in semantic_template["mateSteps"]] == [
        0.09, 0.38, None
    ]
    assert edited["globalTemplateId"] != original["globalTemplateId"]
    assert semantic_template["templateId"] != original["semanticCatalog"]["connectionTemplates"][0]["templateId"]
    assert edited["baseGraph"]["SupportPositionDemoPolicy"]["positionParametersMeters"] == parameters
    assert [row["Distance"] for row in edited["baseGraph"]["Mates"][:2]] == [0.09, 0.38]
    global_template = next(
        row for row in edited["candidateGlobalCatalog"]["connectionTemplates"]
        if row["globalTemplateId"] == edited["globalTemplateId"]
    )
    assert global_template["mateSteps"] == semantic_template["mateSteps"]


@pytest.mark.parametrize("mismatch", ["audit_vs_policy", "graph_vs_policy", "support_gap"])
def test_support_position_rejects_parameter_mismatch(mismatch: str) -> None:
    inputs = _support_inputs()
    if mismatch == "audit_vs_policy":
        inputs["candidate_audit"]["positionParametersMeters"]["longitudinal"] = 0.09
    elif mismatch == "graph_vs_policy":
        inputs["candidate_graph"]["Mates"][0]["Distance"] = 0.09
    else:
        inputs["candidate_audit"]["positionParametersMeters"]["supportGap"] = 0.01
        inputs["candidate_graph"]["SupportPositionDemoPolicy"]["positionParametersMeters"]["supportGap"] = 0.01
    with pytest.raises(CrossProjectWasteCupDatumCatalogError, match="参数或能力边界"):
        build_wastecup_datum_catalog_package(**inputs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("directMechanicalCompatibilityClaim", True),
        ("actualFixationMethod", "verified"),
        ("holePatternMatchRequired", True),
    ],
)
def test_support_position_rejects_strengthened_mechanical_claims(field: str, value: object) -> None:
    inputs = _support_inputs()
    inputs["candidate_graph"]["SupportPositionDemoPolicy"][field] = value
    with pytest.raises(CrossProjectWasteCupDatumCatalogError, match="参数或能力边界"):
        build_wastecup_datum_catalog_package(**inputs)


def test_real_catalog_policy_comparison_builds_in_temp_root(tmp_path: Path) -> None:
    source = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
    for name in ("candidate_effective_mate_graph.json", "candidate_audit.json"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_cross_project_wastecup_datum_demo_catalog.py"),
            "--root",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert completed.returncode == 0, completed.stderr
    comparison = json.loads(
        (tmp_path / "semantic-package-v1/policy-compilation-comparison.json").read_text(
            encoding="utf-8"
        )
    )
    assert comparison["defaultDirectInstallation"]["status"] == "blocked"
    assert comparison["explicitDatumPlacementDemo"]["status"] == "ready"
    assert (
        comparison["explicitDatumPlacementDemo"]["manifestStatus"]
        == "ready_for_project_adapter"
    )
    graph = json.loads(
        (tmp_path / "semantic-package-v1/base_wastecup_datum_graph.json").read_text(
            encoding="utf-8"
        )
    )
    assert {row["ModuleToken"] for row in graph["Modules"]} == {"A600", "P000"}
    assert len(graph["Mates"]) == 3
    assert graph["CaseAnchor"] is None
    assert graph["TargetLeafPoseAnchors"] == []
    assert graph["BaseGraphPolicy"]["moduleTokens"] == ["A600"]
    assert graph["BaseGraphPolicy"]["executionGraphComplete"] is True


def _aa00_inputs() -> dict:
    """Synthetic AA00 endpoint labels test routing, not measured CAD geometry."""
    inputs = _support_inputs()

    def relabel(value: object) -> object:
        if isinstance(value, str):
            return value.replace("A600", "AA00").replace("a600", "aa00")
        if isinstance(value, list):
            return [relabel(item) for item in value]
        if isinstance(value, dict):
            return {key: relabel(item) for key, item in value.items()}
        return value

    inputs["candidate_graph"] = relabel(inputs["candidate_graph"])
    inputs["candidate_audit"] = relabel(inputs["candidate_audit"])
    inputs["candidate_audit"]["targetProjectId"] = "project03"
    inputs["context_endpoint_catalog"] = relabel(inputs.pop("a600_endpoint_catalog"))
    return inputs


def test_aa00_support_candidate_uses_context_project_and_isolated_identities() -> None:
    old = build_wastecup_datum_catalog_package(**_support_inputs())
    inputs = _aa00_inputs()
    before = copy.deepcopy(inputs)
    package = build_wastecup_datum_catalog_package(**inputs)
    assert inputs == before
    ports = package["semanticCatalog"]["ports"]
    assert ports[1]["moduleToken"] == "AA00"
    assert ports[1]["projectId"] == "project03"
    assert ports[1]["portId"].startswith("AA00.")
    assert ports[0]["portId"] != old["semanticCatalog"]["ports"][0]["portId"]
    assert set(package["globalPortIds"]).isdisjoint(old["globalPortIds"])
    assert package["globalTemplateId"].startswith("template/project-global/p000-aa00-")
    assert package["baseGraph"]["BaseGraphPolicy"]["moduleTokens"] == ["AA00"]
    assert package["baseGraph"]["EditPolicy"]["fixedModuleTokens"] == ["AA00"]
    template = package["semanticCatalog"]["connectionTemplates"][0]
    assert template["templateId"].startswith("P000_to_AA00_support_position_demo_v2_")
    assert [row["mateName"] for row in template["mateSteps"]] == [
        "P000_AA00_DATUM_DISTANCE_1", "P000_AA00_DATUM_DISTANCE_2", "P000_AA00_DATUM_SUPPORT"
    ]
    assert template["constraintEffect"]["cadValidationStatus"] == "not_yet_validated"
    assert all(port["validationStatus"] == "candidate-awaiting-nonprototype-cad-validation" for port in ports)
    assert template["constraintEffect"]["directMechanicalInterfaceCompatible"] is False


def test_aa00_alignment_is_from_graph_and_changes_recipe_identity() -> None:
    inputs = _aa00_inputs()
    original = build_wastecup_datum_catalog_package(**inputs)
    for mate, alignment, name in zip(
        inputs["candidate_graph"]["Mates"],
        (1, 1, 0),
        ("swMateAlignANTI_ALIGNED", "swMateAlignANTI_ALIGNED", "swMateAlignALIGNED"),
    ):
        mate["Alignment"] = alignment
        mate["AlignmentName"] = name
    edited = build_wastecup_datum_catalog_package(**inputs)
    steps = edited["semanticCatalog"]["connectionTemplates"][0]["mateSteps"]
    assert [step["alignment"] for step in steps] == [1, 1, 0]
    assert [step["alignmentName"] for step in steps] == [
        "swMateAlignANTI_ALIGNED", "swMateAlignANTI_ALIGNED", "swMateAlignALIGNED"
    ]
    assert edited["globalTemplateId"] != original["globalTemplateId"]
    global_template = next(
        row for row in edited["candidateGlobalCatalog"]["connectionTemplates"]
        if row["globalTemplateId"] == edited["globalTemplateId"]
    )
    assert global_template["mateSteps"] == steps


def test_aa00_position_parameters_have_distinct_template_identity() -> None:
    inputs = _aa00_inputs()
    original = build_wastecup_datum_catalog_package(**inputs)
    parameters = {"longitudinal": 0.12, "lateral": 0.25, "supportGap": 0}
    inputs["candidate_audit"]["positionParametersMeters"] = copy.deepcopy(parameters)
    inputs["candidate_graph"]["SupportPositionDemoPolicy"]["positionParametersMeters"] = parameters
    inputs["candidate_graph"]["Mates"][0]["Distance"] = 0.12
    inputs["candidate_graph"]["Mates"][1]["Distance"] = 0.25
    edited = build_wastecup_datum_catalog_package(**inputs)
    assert edited["globalTemplateId"] != original["globalTemplateId"]
    assert [step.get("distanceMeters") for step in edited["semanticCatalog"]["connectionTemplates"][0]["mateSteps"]] == [0.12, 0.25, None]


@pytest.mark.parametrize("alignment", [None, True, -1, 3, "1"])
def test_invalid_graph_alignment_is_rejected(alignment: object) -> None:
    inputs = _aa00_inputs()
    inputs["candidate_graph"]["Mates"][0]["Alignment"] = alignment
    with pytest.raises(CrossProjectWasteCupDatumCatalogError, match="对齐方向"):
        build_wastecup_datum_catalog_package(**inputs)


def test_inconsistent_alignment_name_is_rejected() -> None:
    inputs = _aa00_inputs()
    inputs["candidate_graph"]["Mates"][0]["AlignmentName"] = "swMateAlignANTI_ALIGNED"
    with pytest.raises(CrossProjectWasteCupDatumCatalogError, match="对齐方向"):
        build_wastecup_datum_catalog_package(**inputs)


def test_context_catalog_alias_is_backwards_compatible_but_not_ambiguous() -> None:
    inputs = _support_inputs()
    package = build_wastecup_datum_catalog_package(**inputs)
    renamed = copy.deepcopy(inputs)
    renamed["context_endpoint_catalog"] = renamed.pop("a600_endpoint_catalog")
    assert build_wastecup_datum_catalog_package(**renamed) == package
    renamed["a600_endpoint_catalog"] = {"Endpoints": []}
    with pytest.raises(CrossProjectWasteCupDatumCatalogError, match="不同内容"):
        build_wastecup_datum_catalog_package(**renamed)


def test_original_a600_support_template_identity_is_preserved() -> None:
    package = build_wastecup_datum_catalog_package(**_support_inputs())
    assert package["globalTemplateId"] == "template/project-global/p000-a600-wastecup-datum-demo/6620f1ab8a"


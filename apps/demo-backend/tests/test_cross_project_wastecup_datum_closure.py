from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from demo_backend.cross_project_wastecup_datum_closure import (
    CrossProjectWasteCupDatumClosureError,
    close_project05_p000_to_project02_a600_datum_demo,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    graph = tmp_path / "graph.json"
    output = tmp_path / "out.SLDASM"
    graph.write_text("{}", encoding="utf-8")
    output.write_bytes(b"assembly")
    audit = {
        "schemaVersion": "cross-project-wastecup-datum-candidate/v1",
        "cadLaunchAllowed": True,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
    }
    result = {
        "schemaVersion": "checkpoint-selected-face-context-insert-run/v1",
        "success": True,
        "durationSeconds": 10.0,
        "effectiveGraphSha256": _sha(graph),
        "outputAssemblySha256": _sha(output),
        "sourceAssemblyUnchanged": True,
        "outputClosedAfterVerification": True,
        "toolResult": {
            "Success": True,
            "IndependentComponentInserted": True,
            "TargetCaseAnchored": False,
            "RequestedTargetLeafPoseAnchorCount": 0,
            "AppliedTargetLeafPoseAnchorCount": 0,
            "RequestedMateCount": 3,
            "CreatedMateCount": 3,
            "TargetFullyConstrained": True,
            "TargetConstraintStateAccepted": True,
            "MateSolveClean": True,
            "ComponentSemanticsMatch": True,
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "Diagnostics": ["inserted target at a deterministic non-source pose"],
            "PhaseDurationsSeconds": {"total": 8.0},
            "MateResults": [
                {
                    "Success": True,
                    "ErrorName": "swAddMateError_NoError",
                    "EndpointResolutionStrategies": [
                        "endpoint#0: BodyFaceIndex",
                        "endpoint#1: SourceAssemblyPersistentReference",
                    ],
                }
                for _ in range(3)
            ],
            "MateVerifications": [
                {
                    "Found": True,
                    "TypeMatches": True,
                    "AlignmentMatches": True,
                    "DistanceMatches": True,
                    "AngleMatches": True,
                    "AdvancedOptionsMatch": True,
                }
                for _ in range(3)
            ],
        },
    }
    return audit, result, graph, output


def test_closure_passes_and_keeps_direct_interface_claim_false(tmp_path: Path) -> None:
    audit, result, graph, output = _fixture(tmp_path)
    value = close_project05_p000_to_project02_a600_datum_demo(
        candidate_audit=audit,
        cad_result=result,
        effective_graph_path=graph,
        output_assembly_path=output,
    )
    assert value["success"] is True
    assert value["semanticDatumPlacementPassed"] is True
    assert value["releaseEligibleForDatumPlacementDemo"] is True
    assert value["releaseEligibleForDirectMechanicalSubstitution"] is False
    assert value["endpointRecovery"]["portableAcrossTopologyEdits"] is False


def test_closure_fails_when_leaf_anchor_was_used(tmp_path: Path) -> None:
    audit, result, graph, output = _fixture(tmp_path)
    result["toolResult"]["AppliedTargetLeafPoseAnchorCount"] = 1
    with pytest.raises(CrossProjectWasteCupDatumClosureError, match="noCaseOrLeafPoseAnchors"):
        close_project05_p000_to_project02_a600_datum_demo(
            candidate_audit=audit,
            cad_result=result,
            effective_graph_path=graph,
            output_assembly_path=output,
        )


def _support_fixture(tmp_path: Path) -> tuple[dict, dict, Path, Path, dict]:
    audit, result, graph, output = _fixture(tmp_path)
    audit.update(
        {
            "mode": "support_position_demo",
            "holePatternMatchRequired": False,
            "actualFixationMethod": "not_verified",
            "directMechanicalCompatibilityClaim": False,
            "positionParametersMeters": {
                "longitudinal": 0.08,
                "lateral": 0.39,
                "supportGap": 0,
            },
            "parameterAuthority": "explicit_demo_design_parameters_not_vendor_mounting_dimensions",
        }
    )
    names = [
        "MCP_GRAPH_P000_A600_DATUM_DISTANCE_1",
        "MCP_GRAPH_P000_A600_DATUM_DISTANCE_2",
        "MCP_GRAPH_P000_A600_DATUM_SUPPORT",
    ]
    for verification, name in zip(result["toolResult"]["MateVerifications"], names):
        verification["ExpectedMateName"] = name
    result["toolResult"]["ExternalPlacementEquivalencePassed"] = False
    state = {
        "success": True,
        "assemblySha256": _sha(output),
        "observed": {
            "readOnly": True,
            "components": [
                {"name": "FL9A24D062A600.001-1", "isFixed": True},
                {"name": "FL9C254098P000.001-1", "isFixed": False},
            ],
            "mates": [
                {"name": name, "isSuppressed": False, "errorCode": 0}
                for name in names
            ],
        },
    }
    return audit, result, graph, output, state


def test_support_demo_requires_bound_real_state_but_does_not_claim_fixation(tmp_path: Path) -> None:
    audit, result, graph, output, state = _support_fixture(tmp_path)
    value = close_project05_p000_to_project02_a600_datum_demo(
        candidate_audit=audit,
        cad_result=result,
        effective_graph_path=graph,
        output_assembly_path=output,
        read_only_state=state,
    )

    assert value["success"] is True
    assert value["status"] == "PASSED_SUPPORT_POSITION_DEMO"
    assert value["holePatternMatchRequired"] is False
    assert value["actualFixationMethod"] == "not_verified"
    assert value["actualFixationNotice"] == "实际固定方式暂未验证"
    assert value["releaseEligibleForDirectMechanicalSubstitution"] is False
    assert value["directMechanicalInterfaceCompatible"] == "not_evaluated"
    assert value["readOnlyStateVerification"] == state
    assert value["positionParametersMeters"] == audit["positionParametersMeters"]
    assert value["legacyExternalPlacementWitness"]["passed"] is False
    assert value["legacyExternalPlacementWitness"]["acceptanceCriterion"] is False
    assert value["checks"]["onlyBaseFixedTargetLocatedByMates"] is True
    assert value["checks"]["threeNamedMatesActiveAfterReopen"] is True


def test_support_demo_rejects_missing_state(tmp_path: Path) -> None:
    audit, result, graph, output, _ = _support_fixture(tmp_path)
    with pytest.raises(CrossProjectWasteCupDatumClosureError, match="readOnlyStateBoundToOutput"):
        close_project05_p000_to_project02_a600_datum_demo(
            candidate_audit=audit,
            cad_result=result,
            effective_graph_path=graph,
            output_assembly_path=output,
        )


def test_support_demo_aa00_requires_explicit_matching_base_identity(tmp_path: Path) -> None:
    audit, result, graph, output, state = _support_fixture(tmp_path)
    audit.update(targetBaseToken="AA00", targetProjectId="project03")
    state["observed"]["components"][0]["name"] = "FL9A24D063AA00.001-1"
    for row in result["toolResult"]["MateVerifications"]:
        row["ExpectedMateName"] = row["ExpectedMateName"].replace("A600", "AA00")
    for row in state["observed"]["mates"]:
        row["name"] = row["name"].replace("A600", "AA00")
    kwargs = dict(candidate_audit=audit, cad_result=result, effective_graph_path=graph,
                  output_assembly_path=output, read_only_state=state)
    with pytest.raises(CrossProjectWasteCupDatumClosureError, match="targetBaseIdentityMatches"):
        close_project05_p000_to_project02_a600_datum_demo(**kwargs)
    value = close_project05_p000_to_project02_a600_datum_demo(
        **kwargs, target_base_token="AA00", target_project_id="project03",
        expected_context_module_tokens=("AA00",),
    )
    assert value["success"] is True
    assert value["targetBaseToken"] == "AA00"
    assert value["targetProjectId"] == "project03"


@pytest.mark.parametrize(
    ("defect", "failed_check"),
    [
        ("target_fixed", "onlyBaseFixedTargetLocatedByMates"),
        ("base_unfixed", "onlyBaseFixedTargetLocatedByMates"),
        ("extra_component", "onlyBaseFixedTargetLocatedByMates"),
        ("suppressed_mate", "threeNamedMatesActiveAfterReopen"),
        ("mate_error", "threeNamedMatesActiveAfterReopen"),
        ("wrong_mate_name", "threeNamedMatesActiveAfterReopen"),
        ("missing_mate", "threeNamedMatesActiveAfterReopen"),
        ("wrong_state_sha", "readOnlyStateBoundToOutput"),
        ("wrong_cad_sha", "outputDigestMatchesCadRun"),
        ("not_read_only", "readOnlyStateBoundToOutput"),
    ],
)
def test_support_demo_rejects_unbound_or_invalid_observed_state(tmp_path: Path, defect: str, failed_check: str) -> None:
    audit, result, graph, output, state = _support_fixture(tmp_path)
    observed = state["observed"]
    if defect == "target_fixed":
        observed["components"][1]["isFixed"] = True
    elif defect == "base_unfixed":
        observed["components"][0]["isFixed"] = False
    elif defect == "extra_component":
        observed["components"].append({"name": "EXTRA.001-1", "isFixed": False})
    elif defect == "suppressed_mate":
        observed["mates"][0]["isSuppressed"] = True
    elif defect == "mate_error":
        observed["mates"][0]["errorCode"] = 1
    elif defect == "wrong_mate_name":
        observed["mates"][0]["name"] = "ANOTHER_MATE"
    elif defect == "missing_mate":
        observed["mates"].pop()
    elif defect == "wrong_state_sha":
        state["assemblySha256"] = "0" * 64
    elif defect == "wrong_cad_sha":
        result["outputAssemblySha256"] = "0" * 64
    elif defect == "not_read_only":
        observed["readOnly"] = False

    with pytest.raises(CrossProjectWasteCupDatumClosureError, match=failed_check):
        close_project05_p000_to_project02_a600_datum_demo(
            candidate_audit=audit,
            cad_result=result,
            effective_graph_path=graph,
            output_assembly_path=output,
            read_only_state=state,
        )

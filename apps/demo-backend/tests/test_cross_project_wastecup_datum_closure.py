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

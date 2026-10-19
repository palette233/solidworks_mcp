import pytest

from demo_backend.mate_transaction_preflight import (
    MateTransactionPreflightError,
    preflight_direct_mate_transaction,
)


def endpoint(index, token, normal, center):
    return {
        "Index": index,
        "ModuleToken": token,
        "GeometryType": "Face",
        "FaceNormalWorld": normal,
        "FaceCenterWorld": center,
    }


def effective_graph(normals):
    mates = []
    operations = []
    for index, normal in enumerate(normals):
        name = f"plane-{index}"
        mates.append({
            "MateName": name,
            "MateType": 0,
            "ModuleTokens": ["A700", "A600"],
            "IsSuppressed": False,
            "Endpoints": [
                endpoint(0, "A700", normal, [0.1 * index, 0.2 * index, 0.3 * index]),
                endpoint(1, "A600", [-value for value in normal], [0, 0, 0]),
            ],
        })
        operations.append({"index": index, "operation": "addMate", "mateName": name})
    return {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": mates,
        "PatchAudit": {"operations": operations},
    }


def test_three_independent_mates_are_ready_for_closed_batch():
    result = preflight_direct_mate_transaction(
        effective_graph([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
        "A700",
        require_closed_dof=True,
        require_multiple_operations=True,
    )

    assert result["status"] == "ready_for_cad_execution"
    assert result["publishAllowed"] is True
    assert result["operationCount"] == 3
    assert result["rigidBodyDofAnalysis"]["residualDof"] == 0


def test_residual_dof_blocks_required_closure():
    result = preflight_direct_mate_transaction(
        effective_graph([[0, 1, 0]]), "A700", require_closed_dof=True
    )

    assert result["status"] == "blocked"
    assert result["publishAllowed"] is False
    assert result["blockers"][0]["code"] == "RESIDUAL_DOF"


def test_unrelated_active_mate_is_rejected():
    graph = effective_graph([[0, 1, 0], [1, 0, 0]])
    graph["Modules"].append({"ModuleToken": "A500"})
    graph["Mates"].append({
        "MateName": "unrelated",
        "MateType": 0,
        "ModuleTokens": ["A500", "A600"],
        "IsSuppressed": False,
        "Endpoints": [
            endpoint(0, "A500", [0, 1, 0], [0, 0, 0]),
            endpoint(1, "A600", [0, -1, 0], [0, 0, 0]),
        ],
    })

    with pytest.raises(MateTransactionPreflightError, match="unrelated active mates"):
        preflight_direct_mate_transaction(graph, "A700")


def test_legacy_graph_without_patch_audit_is_rejected():
    graph = effective_graph([[0, 1, 0], [1, 0, 0]])
    graph.pop("PatchAudit")

    with pytest.raises(MateTransactionPreflightError, match="requires PatchAudit"):
        preflight_direct_mate_transaction(graph, "A700")


def test_strict_driving_preflight_rejects_redundant_mutating_relation():
    graph = effective_graph([[0, 1, 0], [0, 1, 0]])

    result = preflight_direct_mate_transaction(
        graph,
        "A700",
        reject_redundant_mutations=True,
    )

    assert result["status"] == "blocked"
    assert result["publishAllowed"] is False
    assert result["drivingDecision"] == "blocked_before_cad"
    assert result["redundantMutatingMateNames"] == ["plane-1"]
    assert "REDUNDANT_MUTATING_RELATION" in {
        row["code"] for row in result["blockers"]
    }


def test_non_strict_audit_reports_redundancy_without_changing_legacy_gate():
    result = preflight_direct_mate_transaction(
        effective_graph([[0, 1, 0], [0, 1, 0]]),
        "A700",
    )

    assert result["status"] == "ready_for_cad_execution"
    assert result["publishAllowed"] is True
    assert result["drivingDecision"] == "verification_only_redundant_relation"

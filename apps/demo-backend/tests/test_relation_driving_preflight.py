from __future__ import annotations

import json

from demo_backend import global_assembly_workbench
from demo_backend.relation_driving_preflight import (
    classify_relation_driving_preflight,
)


def _verification_preview(*, drives_placement: bool = False):
    return {
        "status": "ready_for_endpoint_selection",
        "matchingTemplates": [
            {
                "globalTemplateId": "template/test/relation",
                "templateProfile": {
                    "globalTemplateId": "template/test/relation",
                    "drivesPlacement": drives_placement,
                },
            }
        ],
    }


def _transaction(*, blockers=None, decision="candidate_for_driving_cad_trial"):
    return {
        "status": "ready_for_cad_execution" if not blockers else "blocked",
        "publishAllowed": not blockers,
        "drivingDecision": decision,
        "blockers": list(blockers or []),
    }


def _release(*, driving: bool):
    return {
        "releaseId": "relation-test",
        "releaseDigest": "a" * 64,
        "scope": {
            "drivingRelationRelease": driving,
            "authorizedDrivingTemplateIds": (
                ["template/test/relation"] if driving else []
            ),
        },
    }


def test_validation_only_release_keeps_mechanically_valid_drive_as_verification_only():
    result = classify_relation_driving_preflight(
        requirement="让两个孔同轴",
        released_verification_preview=_verification_preview(drives_placement=False),
        transaction_preflight=_transaction(),
        release=_release(driving=False),
    )

    assert result["decisionCategory"] == "verification_only"
    assert result["cadExecutionAllowed"] is False
    assert result["reasonCodes"] == ["RELEASED_TEMPLATE_IS_VALIDATION_ONLY"]


def test_redundant_mutating_relation_is_downgraded_to_verification_only():
    result = classify_relation_driving_preflight(
        requirement="新增一个重合配合",
        released_verification_preview=_verification_preview(drives_placement=True),
        transaction_preflight=_transaction(
            blockers=[{"code": "REDUNDANT_MUTATING_RELATION"}],
            decision="blocked_before_cad",
        ),
        release=_release(driving=True),
    )

    assert result["decisionCategory"] == "verification_only"
    assert result["cadExecutionAllowed"] is False
    assert result["reasonCodes"] == [
        "PROPOSED_RELATION_ADDS_NO_INDEPENDENT_DOF_CONSTRAINT"
    ]


def test_supported_nonredundant_driving_release_can_enter_cad_trial():
    result = classify_relation_driving_preflight(
        requirement="新增一个同轴配合",
        released_verification_preview=_verification_preview(drives_placement=True),
        transaction_preflight=_transaction(),
        release=_release(driving=True),
    )

    assert result["decisionCategory"] == "ready_for_driving_cad_trial"
    assert result["cadExecutionAllowed"] is True


def test_unsupported_geometry_blocks_before_cad():
    result = classify_relation_driving_preflight(
        requirement="新增一个槽口配合",
        released_verification_preview=_verification_preview(drives_placement=True),
        transaction_preflight=_transaction(
            blockers=[{"code": "UNSUPPORTED_DOF_RELATION"}],
            decision="blocked_before_cad",
        ),
        release=_release(driving=True),
    )

    assert result["decisionCategory"] == "blocked"
    assert result["cadExecutionAllowed"] is False
    assert result["reasonCodes"] == ["UNSUPPORTED_DOF_RELATION"]


def test_workbench_preflight_joins_graph_and_released_semantics(tmp_path, monkeypatch):
    graph_path = tmp_path / "effective.json"
    graph_path.write_text(json.dumps({"fixture": True}), encoding="utf-8")
    monkeypatch.setattr(
        global_assembly_workbench,
        "preflight_direct_mate_transaction",
        lambda *args, **kwargs: _transaction(),
    )
    monkeypatch.setattr(
        global_assembly_workbench,
        "preview_released_relation_intent",
        lambda *args, **kwargs: _verification_preview(drives_placement=False),
    )
    monkeypatch.setattr(
        global_assembly_workbench,
        "describe_released_relation_catalog",
        lambda *args, **kwargs: _release(driving=False),
    )

    result = global_assembly_workbench.preflight_released_driving_relation(
        tmp_path,
        {
            "requirement": "让两个孔同轴",
            "effectiveGraphPath": "effective.json",
            "targetModuleToken": "GN00",
        },
    )

    assert result["decisionCategory"] == "verification_only"
    assert result["targetModuleToken"] == "GN00"
    assert len(result["preflightDigest"]) == 64

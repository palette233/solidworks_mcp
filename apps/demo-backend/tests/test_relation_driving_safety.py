import json
from pathlib import Path

import pytest

from demo_backend.relation_driving_safety import (
    assess_relation_driving_safety,
    relation_driving_safety_registry_binding,
)


TEMPLATE = "template/project02/a700-to-a600-nonanchor-driving-v1/32804d30f3"
WORKSPACE = Path(__file__).resolve().parents[3]


def _registry(status="blocked_external_pose_branch"):
    return {
        "schemaVersion": "relation-driving-safety-registry/v1",
        "registryId": "test",
        "templates": [
            {
                "globalTemplateId": TEMPLATE,
                "moduleToken": "A700",
                "status": status,
                "reason": "external placement is not equivalent",
                "recommendedFallback": {"strategyId": "fallback-v1"},
            }
        ],
    }


def test_blocked_template_requires_external_pose_equivalence():
    result = assess_relation_driving_safety(TEMPLATE, registry=_registry())

    assert result["status"] == "blocked_external_pose_branch"
    assert result["blockers"][0]["code"] == (
        "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
    )
    assert result["blockers"][0]["recommendedFallback"] == {
        "strategyId": "fallback-v1"
    }


def test_verified_template_is_accepted_and_binding_is_stable():
    registry = _registry("verified_external_pose_equivalent")

    assert not assess_relation_driving_safety(TEMPLATE, registry=registry)["blockers"]
    assert relation_driving_safety_registry_binding(registry)["registryDigest"]


def test_blocked_template_accepts_only_explicit_confirmed_calibrated_fallback():
    registry = _registry()
    registry["templates"][0]["recommendedFallback"] = {
        "strategyId": "fallback-v1",
        "scope": "project02-only",
        "effectiveMateGraphPath": "graph.json",
        "effectiveMateGraphSha256": "a" * 64,
        "validationEvidencePath": "validation.json",
        "validationEvidenceSha256": "b" * 64,
        "automaticSelectionAllowed": False,
    }

    result = assess_relation_driving_safety(
        TEMPLATE,
        registry=registry,
        explicit_selection={"strategyId": "fallback-v1", "confirmed": True},
    )

    assert result["status"] == "explicit_calibrated_fallback_selected"
    assert not result["blockers"]
    assert result["executionOverride"]["portable"] is False
    assert result["executionOverride"]["executionStrategy"] == (
        "calibrated_static_snapshot_insert"
    )


def test_calibrated_fallback_never_activates_without_confirmation():
    registry = _registry()
    registry["templates"][0]["recommendedFallback"].update(
        {
            "scope": "project02-only",
            "effectiveMateGraphPath": "graph.json",
            "effectiveMateGraphSha256": "a" * 64,
            "validationEvidencePath": "validation.json",
            "validationEvidenceSha256": "b" * 64,
        }
    )

    result = assess_relation_driving_safety(
        TEMPLATE,
        registry=registry,
        explicit_selection={"strategyId": "fallback-v1", "confirmed": False},
    )

    assert result["blockers"][0]["code"] == (
        "DRIVING_FALLBACK_EXPLICIT_CONFIRMATION_REQUIRED"
    )


@pytest.mark.parametrize(
    "template_id",
    [
        "template/project02/a700-to-a600-nonanchor-driving-v1/b707e436d3",
        "template/project02/a700-to-a600-nonanchor-driving-v1/32804d30f3",
        "template/project02/a700-to-a600-nonanchor-driving-v1/e2865a6c0f",
        "template/project02/a700-to-a600-nonanchor-driving-v1/71a7cf02a6",
    ],
)
def test_all_released_a700_template_variants_are_revoked(template_id):
    registry = json.loads(
        (
            WORKSPACE
            / "demo/global_assembly_catalog/relation-driving-safety-v1.json"
        ).read_text(encoding="utf-8")
    )

    result = assess_relation_driving_safety(template_id, registry=registry)

    assert result["status"] == "blocked_external_pose_branch"
    assert result["blockers"][0]["code"] == (
        "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
    )


def test_g000_free_slot_release_is_revoked_after_current_closure_failure():
    registry = json.loads(
        (
            WORKSPACE
            / "demo/global_assembly_catalog/relation-driving-safety-v1.json"
        ).read_text(encoding="utf-8")
    )
    template_id = "template/project05/g000-to-a000-static-four-relation-v2/f738bc665b"

    result = assess_relation_driving_safety(template_id, registry=registry)

    assert result["status"] == "blocked_external_pose_branch"
    assert result["blockers"][0]["code"] == (
        "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
    )
    assert "欠约束" in result["reason"]

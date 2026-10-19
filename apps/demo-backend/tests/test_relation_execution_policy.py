from __future__ import annotations

import pytest

from demo_backend.relation_execution_policy import (
    RelationExecutionPolicyError,
    assess_template_execution_policy,
    filter_connection_candidates_by_execution_policy,
)


def _catalog() -> dict:
    return {
        "connectionTemplates": [
            {
                "globalTemplateId": "template/direct",
                "purposes": ["installation"],
            },
            {
                "globalTemplateId": "template/datum-demo",
                "purposes": ["installation", "datum_placement_demo"],
            },
        ]
    }


def test_default_mode_only_allows_direct_installation() -> None:
    candidates = [
        {"globalTemplateId": "template/direct"},
        {"globalTemplateId": "template/datum-demo"},
    ]
    allowed, audit = filter_connection_candidates_by_execution_policy(
        _catalog(), candidates
    )
    assert [row["globalTemplateId"] for row in allowed] == ["template/direct"]
    rejected = next(
        row for row in audit if row["globalTemplateId"] == "template/datum-demo"
    )
    assert rejected["executionPolicyAssessment"]["allowed"] is False


def test_explicit_datum_mode_only_allows_datum_demo() -> None:
    candidates = [
        {"globalTemplateId": "template/direct"},
        {"globalTemplateId": "template/datum-demo"},
    ]
    allowed, _ = filter_connection_candidates_by_execution_policy(
        _catalog(), candidates, requested_mode="datum_placement_demo"
    )
    assert [row["globalTemplateId"] for row in allowed] == [
        "template/datum-demo"
    ]


def test_unknown_mode_fails_closed() -> None:
    with pytest.raises(RelationExecutionPolicyError):
        assess_template_execution_policy(
            {"purposes": ["installation"]}, requested_mode="prototype_pose"
        )


from demo_backend.relation_validation_preconditions import (
    assess_relation_validation_precondition,
    relation_validation_precondition_registry_binding,
)


TEMPLATE = "template/project02/a500-to-a700-source-spacing/ca450b2dcd"


def _registry(dependency_kind="external_placement_equivalence"):
    return {
        "schemaVersion": "relation-validation-precondition-registry/v1",
        "registryId": "test-registry",
        "requirements": [
            {
                "globalTemplateId": TEMPLATE,
                "requiredEvidenceId": "project02/a700/external-placement-equivalence",
                "dependencyKind": dependency_kind,
                "reason": "external pose must be equivalent",
            }
        ],
    }


def test_validation_is_blocked_without_external_pose_evidence():
    result = assess_relation_validation_precondition(TEMPLATE, registry=_registry())

    assert result["status"] == "evidence_required"
    assert result["blockers"][0]["code"] == (
        "VALIDATION_EXTERNAL_PLACEMENT_EQUIVALENCE_REQUIRED"
    )


def test_validation_accepts_digest_bound_external_pose_evidence():
    result = assess_relation_validation_precondition(
        TEMPLATE,
        registry=_registry(),
        state_evidence=[
            {
                "evidenceId": "project02/a700/external-placement-equivalence",
                "appliedToCurrentCheckpoint": True,
                "evidenceDigest": "abc123",
            }
        ],
    )

    assert result["status"] == "satisfied"
    assert result["blockers"] == []


def test_unregistered_validation_remains_usable():
    result = assess_relation_validation_precondition(
        "template/project01/unrelated", registry=_registry()
    )

    assert result["status"] == "not_declared"
    assert result["required"] is False


def test_registry_binding_is_deterministic():
    first = relation_validation_precondition_registry_binding(_registry())
    second = relation_validation_precondition_registry_binding(_registry())

    assert first == second
    assert len(first["registryDigest"]) == 64

from __future__ import annotations

from demo_backend.prototype_dependency_audit import audit_project_profile_dependencies


def test_project02_dependency_audit_preserves_static_and_production_boundary() -> None:
    audit = audit_project_profile_dependencies("project02")

    assert audit["staticDemoProfileAccepted"] is True
    assert audit["productionProfileAccepted"] is False
    assert audit["prototypeDependentModuleCount"] == 7
    assert audit["productionAuthorityAcceptedModuleCount"] == 0
    assert audit["countsBySourceConfidence"] == {
        "inferred-from-prototype": 7,
        "measured-from-cad": 2,
    }
    assert audit["parameterAuthorityAudit"]["requirementCount"] == 9
    assert audit["parameterAuthorityAudit"]["productionAcceptedRequirementCount"] == 0
    assert audit["parameterAuthorityAudit"]["staticDemoParameterEvidenceAccepted"] is True
    assert audit["parameterAuthorityAudit"]["productionParameterAuthorityAccepted"] is False
    assert {row["moduleToken"] for row in audit["productionBlockers"]} == {
        "A600",
        "A800",
        "A180",
        "A700",
        "A300",
        "A500",
        "A100",
        "A200",
        "T401",
    }

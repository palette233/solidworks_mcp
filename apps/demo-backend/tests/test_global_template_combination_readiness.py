import json
from pathlib import Path

from demo_backend.global_template_combination_readiness import (
    assess_template_combination_readiness,
)


ROOT = Path(__file__).resolve().parents[3]


def _catalog():
    return json.loads(
        (
            ROOT
            / "demo/global_assembly_catalog/v1/"
            "global_module_catalog.combination-v1-preview.json"
        ).read_text(encoding="utf-8-sig")
    )


def test_project03_audit_keeps_atomic_closure_and_missing_combination_distinct():
    report = assess_template_combination_readiness(
        _catalog(),
        project_id="project03",
    )
    ae00 = next(
        row
        for row in report["templates"]
        if row["legacyTemplateId"] == "AE00_to_AA00_three_datum_installation"
    )
    ag00_diagnostic = next(
        row
        for row in report["templates"]
        if row["globalTemplateId"].endswith("/9c4d9b9fb1")
    )

    assert ae00["state"] == "declared_atomic_closed"
    assert ae00["blockers"] == []
    assert ag00_diagnostic["state"] == "requires_semantic_completion"
    assert {
        row["code"] for row in ag00_diagnostic["blockers"]
    } == {"SUPPLEMENTAL_RELATION_OR_COMBINATION_MISSING"}
    assert report["policy"]["prototypeTopLevelPoseMayCloseResidualDof"] is False


def test_project03_anchor_dependent_declarations_are_not_treated_as_portable_closure():
    report = assess_template_combination_readiness(
        _catalog(),
        project_id="project03",
    )
    ab00 = [
        row
        for row in report["templates"]
        if row["legacyTemplateId"] == "AB00_to_AA00_partial_anchored_installation"
    ]

    assert ab00
    assert all(row["state"] == "requires_semantic_completion" for row in ab00)
    assert all(
        "PROTOTYPE_OR_ANCHOR_DEPENDENCY_DECLARED"
        in {blocker["code"] for blocker in row["blockers"]}
        for row in ab00
    )


def test_project03_anchor_marker_in_legacy_id_is_not_missed():
    report = assess_template_combination_readiness(
        _catalog(),
        project_id="project03",
    )
    ac00 = next(
        row
        for row in report["templates"]
        if row["legacyTemplateId"]
        == "AC00_to_AB00_three_relation_anchored_installation"
    )

    assert ac00["state"] == "requires_semantic_completion"
    assert "PROTOTYPE_OR_ANCHOR_DEPENDENCY_DECLARED" in {
        blocker["code"] for blocker in ac00["blockers"]
    }

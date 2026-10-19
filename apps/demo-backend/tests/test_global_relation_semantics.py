import json
from pathlib import Path

import pytest

from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_assembly_transactions import (
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_module_catalog import build_global_module_catalog
from demo_backend.global_relation_semantics import (
    assess_template_for_relation_intent,
    build_relation_capability_matrix,
    normalize_template_relation_profile,
    parse_relation_intent,
    validate_relation_capability_matrix,
)


WORKSPACE = Path(__file__).resolve().parents[3]
CATALOG_PATH = (
    WORKSPACE / "demo/global_assembly_catalog/v1/global_module_catalog.json"
)


@pytest.fixture(scope="module")
def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def definition(catalog, project_id, token):
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == project_id and alias["moduleToken"] == token
            for alias in row["projectAliases"]
        )
    )


def context_with_base(catalog, project_id, token):
    row = definition(catalog, project_id, token)
    context = create_global_assembly_context(
        f"relation-{project_id}-{token}", catalog_digest=catalog["catalogDigest"]
    )
    preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": f"安装{project_id} {token}",
            "moduleDefinitionId": row["moduleDefinitionId"],
        },
    )
    assert preview["status"] == "ready", preview
    return apply_global_command_preview(
        context,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )


@pytest.mark.parametrize(
    ("text", "primary", "parameter_key", "parameter_value"),
    [
        ("将扫描模组安装到箱体上", "installation", None, None),
        ("让两个安装面重合", "coincident", None, None),
        ("让两个孔同轴", "concentric", None, None),
        ("令两个基准面平行", "parallel", None, None),
        ("令两个基准面垂直", "perpendicular", None, None),
        ("保持50mm间距", "spacing", "distanceMeters", 0.05),
        ("两个平面夹角30度", "angle", "angleDegrees", 30.0),
        ("将模组在槽内居中", "centered", None, None),
        ("将清洁模组放在操作面侧", "side_placement", "sideQualifier", "operator_side"),
    ],
)
def test_relation_intent_normalizes_supported_language(
    text, primary, parameter_key, parameter_value
):
    result = parse_relation_intent(text)
    assert result["status"] == "parsed"
    assert result["primaryRelation"] == primary
    if parameter_key:
        assert result["parameters"][parameter_key] == pytest.approx(parameter_value)


def test_generic_alignment_and_multiple_values_fail_closed():
    alignment = parse_relation_intent("把两个模组对齐")
    multiple = parse_relation_intent("保持50mm或60mm间距")

    assert alignment["status"] == "blocked"
    assert alignment["blockers"][0]["code"] == "ALIGNMENT_KIND_REQUIRED"
    assert multiple["status"] == "blocked"
    assert multiple["blockers"][0]["code"] == "MULTIPLE_DISTANCE_VALUES"


def test_non_operator_side_is_not_double_counted_as_operator_side():
    result = parse_relation_intent("将功能模组放到非操作面侧")
    assert result["status"] == "parsed"
    assert result["parameters"]["sideQualifier"] == "opposite_operator_side"


def test_project_number_and_module_token_are_not_misread_as_meters():
    result = parse_relation_intent("在A000上安装项目05 M000产品定位CCD模组")
    assert result["primaryRelation"] == "installation"
    assert result["parameters"]["distanceMeters"] is None


def test_installation_target_slot_is_a_catalog_port_not_a_slot_mate_request():
    result = parse_relation_intent(
        "Install Project01 SS00 transport module onto the Project03 AA00 transport slot."
    )

    assert result["primaryRelation"] == "installation"
    assert result["requestedRelationKinds"] == ["installation"]


def test_explicit_pin_in_slot_still_requests_slot_geometry():
    result = parse_relation_intent("Install the pin in slot using a slot mate.")

    assert result["primaryRelation"] == "installation"
    assert result["requestedRelationKinds"] == ["installation", "slot"]


def test_compound_installation_is_not_reused_as_standalone_concentric(catalog):
    context = context_with_base(catalog, "project05", "A000")
    f000 = definition(catalog, "project05", "F000")

    installation = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "在项目05 A000上安装F000扫描模组",
            "moduleDefinitionId": f000["moduleDefinitionId"],
        },
    )
    standalone = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "只让项目05 F000与A000同轴",
            "moduleDefinitionId": f000["moduleDefinitionId"],
        },
    )

    assert installation["status"] == "ready"
    assert installation["proposedPatch"]["connection"]["relationProfile"][
        "compoundInstallation"
    ] is True
    assert standalone["status"] == "blocked"
    assert standalone["blockers"][-1]["code"] == "REQUESTED_RELATION_TEMPLATE_NOT_AVAILABLE"
    reason_codes = {
        reason["code"]
        for item in standalone["relationCandidateAssessments"]
        for reason in item["relationAssessment"]["reasons"]
    }
    assert "STANDALONE_RELATION_TEMPLATE_REQUIRED" in reason_codes


def test_spacing_is_not_ready_when_signed_catalog_has_only_validation_or_nonportable_choices(catalog):
    context = context_with_base(catalog, "project02", "A500")
    a700 = definition(catalog, "project02", "A700")
    preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "将项目02 A700与A500保持50mm间距",
            "moduleDefinitionId": a700["moduleDefinitionId"],
        },
    )

    assert preview["status"] == "needs_confirmation"
    reasons = {
        reason["code"]
        for item in preview["relationCandidateAssessments"]
        for reason in item["relationAssessment"]["reasons"]
    }
    assert "VALIDATION_ONLY_RELATION_CANNOT_DRIVE_PLACEMENT" in reasons
    assert "PORT_EVIDENCE_NOT_PORTABLE" in {
        blocker["code"] for blocker in preview["blockers"]
    }


def test_unregistered_distance_override_fails_closed(catalog):
    context = context_with_base(catalog, "project02", "A500")
    a700 = definition(catalog, "project02", "A700")
    preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "将项目02 A700与A500保持60mm间距",
            "moduleDefinitionId": a700["moduleDefinitionId"],
        },
    )
    reason_codes = {
        reason["code"]
        for item in preview["relationCandidateAssessments"]
        for reason in item["relationAssessment"]["reasons"]
    }
    assert preview["status"] == "blocked"
    assert "REQUESTED_DISTANCE_NOT_SUPPORTED_BY_TEMPLATE" in reason_codes


def test_template_profile_explains_dof_and_driving_vs_validation(catalog):
    partial = next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"] == "AG00_to_AA00_partial_installation"
        and (row.get("constraintEffect") or {}).get("expectedResidualDof") == 1
    )
    spacing = next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"] == "A500_to_A700_source_spacing"
    )

    partial_profile = normalize_template_relation_profile(partial)
    spacing_profile = normalize_template_relation_profile(spacing)

    assert partial_profile["constraintExplanation"]["state"] == "declared_underconstrained"
    assert partial_profile["constraintExplanation"]["expectedResidualDof"] == 1
    assert spacing_profile["drivingMateStepCount"] == 0
    assert spacing_profile["validationMateStepCount"] == 1
    assert spacing_profile["drivesPlacement"] is False


def test_capability_matrix_and_direct_template_assessment(catalog):
    matrix = build_relation_capability_matrix(catalog)
    spacing = next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"] == "A500_to_A700_source_spacing"
    )
    assessment = assess_template_for_relation_intent(
        spacing, parse_relation_intent("保持50mm间距")
    )

    assert matrix["summary"]["templateCount"] == len(catalog["connectionTemplates"])
    assert validate_relation_capability_matrix(matrix, catalog=catalog)["success"] is True
    assert matrix["genericRelationDefinitions"]["concentric"][
        "requiredEndpointGeometry"
    ] == ["cylinder-cylinder", "axis-axis"]
    assert matrix["genericRelationDefinitions"]["distance"][
        "dofEstimateAuthority"
    ].startswith("non_authoritative")
    assert matrix["summary"]["compoundInstallationTemplateCount"] > 0
    assert matrix["summary"][
        "portablePlacementCapableStandaloneRelationTemplateCount"
    ] == 0
    assert assessment["compatible"] is False
    assert assessment["reasons"][-1]["code"] == "VALIDATION_ONLY_RELATION_CANNOT_DRIVE_PLACEMENT"


def test_refreshed_endpoint_evidence_allows_relation_selection_but_dof_gate_still_blocks():
    refreshed = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    context = context_with_base(refreshed, "project02", "A500")
    a700 = definition(refreshed, "project02", "A700")
    payload = {
        "requirement": "将项目02 A700与A500保持50mm间距",
        "moduleDefinitionId": a700["moduleDefinitionId"],
    }
    first = preview_global_assembly_command(refreshed, context, payload)
    portable = [
        row
        for row in first["connectionCandidates"]
        if row["portable"]
        and row["relationAssessment"]["templateProfile"]["drivesPlacement"]
    ]
    assert first["status"] == "needs_confirmation"
    assert portable

    selected = portable[0]
    second = preview_global_assembly_command(
        refreshed,
        context,
        {
            **payload,
            "newPortId": selected["newPortId"],
            "existingPortId": selected["existingPortId"],
            "existingInstanceId": selected["existingInstanceId"],
            "globalTemplateId": selected["globalTemplateId"],
            "newSide": selected["newSide"],
        },
    )
    assert second["status"] == "ready"
    updated = apply_global_command_preview(
        context,
        second,
        preview_digest=second["previewDigest"],
        confirmed=True,
    )
    dag = compile_global_assembly_transaction_dag(refreshed, updated)
    assert dag["status"] == "blocked"
    assert "TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE" in {
        row["code"] for row in dag["blockers"]
    }
    explanation = dag["steps"][0]["constraintAssessment"][
        "templateExplanations"
    ][0]
    assert explanation["state"] == "declared_underconstrained"

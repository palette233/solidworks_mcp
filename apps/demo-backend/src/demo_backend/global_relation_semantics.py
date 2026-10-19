"""Natural-language relation intent and catalog-template semantics.

The global module catalog is assembled from several project-specific semantic
port catalogs.  Most of those templates are compound installation bundles.
This module prevents a compound bundle that merely *contains* a parallel or
concentric mate from being mistaken for a standalone user request for that
single relation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from typing import Any, Iterable


RELATION_INTENT_SCHEMA = "global-relation-intent/v1"
RELATION_TEMPLATE_PROFILE_SCHEMA = "global-relation-template-profile/v1"
RELATION_CAPABILITY_MATRIX_SCHEMA = "global-relation-capability-matrix/v1"


_RELATION_ORDER = (
    "installation",
    "coincident",
    "concentric",
    "parallel",
    "perpendicular",
    "distance",
    "angle",
    "centered",
    "slot",
)

_RELATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "installation": (
        r"安装(?!面|孔|基准|端口|表面)",
        r"装配",
        r"装到",
        r"固定到",
        r"接入",
        r"连接到",
        r"添加",
        r"加入",
        r"\binstall\b",
        r"\bmount\b",
        r"\badd\b",
        r"\bconnect\b",
    ),
    "coincident": (r"重合", r"贴合", r"共面", r"\bcoincident\b"),
    "concentric": (r"同轴", r"同心", r"轴线对齐", r"\bconcentric\b"),
    "parallel": (r"平行", r"\bparallel\b"),
    "perpendicular": (r"垂直", r"正交", r"\bperpendicular\b"),
    "distance": (r"距离", r"相距", r"间距", r"间隔", r"偏置", r"\bdistance\b", r"\boffset\b"),
    "angle": (r"角度", r"夹角", r"\bangle\b"),
    "centered": (r"居中", r"对中", r"中心对齐", r"宽度配合", r"\bcenter(?:ed)?\b"),
    "slot": (r"槽口", r"滑槽", r"\bslot\b"),
}

# In installation commands, ``transport slot`` and similar phrases name a
# catalog slot/port; they do not request a SolidWorks Slot mate.  Explicit
# geometry language such as ``pin in slot`` remains a real slot relation.
_INSTALLATION_TARGET_SLOT_PATTERNS: tuple[str, ...] = (
    r"\b(?:installation|mounting|transport|calibration|scanner|service|module)\s+slot\b",
)

_SIDE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("operator_side", (r"(?<!非)操作面侧", r"(?<!非)操作侧")),
    ("opposite_operator_side", (r"操作面对侧", r"非操作面侧", r"对侧")),
    ("left", (r"左侧", r"左边")),
    ("right", (r"右侧", r"右边")),
    ("front", (r"前侧", r"前面")),
    ("rear", (r"后侧", r"后面")),
)

_MATE_NAME_TO_KIND = {
    "SWMATECOINCIDENT": "coincident",
    "SWMATECONCENTRIC": "concentric",
    "SWMATEPARALLEL": "parallel",
    "SWMATEPERPENDICULAR": "perpendicular",
    "SWMATEDISTANCE": "distance",
    "SWMATEANGLE": "angle",
    "SWMATEWIDTH": "centered",
    "SWMATESLOT": "slot",
}

_MATE_TYPE_TO_KIND = {
    0: "coincident",
    1: "concentric",
    3: "parallel",
    4: "perpendicular",
    5: "distance",
    6: "angle",
    11: "centered",
    21: "slot",
}


# These definitions describe the information required to *request* a relation.
# They do not invent CAD endpoints and their DOF contributions are deliberately
# conservative/non-authoritative; the catalog template and SolidWorks solve
# remain the source of truth for a concrete connection.
GENERIC_RELATION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "installation": {
        "requiredEndpointGeometry": ["catalog-defined compound port bundle"],
        "requiredParameters": [],
        "dofContribution": "defined_by_selected_catalog_template",
        "automaticWithoutRegisteredPorts": False,
    },
    "coincident": {
        "requiredEndpointGeometry": ["plane-plane", "point-point"],
        "requiredParameters": [],
        "typicalRemovedScalarDofRange": [3, 3],
        "automaticWithoutRegisteredPorts": False,
    },
    "concentric": {
        "requiredEndpointGeometry": ["cylinder-cylinder", "axis-axis"],
        "requiredParameters": [],
        "typicalRemovedScalarDofRange": [4, 4],
        "automaticWithoutRegisteredPorts": False,
    },
    "parallel": {
        "requiredEndpointGeometry": ["plane-plane", "axis-axis"],
        "requiredParameters": [],
        "typicalRemovedScalarDofRange": [2, 2],
        "automaticWithoutRegisteredPorts": False,
    },
    "perpendicular": {
        "requiredEndpointGeometry": ["plane-plane", "axis-axis"],
        "requiredParameters": [],
        "typicalRemovedScalarDofRange": [1, 1],
        "automaticWithoutRegisteredPorts": False,
    },
    "distance": {
        "requiredEndpointGeometry": ["plane-plane", "point-point", "axis-axis"],
        "requiredParameters": ["distanceMeters"],
        "typicalRemovedScalarDofRange": [1, 3],
        "automaticWithoutRegisteredPorts": False,
    },
    "angle": {
        "requiredEndpointGeometry": ["plane-plane", "axis-axis"],
        "requiredParameters": ["angleDegrees"],
        "typicalRemovedScalarDofRange": [1, 3],
        "automaticWithoutRegisteredPorts": False,
    },
    "centered": {
        "requiredEndpointGeometry": ["two-width-planes plus two-tab-planes"],
        "requiredParameters": [],
        "typicalRemovedScalarDofRange": [1, 1],
        "automaticWithoutRegisteredPorts": False,
    },
    "slot": {
        "requiredEndpointGeometry": ["slot-face plus pin/cylinder"],
        "requiredParameters": ["slotConstraint"],
        "typicalRemovedScalarDofRange": [2, 4],
        "automaticWithoutRegisteredPorts": False,
    },
    "side_placement": {
        "requiredEndpointGeometry": ["named reference plane plus direction"],
        "requiredParameters": ["sideQualifier"],
        "dofContribution": "not_a_direct_mate_until_compiled_to_geometry",
        "automaticWithoutRegisteredPorts": False,
    },
}


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _quantity_values(text: str, *, kind: str) -> list[float]:
    if kind == "distance":
        pattern = re.compile(
            r"(?<![A-Za-z0-9_.])(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
            r"(?P<unit>毫米|mm|厘米|cm|米|m)(?![A-Za-z0-9])",
            flags=re.IGNORECASE,
        )
        scale = {"毫米": 0.001, "mm": 0.001, "厘米": 0.01, "cm": 0.01, "米": 1.0, "m": 1.0}
        return [
            float(match.group("value")) * scale[match.group("unit").lower()]
            for match in pattern.finditer(text)
        ]
    pattern = re.compile(
        r"(?<![A-Za-z0-9_.])(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
        r"(?P<unit>度|°|deg)(?![A-Za-z0-9])",
        flags=re.IGNORECASE,
    )
    return [float(match.group("value")) for match in pattern.finditer(text)]


def parse_relation_intent(requirement: str) -> dict[str, Any]:
    """Parse only relation semantics; module identity remains catalog-owned."""

    text = str(requirement or "").strip()
    folded = text.casefold()
    recognized = {
        kind
        for kind, patterns in _RELATION_PATTERNS.items()
        if _matches_any(folded, patterns)
    }
    if (
        "installation" in recognized
        and "slot" in recognized
        and _matches_any(folded, _INSTALLATION_TARGET_SLOT_PATTERNS)
    ):
        recognized.remove("slot")

    # Generic "对齐" is deliberately not guessed.  More specific phrases such
    # as 中心对齐 and 轴线对齐 have already been assigned above.
    generic_alignment = bool(
        re.search(r"对齐|\balign(?:ed|ment)?\b", folded, flags=re.IGNORECASE)
        and "centered" not in recognized
        and "concentric" not in recognized
    )

    side_values = [
        side
        for side, patterns in _SIDE_PATTERNS
        if _matches_any(folded, patterns)
    ]
    distance_values = _quantity_values(folded, kind="distance")
    angle_values = _quantity_values(folded, kind="angle")

    blockers: list[dict[str, Any]] = []
    if generic_alignment:
        blockers.append(
            {
                "code": "ALIGNMENT_KIND_REQUIRED",
                "detail": "“对齐”不能唯一确定重合、同轴、平行或居中关系。",
            }
        )
    if len({round(value, 12) for value in distance_values}) > 1:
        blockers.append(
            {
                "code": "MULTIPLE_DISTANCE_VALUES",
                "valuesMeters": distance_values,
            }
        )
    if len({round(value, 12) for value in angle_values}) > 1:
        blockers.append(
            {
                "code": "MULTIPLE_ANGLE_VALUES",
                "valuesDegrees": angle_values,
            }
        )
    if any(value < 0 for value in distance_values):
        blockers.append(
            {"code": "NEGATIVE_DISTANCE_NOT_ALLOWED", "valuesMeters": distance_values}
        )
    if len(set(side_values)) > 1:
        blockers.append(
            {"code": "MULTIPLE_SIDE_QUALIFIERS", "sideQualifiers": side_values}
        )

    has_installation = "installation" in recognized
    explicit = recognized - {"installation"}
    spacing_word = bool(re.search(r"间距|相距|间隔|\bspacing\b", folded, flags=re.IGNORECASE))
    if has_installation:
        primary = "installation"
    elif spacing_word:
        primary = "spacing"
    elif len(explicit) == 1:
        primary = next(iter(explicit))
    elif len(explicit) > 1:
        primary = "explicit_relation_set"
    elif side_values:
        primary = "side_placement"
    else:
        primary = "unspecified"

    requested = sorted(recognized, key=lambda value: _RELATION_ORDER.index(value))
    if primary == "spacing" and "distance" not in requested:
        requested.append("distance")
    result = {
        "schemaVersion": RELATION_INTENT_SCHEMA,
        "status": "blocked" if blockers else "parsed",
        "requirement": text,
        "primaryRelation": primary,
        "requestedRelationKinds": requested,
        "parameters": {
            "distanceMeters": distance_values[0] if len(distance_values) == 1 else None,
            "angleDegrees": angle_values[0] if len(angle_values) == 1 else None,
            "sideQualifier": side_values[0] if len(side_values) == 1 else None,
        },
        "genericAlignmentMentioned": generic_alignment,
        "blockers": blockers,
    }
    result["intentDigest"] = _digest(result)
    return result


def _mate_steps(template: dict[str, Any]) -> list[dict[str, Any]]:
    value = template.get("mateSteps") or []
    if isinstance(value, dict):
        return [value]
    return [item for item in value if isinstance(item, dict)]


def _relation_kind(step: dict[str, Any]) -> str:
    name = str(step.get("mateTypeName") or "").replace("_", "").upper()
    if name in _MATE_NAME_TO_KIND:
        return _MATE_NAME_TO_KIND[name]
    try:
        mate_type = int(step.get("mateType"))
    except (TypeError, ValueError):
        return "unknown"
    return _MATE_TYPE_TO_KIND.get(mate_type, "unknown")


def _constraint_explanation(template: dict[str, Any]) -> dict[str, Any]:
    effect = template.get("constraintEffect") or {}
    fully = effect.get("fullyLocatesAddedComponent")
    expected = effect.get("expectedResidualDof")
    residual = int(expected) if isinstance(expected, (int, float)) else None
    marker = str(fully or "").strip().casefold()
    if fully is True:
        state = "declared_closed"
        residual = 0
        evidence = "catalog_declaration"
    elif "cad-verified" in marker:
        state = "cad_verified_closed"
        residual = 0
        evidence = "historical_cad_verification"
    elif marker == "requires_cad_verification":
        state = "requires_cad_verification"
        evidence = "catalog_incomplete_until_cad_solve"
    elif fully is False:
        state = "declared_underconstrained"
        evidence = "catalog_declaration"
    else:
        state = "unknown"
        evidence = "insufficient_catalog_evidence"
    if effect.get("residualDofPolicy") and residual is None:
        evidence = "project_case_anchor_required"
    return {
        "state": state,
        "expectedResidualDof": residual,
        "residualDofKnown": residual is not None,
        "remainingDof": effect.get("remainingDof"),
        "requiredSolvingState": effect.get("requiredSolvingState"),
        "residualDofPolicy": effect.get("residualDofPolicy"),
        "evidence": evidence,
        "plainLanguage": (
            "模板声明可完整定位新增模组。"
            if residual == 0
            else f"模板预计仍保留{residual}个自由度。"
            if residual is not None
            else "目录尚不能确定该模板是否完整闭合自由度。"
        ),
    }


def normalize_template_relation_profile(template: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for index, step in enumerate(_mate_steps(template), start=1):
        application_mode = str(step.get("applicationMode") or "driving").strip().casefold()
        kind = _relation_kind(step)
        steps.append(
            {
                "order": index,
                "mateName": step.get("mateName"),
                "relationKind": kind,
                "applicationMode": application_mode,
                "driving": application_mode != "validate_only",
                "distanceMeters": step.get("distanceMeters"),
                "angleDegrees": step.get("angleDegrees"),
            }
        )
    kinds = sorted({item["relationKind"] for item in steps})
    driving_kinds = sorted({item["relationKind"] for item in steps if item["driving"]})
    validation_kinds = sorted({item["relationKind"] for item in steps if not item["driving"]})
    purposes = sorted({str(item) for item in template.get("purposes") or []})
    standalone = bool(
        ("spacing" in purposes and kinds == ["distance"])
        or (
            len(steps) == 1
            and len(kinds) == 1
            and "installation" not in purposes
        )
    )
    profile = {
        "schemaVersion": RELATION_TEMPLATE_PROFILE_SCHEMA,
        "globalTemplateId": template.get("globalTemplateId"),
        "legacyTemplateId": template.get("legacyTemplateId"),
        "purposes": purposes,
        "relationKinds": kinds,
        "drivingRelationKinds": driving_kinds,
        "validationRelationKinds": validation_kinds,
        "compoundInstallation": bool("installation" in purposes and len(steps) > 1),
        "supportsStandaloneRelation": standalone,
        "drivesPlacement": any(item["driving"] for item in steps),
        "drivingMateStepCount": sum(1 for item in steps if item["driving"]),
        "validationMateStepCount": sum(1 for item in steps if not item["driving"]),
        "mateSteps": steps,
        "constraintExplanation": _constraint_explanation(template),
        "provenance": template.get("provenance"),
    }
    profile["profileDigest"] = _digest(profile)
    return profile


def assess_template_for_relation_intent(
    template: dict[str, Any],
    intent: dict[str, Any],
    *,
    allow_validation_only: bool = False,
) -> dict[str, Any]:
    profile = normalize_template_relation_profile(template)
    reasons: list[dict[str, Any]] = []
    primary = str(intent.get("primaryRelation") or "unspecified")
    requested = set(intent.get("requestedRelationKinds") or [])
    kinds = set(profile["relationKinds"])
    purposes = set(profile["purposes"])

    if intent.get("status") == "blocked":
        reasons.extend(intent.get("blockers") or [])
    elif primary == "unspecified":
        pass
    elif primary == "installation":
        if "installation" not in purposes:
            reasons.append({"code": "INSTALLATION_TEMPLATE_REQUIRED"})
        missing = sorted((requested - {"installation"}) - kinds)
        if missing:
            reasons.append(
                {"code": "INSTALLATION_MODIFIER_NOT_IN_TEMPLATE", "missingKinds": missing}
            )
    elif primary in {"spacing", "distance"}:
        if not (
            "distance" in kinds
            and ("spacing" in purposes or profile["supportsStandaloneRelation"])
        ):
            reasons.append(
                {
                    "code": "STANDALONE_DISTANCE_TEMPLATE_REQUIRED",
                    "detail": "复合安装模板中的距离步骤不能单独替代间距关系。",
                }
            )
    elif primary == "explicit_relation_set":
        if not profile["supportsStandaloneRelation"] or not requested.issubset(kinds):
            reasons.append(
                {
                    "code": "EXACT_RELATION_BUNDLE_TEMPLATE_REQUIRED",
                    "requestedKinds": sorted(requested),
                }
            )
    elif primary == "side_placement":
        reasons.append({"code": "SIDE_REFERENCE_TEMPLATE_REQUIRED"})
    elif primary not in kinds or not profile["supportsStandaloneRelation"]:
        reasons.append(
            {
                "code": "STANDALONE_RELATION_TEMPLATE_REQUIRED",
                "requestedKind": primary,
                "detail": "模板中包含该配合并不等于它可作为独立关系执行。",
            }
        )

    parameters = intent.get("parameters") or {}
    side = parameters.get("sideQualifier")
    if side and side not in set(template.get("sideSemantics") or []):
        reasons.append(
            {
                "code": "SIDE_QUALIFIER_NOT_DECLARED_BY_TEMPLATE",
                "sideQualifier": side,
            }
        )

    requested_distance = parameters.get("distanceMeters")
    supported_distances = sorted(
        {
            float(item["distanceMeters"])
            for item in profile["mateSteps"]
            if item["relationKind"] == "distance"
            and isinstance(item.get("distanceMeters"), (int, float))
        }
    )
    if requested_distance is not None and not any(
        math.isclose(float(requested_distance), value, abs_tol=1e-6)
        for value in supported_distances
    ):
        reasons.append(
            {
                "code": "REQUESTED_DISTANCE_NOT_SUPPORTED_BY_TEMPLATE",
                "requestedDistanceMeters": requested_distance,
                "supportedDistanceMeters": supported_distances,
                "parameterOverrideAllowed": False,
            }
        )

    requested_angle = parameters.get("angleDegrees")
    supported_angles = sorted(
        {
            float(item["angleDegrees"])
            for item in profile["mateSteps"]
            if item["relationKind"] == "angle"
            and isinstance(item.get("angleDegrees"), (int, float))
        }
    )
    if requested_angle is not None and not any(
        math.isclose(float(requested_angle), value, abs_tol=1e-6)
        for value in supported_angles
    ):
        reasons.append(
            {
                "code": "REQUESTED_ANGLE_NOT_SUPPORTED_BY_TEMPLATE",
                "requestedAngleDegrees": requested_angle,
                "supportedAngleDegrees": supported_angles,
                "parameterOverrideAllowed": False,
            }
        )

    if (
        not reasons
        and profile["drivesPlacement"] is not True
        and not allow_validation_only
    ):
        reasons.append(
            {
                "code": "VALIDATION_ONLY_RELATION_CANNOT_DRIVE_PLACEMENT",
                "detail": "该模板只能检查已有位姿，不能定位新插入模组。",
            }
        )

    return {
        "compatible": not reasons,
        "reasons": reasons,
        "templateProfile": profile,
    }


def evaluate_connection_candidates_for_relation(
    catalog: dict[str, Any],
    candidates: list[dict[str, Any]],
    intent: dict[str, Any],
    *,
    allow_validation_only: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    templates = {
        str(item.get("globalTemplateId") or ""): item
        for item in catalog.get("connectionTemplates") or []
    }
    matching: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    for candidate in candidates:
        template_id = str(candidate.get("globalTemplateId") or "")
        template = templates.get(template_id)
        if template is None:
            assessment = {
                "compatible": False,
                "reasons": [{"code": "RELATION_TEMPLATE_NOT_FOUND"}],
                "templateProfile": None,
            }
        else:
            assessment = assess_template_for_relation_intent(
                template,
                intent,
                allow_validation_only=allow_validation_only,
            )
        enriched = {**candidate, "relationAssessment": assessment}
        assessments.append(enriched)
        if assessment["compatible"]:
            matching.append(enriched)
    return matching, assessments


def build_relation_capability_matrix(catalog: dict[str, Any]) -> dict[str, Any]:
    compatibility_by_template = Counter(
        str(row.get("globalTemplateId") or "")
        for row in catalog.get("compatibility") or []
        if row.get("portableForTemplate") is True
    )
    profiles = [
        normalize_template_relation_profile(template)
        for template in catalog.get("connectionTemplates") or []
    ]
    for profile in profiles:
        portable_count = compatibility_by_template.get(
            str(profile.get("globalTemplateId") or ""), 0
        )
        profile["portableCompatibilityCount"] = portable_count
        profile["catalogExecutable"] = bool(
            profile.get("drivesPlacement") and portable_count > 0
        )
        profile["profileDigest"] = _digest(
            {key: value for key, value in profile.items() if key != "profileDigest"}
        )
    kind_counts = Counter(
        kind for profile in profiles for kind in profile.get("relationKinds") or []
    )
    standalone_counts = Counter(
        kind
        for profile in profiles
        if profile.get("supportsStandaloneRelation")
        for kind in profile.get("relationKinds") or []
    )
    standalone_driving_counts = Counter(
        kind
        for profile in profiles
        if profile.get("supportsStandaloneRelation") and profile.get("drivesPlacement")
        for kind in profile.get("relationKinds") or []
    )
    constraint_counts = Counter(
        str((profile.get("constraintExplanation") or {}).get("state") or "unknown")
        for profile in profiles
    )
    result = {
        "schemaVersion": RELATION_CAPABILITY_MATRIX_SCHEMA,
        "sourceCatalogDigest": catalog.get("catalogDigest"),
        "claimBoundary": (
            "关系被识别不等于CAD可执行；独立基础关系必须存在精确模板，"
            "复合安装模板不能拆借其中单个配合。"
        ),
        "genericRelationDefinitions": {
            kind: {
                **definition,
                "dofEstimateAuthority": "non_authoritative_until_concrete_template_and_cad_solve",
            }
            for kind, definition in GENERIC_RELATION_DEFINITIONS.items()
        },
        "templateProfiles": profiles,
        "summary": {
            "templateCount": len(profiles),
            "compoundInstallationTemplateCount": sum(
                1 for profile in profiles if profile["compoundInstallation"]
            ),
            "standaloneRelationTemplateCount": sum(
                1 for profile in profiles if profile["supportsStandaloneRelation"]
            ),
            "placementCapableStandaloneRelationTemplateCount": sum(
                1
                for profile in profiles
                if profile["supportsStandaloneRelation"] and profile["drivesPlacement"]
            ),
            "portablePlacementCapableStandaloneRelationTemplateCount": sum(
                1
                for profile in profiles
                if profile["supportsStandaloneRelation"]
                and profile["catalogExecutable"]
            ),
            "relationKindTemplateCounts": dict(sorted(kind_counts.items())),
            "standaloneRelationKindTemplateCounts": dict(sorted(standalone_counts.items())),
            "placementCapableStandaloneRelationKindTemplateCounts": dict(
                sorted(standalone_driving_counts.items())
            ),
            "constraintStateCounts": dict(sorted(constraint_counts.items())),
        },
        "collisionStatus": "not_evaluated",
    }
    result["matrixDigest"] = _digest(result)
    return result


def validate_relation_capability_matrix(
    matrix: dict[str, Any], *, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    if matrix.get("schemaVersion") != RELATION_CAPABILITY_MATRIX_SCHEMA:
        raise ValueError("不支持的全局关系能力矩阵版本。")
    profiles = matrix.get("templateProfiles")
    if not isinstance(profiles, list):
        raise ValueError("关系能力矩阵缺少templateProfiles数组。")
    template_ids = [str(item.get("globalTemplateId") or "") for item in profiles]
    if any(not item for item in template_ids) or len(template_ids) != len(set(template_ids)):
        raise ValueError("关系模板ID必须非空且唯一。")
    expected = _digest(
        {key: value for key, value in matrix.items() if key != "matrixDigest"}
    )
    if matrix.get("matrixDigest") != expected:
        raise ValueError("关系能力矩阵摘要不匹配。")
    if catalog is not None:
        if matrix.get("sourceCatalogDigest") != catalog.get("catalogDigest"):
            raise ValueError("关系能力矩阵与全局目录摘要不一致。")
        catalog_ids = {
            str(item.get("globalTemplateId") or "")
            for item in catalog.get("connectionTemplates") or []
        }
        if set(template_ids) != catalog_ids:
            raise ValueError("关系能力矩阵未完整覆盖全局目录模板。")
    return {
        "success": True,
        "schemaVersion": RELATION_CAPABILITY_MATRIX_SCHEMA,
        "templateCount": len(profiles),
        "matrixDigest": expected,
    }


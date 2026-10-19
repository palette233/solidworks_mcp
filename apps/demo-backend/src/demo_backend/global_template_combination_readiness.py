from __future__ import annotations

from typing import Any

from .global_module_catalog import validate_global_module_catalog


ANCHOR_MARKERS = (
    "anchor",
    "prototype",
    "calibrated",
    "case_pose",
    "case pose",
)


def assess_template_combination_readiness(
    catalog: dict[str, Any],
    *,
    project_id: str,
) -> dict[str, Any]:
    """Classify installation templates without inventing missing closure data."""

    validate_global_module_catalog(catalog)
    project = str(project_id).strip().lower()
    combinations = list(catalog.get("templateCombinations") or [])
    combination_by_member: dict[str, list[dict[str, Any]]] = {}
    for combination in combinations:
        for template_id in combination.get("memberGlobalTemplateIds") or []:
            combination_by_member.setdefault(str(template_id), []).append(combination)

    rows: list[dict[str, Any]] = []
    for template in catalog.get("connectionTemplates") or []:
        provenance = template.get("provenance") or {}
        if str(provenance.get("projectId") or "").lower() != project:
            continue
        if "installation" not in (template.get("purposes") or []):
            continue
        template_id = str(template.get("globalTemplateId") or "")
        effect = template.get("constraintEffect") or {}
        purpose = str(effect.get("purpose") or "")
        source_path = str(provenance.get("semanticCatalogPath") or "")
        # Anchor/prototype dependence is part of the semantic identity, not only
        # free-form prose.  Several early Project03 templates encoded the fact
        # in their legacy id (for example ``*_anchored_installation``), while
        # their purpose sentence looked like an ordinary closed constraint
        # bundle.  Ignoring the id let those rows appear portable even when the
        # real CAD run still required a case-pose anchor.
        marker_text = " ".join(
            [
                purpose,
                source_path,
                str(template.get("legacyTemplateId") or ""),
                template_id,
            ]
        ).casefold()
        anchor_markers = [value for value in ANCHOR_MARKERS if value in marker_text]
        driving_steps = [
            row
            for row in template.get("mateSteps") or []
            if row.get("applicationMode") != "validate_only"
        ]
        validating_steps = [
            row
            for row in template.get("mateSteps") or []
            if row.get("applicationMode") == "validate_only"
        ]
        member_combinations = combination_by_member.get(template_id, [])
        fully_locates = effect.get("fullyLocatesAddedComponent") is True
        residual = effect.get("expectedResidualDof")
        contradiction = bool(
            fully_locates
            and residual == 0
            and "residual" in purpose.casefold()
            and ("expose" in purpose.casefold() or "partial" in purpose.casefold())
        )
        blockers: list[dict[str, Any]] = []
        if contradiction:
            blockers.append(
                {
                    "code": "CONSTRAINT_DECLARATION_CONTRADICTS_PURPOSE",
                    "detail": "模板用途仍声明残余自由度，但约束效果却声明完整定位。",
                }
            )
        if anchor_markers:
            blockers.append(
                {
                    "code": "PROTOTYPE_OR_ANCHOR_DEPENDENCY_DECLARED",
                    "detail": "模板说明或来源仍包含锚点/原型标定依赖。",
                    "markers": anchor_markers,
                }
            )
        if not fully_locates or residual != 0:
            if not member_combinations:
                blockers.append(
                    {
                        "code": "SUPPLEMENTAL_RELATION_OR_COMBINATION_MISSING",
                        "detail": "模板仍有剩余自由度，目录中没有补充关系组合。",
                        "expectedResidualDof": residual,
                    }
                )
        if member_combinations:
            state = "member_of_declared_combination"
        elif fully_locates and residual == 0 and not blockers:
            state = "declared_atomic_closed"
        elif blockers:
            state = "requires_semantic_completion"
        else:
            state = "not_proven_closed"
        rows.append(
            {
                "globalTemplateId": template_id,
                "legacyTemplateId": template.get("legacyTemplateId"),
                "state": state,
                "fullyLocatesAddedComponent": fully_locates,
                "expectedResidualDof": residual,
                "drivingMateStepCount": len(driving_steps),
                "validateOnlyMateStepCount": len(validating_steps),
                "declaredCombinationIds": sorted(
                    str(row.get("globalCombinationId") or "")
                    for row in member_combinations
                ),
                "semanticCatalogPath": source_path,
                "blockers": blockers,
            }
        )

    return {
        "schemaVersion": "global-template-combination-readiness/v1",
        "catalogDigest": catalog.get("catalogDigest"),
        "projectId": project,
        "templateCount": len(rows),
        "declaredAtomicClosedCount": sum(
            row["state"] == "declared_atomic_closed" for row in rows
        ),
        "declaredCombinationMemberCount": sum(
            row["state"] == "member_of_declared_combination" for row in rows
        ),
        "requiresSemanticCompletionCount": sum(
            row["state"] == "requires_semantic_completion" for row in rows
        ),
        "templates": rows,
        "policy": {
            "prototypeTopLevelPoseMayCloseResidualDof": False,
            "collisionOrBrepEvaluated": False,
        },
    }

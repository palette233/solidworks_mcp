"""Compare declared assembly dependencies with observed mechanical mate edges.

The project profiles contain both process/order dependencies and mechanical
placement dependencies.  They are intentionally not treated as equivalent:
only an exported mate graph can prove that two modules are mechanically
connected.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .global_relation_semantics import normalize_template_relation_profile


AUDIT_SCHEMA = "module-relation-topology-audit/v1"


def _token_aliases(profile: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for token, row in profile.get("modules", {}).items():
        canonical = str(token).upper()
        aliases[canonical] = canonical
        for component_name in row.get("componentNames") or [row.get("componentName")]:
            value = str(component_name or "").strip().upper()
            if not value:
                continue
            aliases[value] = canonical
            stem = value.split(".001", 1)[0]
            aliases[stem] = canonical
            # Historical graphs sometimes use only the four-character suffix
            # of a component that the profile intentionally groups into one
            # functional module (for example LM00 + ZZ00).
            if len(stem) >= 4:
                aliases[stem[-4:]] = canonical
    return aliases


def _normalize_token(value: Any, aliases: dict[str, str]) -> str:
    raw = str(value or "").strip().upper()
    if raw in aliases:
        return aliases[raw]
    without_instance = raw.split("-", 1)[0]
    if without_instance in aliases:
        return aliases[without_instance]
    matches = {
        canonical
        for alias, canonical in aliases.items()
        if len(alias) >= 4 and (raw.startswith(alias) or alias.startswith(raw))
    }
    return next(iter(matches)) if len(matches) == 1 else raw


def _edge(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))


def audit_relation_topology(
    profile: dict[str, Any],
    graph_records: Iterable[tuple[str | Path, dict[str, Any]]],
) -> dict[str, Any]:
    """Return mechanical edges, process-only dependencies, and non-star edges."""

    project_id = str(profile.get("projectId") or "").lower()
    base_module = str(profile.get("baseModule") or "").upper()
    aliases = _token_aliases(profile)
    known_tokens = set(str(value).upper() for value in profile.get("modules", {}))
    observations: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    unknown_tokens: set[str] = set()

    for raw_path, graph in graph_records:
        source_path = str(raw_path)
        policy = graph.get("EditPolicy") or graph.get("editPolicy") or {}
        case_anchors = [
            _normalize_token(value, aliases)
            for value in policy.get("caseAnchoredModuleTokens")
            or policy.get("CaseAnchoredModuleTokens")
            or []
        ]
        leaf_anchor_count = len(
            graph.get("LeafPoseAnchors")
            or graph.get("leafPoseAnchors")
            or graph.get("PoseAnchors")
            or []
        )
        for mate in graph.get("Mates") or graph.get("mates") or []:
            tokens = [
                _normalize_token(value, aliases)
                for value in mate.get("ModuleTokens")
                or mate.get("moduleTokens")
                or []
            ]
            tokens = list(dict.fromkeys(tokens))
            if len(tokens) != 2:
                continue
            unknown_tokens.update(value for value in tokens if value not in known_tokens)
            pair = _edge(tokens[0], tokens[1])
            observations[pair].append(
                {
                    "graphPath": source_path,
                    "mateId": mate.get("MateId") or mate.get("mateId"),
                    "mateName": mate.get("MateName") or mate.get("mateName"),
                    "mateType": mate.get("MateTypeName") or mate.get("mateTypeName"),
                    "caseAnchoredModuleTokens": sorted(set(case_anchors)),
                    "leafPoseAnchorCount": leaf_anchor_count,
                    "portableWithoutPoseAnchor": not case_anchors and leaf_anchor_count == 0,
                }
            )

    mechanical_edges = []
    for pair, rows in sorted(observations.items()):
        portable_rows = [row for row in rows if row["portableWithoutPoseAnchor"]]
        mechanical_edges.append(
            {
                "moduleTokens": list(pair),
                "mateObservationCount": len(rows),
                "graphPaths": sorted({row["graphPath"] for row in rows}),
                "portableObservationCount": len(portable_rows),
                "hasPoseAnchorFreeEvidence": bool(portable_rows),
                "isBaseEdge": base_module in pair,
                "isNonStarMechanicalEdge": base_module not in pair,
                "observations": rows,
            }
        )

    declared_dependencies = []
    process_only = []
    mechanical_pairs = set(observations)
    for target, row in profile.get("modules", {}).items():
        target = str(target).upper()
        policy = row.get("assemblyPolicy") or {}
        for required in policy.get("requires") or []:
            required = str(required).upper()
            pair = _edge(target, required)
            item = {
                "targetModuleToken": target,
                "requiredModuleToken": required,
                "mechanicalMateObserved": pair in mechanical_pairs,
                "classification": (
                    "mechanical_and_process_dependency"
                    if pair in mechanical_pairs
                    else "process_or_sequence_dependency_only"
                ),
            }
            declared_dependencies.append(item)
            if pair not in mechanical_pairs:
                process_only.append(item)

    nonstar = [row for row in mechanical_edges if row["isNonStarMechanicalEdge"]]
    portable_nonstar = [row for row in nonstar if row["hasPoseAnchorFreeEvidence"]]
    return {
        "schemaVersion": AUDIT_SCHEMA,
        "projectId": project_id,
        "baseModuleToken": base_module,
        "mechanicalEdgeCount": len(mechanical_edges),
        "nonStarMechanicalEdgeCount": len(nonstar),
        "portableNonStarMechanicalEdgeCount": len(portable_nonstar),
        "mechanicalEdges": mechanical_edges,
        "declaredDependencies": declared_dependencies,
        "processOnlyDependencies": process_only,
        "portableNonStarMechanicalEdges": portable_nonstar,
        "unknownObservedModuleTokens": sorted(unknown_tokens),
        "claimBoundary": (
            "assemblyPolicy.requires描述装配顺序或工艺上下文；只有配合图中的"
            "ModuleTokens边可证明两个模组存在机械配合。"
        ),
    }


def annotate_relation_topology_with_catalog(
    audit: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    """Attach catalog execution semantics without upgrading an edge to driving."""

    project_id = str(audit.get("projectId") or "").lower()
    definition_tokens: dict[str, str] = {}
    for definition in catalog.get("moduleDefinitions") or []:
        definition_id = str(definition.get("moduleDefinitionId") or "")
        tokens = {
            str(alias.get("moduleToken") or "").upper()
            for alias in definition.get("projectAliases") or []
            if str(alias.get("projectId") or "").lower() == project_id
        }
        if len(tokens) == 1:
            definition_tokens[definition_id] = next(iter(tokens))
    port_definitions = {
        str(port.get("globalPortId") or ""): str(port.get("moduleDefinitionId") or "")
        for port in catalog.get("semanticPorts") or []
    }

    templates_by_edge: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    template_edges: dict[str, tuple[str, str]] = {}
    for template in catalog.get("connectionTemplates") or []:
        provenance = template.get("provenance") or {}
        if str(provenance.get("projectId") or "").lower() != project_id:
            continue
        port_ids = {
            str(value)
            for key in ("candidatePortIdsA", "candidatePortIdsB")
            for value in template.get(key) or []
        }
        tokens = {
            definition_tokens.get(port_definitions.get(port_id, ""), "")
            for port_id in port_ids
        }
        tokens.discard("")
        if len(tokens) != 2:
            continue
        profile = normalize_template_relation_profile(template)
        constraint_state = (profile.get("constraintExplanation") or {}).get("state")
        drives_placement = profile.get("drivesPlacement") is True
        release_ready_driver = drives_placement and constraint_state in {
            "declared_closed",
            "cad_verified_closed",
        }
        pair = _edge(*sorted(tokens))
        template_id = str(template.get("globalTemplateId") or "")
        template_edges[template_id] = pair
        templates_by_edge[pair].append(
            {
                "globalTemplateId": template_id,
                "legacyTemplateId": template.get("legacyTemplateId"),
                "purposes": template.get("purposes") or [],
                "relationKinds": profile.get("relationKinds") or [],
                "drivesPlacement": drives_placement,
                "releaseReadyPlacementDriver": release_ready_driver,
                "drivingMateStepCount": profile.get("drivingMateStepCount"),
                "validationMateStepCount": profile.get("validationMateStepCount"),
                "constraintState": constraint_state,
            }
        )

    combinations_by_edge: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for combination in catalog.get("templateCombinations") or []:
        provenance = combination.get("provenance") or {}
        if str(provenance.get("projectId") or "").lower() != project_id:
            continue
        member_ids = [
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        ]
        member_edges = sorted(
            {template_edges[value] for value in member_ids if value in template_edges}
        )
        if not member_edges:
            continue
        collectively_closed = (
            combination.get("fullyLocatesAddedComponent") is True
            and int(combination.get("expectedResidualDof") or 0) == 0
            and combination.get("exactMemberSetRequired") is True
        )
        summary = {
            "globalCombinationId": combination.get("globalCombinationId"),
            "legacyCombinationId": combination.get("legacyCombinationId"),
            "memberGlobalTemplateIds": member_ids,
            "memberMechanicalEdges": [list(value) for value in member_edges],
            "collectivelyClosesPlacement": collectively_closed,
            "applicationScope": combination.get("applicationScope"),
            "explanation": combination.get("explanation"),
        }
        for pair in member_edges:
            combinations_by_edge[pair].append(summary)

    result = deepcopy(audit)
    result["schemaVersion"] = "module-relation-semantic-topology-audit/v2"
    for edge in result.get("mechanicalEdges") or []:
        pair = _edge(*(str(value).upper() for value in edge.get("moduleTokens") or []))
        templates = templates_by_edge.get(pair, [])
        driving_candidates = [row for row in templates if row["drivesPlacement"]]
        ready_driving = [
            row for row in driving_candidates if row["releaseReadyPlacementDriver"]
        ]
        incomplete_driving = [
            row for row in driving_candidates if not row["releaseReadyPlacementDriver"]
        ]
        validation_only = [
            row
            for row in templates
            if not row["drivesPlacement"] and int(row.get("validationMateStepCount") or 0) > 0
        ]
        combinations = combinations_by_edge.get(pair, [])
        closing_combinations = [
            row for row in combinations if row["collectivelyClosesPlacement"]
        ]
        edge["catalogRelationSemantics"] = {
            "templateCount": len(templates),
            "drivingTemplateCount": len(driving_candidates),
            "releaseReadyDrivingTemplateCount": len(ready_driving),
            "incompleteDrivingTemplateCount": len(incomplete_driving),
            "validationOnlyTemplateCount": len(validation_only),
            "collectivelyClosingCombinationCount": len(closing_combinations),
            "classification": (
                "has_driving_template"
                if ready_driving
                else "collectively_closed_bundle_member"
                if closing_combinations
                else "validation_only"
                if validation_only
                else "incomplete_driving_only"
                if incomplete_driving
                else "mechanical_edge_without_catalog_template"
            ),
            "placementDriverReady": bool(ready_driving),
            "collectivePlacementClosureAvailable": bool(closing_combinations),
            "drivingAuthorizationImpliedByMechanicalEdge": False,
            "templates": templates,
            "templateCombinations": combinations,
        }
    result["claimBoundary"] += (
        " 机械边存在本身不授予位姿驱动权限；仍需模板语义、自由度闭合和真实CAD证据。"
    )
    return result

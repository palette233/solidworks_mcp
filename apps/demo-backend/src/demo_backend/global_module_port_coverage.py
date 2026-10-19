"""Build a deterministic module/port/template coverage matrix.

The global module catalog is the source of truth.  This module does not invent
missing ports or CAD geometry; it turns existing evidence into explicit ready
or blocked states that can be consumed before SolidWorks is started.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from typing import Any, Iterable

from .global_module_catalog import validate_global_module_catalog


COVERAGE_MATRIX_SCHEMA = "global-module-port-coverage-matrix/v1"
SELECTION_READINESS_SCHEMA = "global-module-selection-readiness/v1"

CHAIN_CRITICAL_CATEGORIES = {
    "frame",
    "transport",
    "scanner",
    "ccd",
    "calibration",
    "cleaning_weighing",
    "gantry",
}


class GlobalModulePortCoverageError(ValueError):
    pass


def _digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _priority(definition: dict[str, Any]) -> str:
    is_base = any(bool(row.get("isBaseModule")) for row in definition.get("projectAliases") or [])
    return "P0" if is_base or definition.get("category") in CHAIN_CRITICAL_CATEGORIES else "P1"


def _module_aliases(definition: dict[str, Any]) -> list[str]:
    aliases = set(str(value).strip() for value in definition.get("aliases") or [] if str(value).strip())
    for row in definition.get("projectAliases") or []:
        project_id = str(row.get("projectId") or "").strip().lower()
        token = str(row.get("moduleToken") or "").strip()
        if token:
            aliases.add(token)
        if project_id and token:
            aliases.add(f"{project_id}:{token}")
    return sorted(aliases, key=str.casefold)


def build_global_module_port_coverage_matrix(catalog: dict[str, Any]) -> dict[str, Any]:
    """Summarize module, port, template and pair-level execution coverage."""

    validate_global_module_catalog(catalog)
    definitions = {
        str(row["moduleDefinitionId"]): row for row in catalog.get("moduleDefinitions") or []
    }
    ports = {str(row["globalPortId"]): row for row in catalog.get("semanticPorts") or []}
    templates = {
        str(row["globalTemplateId"]): row
        for row in catalog.get("connectionTemplates") or []
    }

    compatibility_by_port: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pair_rows: list[dict[str, Any]] = []
    for edge in catalog.get("compatibility") or []:
        port_a_id = str(edge.get("portAId") or "")
        port_b_id = str(edge.get("portBId") or "")
        port_a = ports.get(port_a_id) or {}
        port_b = ports.get(port_b_id) or {}
        definition_a = str(port_a.get("moduleDefinitionId") or "")
        definition_b = str(port_b.get("moduleDefinitionId") or "")
        template_id = str(edge.get("globalTemplateId") or "")
        template = templates.get(template_id) or {}
        endpoint_ready = bool(edge.get("portableForTemplate"))
        blockers = [] if endpoint_ready else ["TEMPLATE_ENDPOINTS_NOT_PORTABLE"]
        row = {
            "pairId": f"pair/{_digest([definition_a, definition_b, port_a_id, port_b_id, template_id])[:16]}",
            "moduleDefinitionIdA": definition_a,
            "moduleDefinitionIdB": definition_b,
            "portAId": port_a_id,
            "portBId": port_b_id,
            "templateId": template_id,
            "legacyTemplateId": template.get("legacyTemplateId"),
            "purpose": edge.get("purpose"),
            "directional": bool(edge.get("directional", True)),
            "semanticGraphReady": bool(definition_a and definition_b and template_id),
            "cadEndpointReady": endpoint_ready,
            "status": "ready" if endpoint_ready else "blocked",
            "blockers": blockers,
        }
        pair_rows.append(row)
        compatibility_by_port[port_a_id].append(row)
        compatibility_by_port[port_b_id].append(row)

    module_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    for definition_id, definition in definitions.items():
        module_ports = [ports[port_id] for port_id in definition.get("portIds") or [] if port_id in ports]
        mechanical_ports = [row for row in module_ports if str(row.get("category")) == "mechanical"]
        functional_ports = [row for row in module_ports if str(row.get("category")) == "functional"]
        portable_ports = [row for row in module_ports if bool(row.get("portable"))]
        edges = {
            row["pairId"]: row
            for port in module_ports
            for row in compatibility_by_port.get(str(port.get("globalPortId") or ""), [])
        }
        compatible_edges = list(edges.values())
        portable_edges = [row for row in compatible_edges if row["cadEndpointReady"]]
        template_ids = sorted({str(row["templateId"]) for row in compatible_edges})
        purposes = sorted({str(row.get("purpose") or "") for row in compatible_edges if row.get("purpose")})
        compatible_definitions = sorted(
            {
                str(row["moduleDefinitionIdB"])
                if row["moduleDefinitionIdA"] == definition_id
                else str(row["moduleDefinitionIdA"])
                for row in portable_edges
            }
            - {definition_id}
        )
        blockers: list[str] = []
        if not module_ports:
            blockers.append("NO_SEMANTIC_PORT")
        if module_ports and not mechanical_ports:
            blockers.append("NO_MECHANICAL_INSTALLATION_PORT")
        if module_ports and not compatible_edges:
            blockers.append("NO_COMPATIBILITY_EDGE")
        if compatible_edges and not portable_edges:
            blockers.append("NO_PORTABLE_TEMPLATE_ENDPOINT_SET")
        if mechanical_ports and not any(bool(row.get("portable")) for row in mechanical_ports):
            blockers.append("NO_PORTABLE_MECHANICAL_PORT")
        graph_ready = bool(compatible_edges)
        cad_endpoint_ready = bool(portable_edges)
        status = (
            "ready_for_generic_cad_planning"
            if cad_endpoint_ready
            else "ready_for_semantic_graph_only"
            if graph_ready
            else "blocked"
        )
        row = {
            "moduleDefinitionId": definition_id,
            "displayName": definition.get("displayName"),
            "category": definition.get("category"),
            "aliases": _module_aliases(definition),
            "projectAliases": definition.get("projectAliases") or [],
            "componentNames": definition.get("componentNames") or [],
            "cadSources": definition.get("cadSources") or [],
            "isBaseModule": any(
                bool(item.get("isBaseModule")) for item in definition.get("projectAliases") or []
            ),
            "gapPriority": _priority(definition),
            "portCount": len(module_ports),
            "mechanicalPortCount": len(mechanical_ports),
            "functionalPortCount": len(functional_ports),
            "portablePortCount": len(portable_ports),
            "compatibleEdgeCount": len(compatible_edges),
            "portableCompatibleEdgeCount": len(portable_edges),
            "templateIds": template_ids,
            "supportedPurposes": purposes,
            "compatibleModuleDefinitionIds": compatible_definitions,
            "naturalLanguageSearchable": bool(_module_aliases(definition)),
            "semanticGraphReady": graph_ready,
            "cadEndpointReady": cad_endpoint_ready,
            "status": status,
            "blockers": blockers,
            "ports": [
                {
                    "globalPortId": port.get("globalPortId"),
                    "displayName": port.get("displayName"),
                    "category": port.get("category"),
                    "interfaceType": port.get("interfaceType"),
                    "capabilities": port.get("capabilities") or [],
                    "portable": bool(port.get("portable")),
                    "portabilityReasons": port.get("portabilityReasons") or [],
                    "compatibleEdgeCount": len(
                        compatibility_by_port.get(str(port.get("globalPortId") or ""), [])
                    ),
                    "portableCompatibleEdgeCount": sum(
                        bool(item["cadEndpointReady"])
                        for item in compatibility_by_port.get(
                            str(port.get("globalPortId") or ""), []
                        )
                    ),
                }
                for port in sorted(module_ports, key=lambda item: str(item.get("globalPortId")))
            ],
        }
        module_rows.append(row)
        for code in blockers:
            gap_rows.append(
                {
                    "priority": row["gapPriority"],
                    "code": code,
                    "moduleDefinitionId": definition_id,
                    "displayName": row["displayName"],
                    "category": row["category"],
                    "projectAliases": row["projectAliases"],
                }
            )

    category_rows: list[dict[str, Any]] = []
    categories = sorted({str(row.get("category") or "functional") for row in module_rows})
    for category in categories:
        rows = [row for row in module_rows if row.get("category") == category]
        category_rows.append(
            {
                "category": category,
                "moduleCount": len(rows),
                "graphReadyCount": sum(bool(row["semanticGraphReady"]) for row in rows),
                "cadEndpointReadyCount": sum(bool(row["cadEndpointReady"]) for row in rows),
                "blockedModuleDefinitionIds": [
                    row["moduleDefinitionId"] for row in rows if not row["cadEndpointReady"]
                ],
            }
        )

    module_rows.sort(key=lambda row: str(row["moduleDefinitionId"]))
    pair_rows.sort(key=lambda row: str(row["pairId"]))
    gap_rows.sort(
        key=lambda row: (
            0 if row["priority"] == "P0" else 1,
            str(row["code"]),
            str(row["moduleDefinitionId"]),
        )
    )
    matrix: dict[str, Any] = {
        "schemaVersion": COVERAGE_MATRIX_SCHEMA,
        "sourceCatalogDigest": catalog.get("catalogDigest"),
        "purpose": "自然语言模组组合在启动SolidWorks前的端口、模板和端点覆盖审计",
        "claimBoundary": (
            "ready只表示存在可恢复端点和已登记关系模板；不表示碰撞、光学、动态工艺或生产放行。"
        ),
        "modules": module_rows,
        "connectionPairs": pair_rows,
        "categories": category_rows,
        "gaps": gap_rows,
        "summary": {
            "moduleCount": len(module_rows),
            "naturalLanguageSearchableModuleCount": sum(
                bool(row["naturalLanguageSearchable"]) for row in module_rows
            ),
            "semanticGraphReadyModuleCount": sum(
                bool(row["semanticGraphReady"]) for row in module_rows
            ),
            "cadEndpointReadyModuleCount": sum(
                bool(row["cadEndpointReady"]) for row in module_rows
            ),
            "blockedModuleCount": sum(not bool(row["cadEndpointReady"]) for row in module_rows),
            "connectionPairCount": len(pair_rows),
            "cadReadyConnectionPairCount": sum(bool(row["cadEndpointReady"]) for row in pair_rows),
            "gapCount": len(gap_rows),
            "p0GapCount": sum(row["priority"] == "P0" for row in gap_rows),
            "p1GapCount": sum(row["priority"] == "P1" for row in gap_rows),
        },
    }
    matrix["matrixDigest"] = _digest(matrix)
    return matrix


def validate_global_module_port_coverage_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    if matrix.get("schemaVersion") != COVERAGE_MATRIX_SCHEMA:
        raise GlobalModulePortCoverageError("不支持的全局模组端口覆盖矩阵版本。")
    modules = matrix.get("modules")
    pairs = matrix.get("connectionPairs")
    if not isinstance(modules, list) or not isinstance(pairs, list):
        raise GlobalModulePortCoverageError("覆盖矩阵缺少modules或connectionPairs数组。")
    module_ids = [str(row.get("moduleDefinitionId") or "") for row in modules]
    if any(not value for value in module_ids) or len(module_ids) != len(set(module_ids)):
        raise GlobalModulePortCoverageError("覆盖矩阵中的moduleDefinitionId必须非空且唯一。")
    expected = _digest({key: value for key, value in matrix.items() if key != "matrixDigest"})
    if matrix.get("matrixDigest") != expected:
        raise GlobalModulePortCoverageError("全局模组端口覆盖矩阵摘要不匹配。")
    return {
        "success": True,
        "schemaVersion": COVERAGE_MATRIX_SCHEMA,
        "moduleCount": len(modules),
        "connectionPairCount": len(pairs),
        "matrixDigest": expected,
    }


def _resolve_module_reference(
    matrix: dict[str, Any], reference: str
) -> tuple[str | None, list[str]]:
    normalized = str(reference or "").strip().casefold()
    if not normalized:
        return None, []
    matches: list[str] = []
    for row in matrix.get("modules") or []:
        definition_id = str(row.get("moduleDefinitionId") or "")
        candidates = {definition_id.casefold(), *(str(value).casefold() for value in row.get("aliases") or [])}
        if normalized in candidates:
            matches.append(definition_id)
    matches = sorted(set(matches))
    return (matches[0], matches) if len(matches) == 1 else (None, matches)


def assess_module_selection_readiness(
    matrix: dict[str, Any], module_references: Iterable[str]
) -> dict[str, Any]:
    """Assess whether selected module definitions form one CAD-ready semantic subgraph."""

    validate_global_module_port_coverage_matrix(matrix)
    requested = [str(value).strip() for value in module_references if str(value).strip()]
    resolved: list[str] = []
    blockers: list[dict[str, Any]] = []
    for reference in requested:
        definition_id, matches = _resolve_module_reference(matrix, reference)
        if definition_id:
            resolved.append(definition_id)
        elif matches:
            blockers.append(
                {
                    "code": "AMBIGUOUS_MODULE_REFERENCE",
                    "reference": reference,
                    "candidateModuleDefinitionIds": matches,
                }
            )
        else:
            blockers.append({"code": "UNKNOWN_MODULE_REFERENCE", "reference": reference})
    resolved = list(dict.fromkeys(resolved))
    module_by_id = {
        str(row["moduleDefinitionId"]): row for row in matrix.get("modules") or []
    }
    for definition_id in resolved:
        row = module_by_id[definition_id]
        if not row.get("cadEndpointReady"):
            blockers.append(
                {
                    "code": "MODULE_NOT_CAD_ENDPOINT_READY",
                    "moduleDefinitionId": definition_id,
                    "moduleBlockers": row.get("blockers") or [],
                }
            )

    selected = set(resolved)
    adjacency: dict[str, set[str]] = defaultdict(set)
    selected_pairs: list[dict[str, Any]] = []
    for pair in matrix.get("connectionPairs") or []:
        a = str(pair.get("moduleDefinitionIdA") or "")
        b = str(pair.get("moduleDefinitionIdB") or "")
        if a in selected and b in selected and pair.get("cadEndpointReady"):
            adjacency[a].add(b)
            adjacency[b].add(a)
            selected_pairs.append(pair)

    if len(resolved) > 1 and not blockers:
        visited: set[str] = set()
        queue: deque[str] = deque([resolved[0]])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(sorted(adjacency.get(current, set()) - visited))
        missing = sorted(selected - visited)
        if missing:
            blockers.append(
                {
                    "code": "SELECTION_NOT_CONNECTED_BY_CAD_READY_TEMPLATES",
                    "unreachableModuleDefinitionIds": missing,
                }
            )
    if not requested:
        blockers.append({"code": "EMPTY_MODULE_SELECTION"})

    return {
        "schemaVersion": SELECTION_READINESS_SCHEMA,
        "status": "ready" if not blockers else "blocked",
        "requestedModuleReferences": requested,
        "resolvedModuleDefinitionIds": resolved,
        "selectedConnectionPairIds": sorted(str(row["pairId"]) for row in selected_pairs),
        "blockers": blockers,
        "collisionStatus": "not_evaluated",
        "claimBoundary": (
            "ready表示选中模组可由已登记端口和模板连成CAD规划子图，不代表已执行CAD或完成工程验证。"
        ),
    }

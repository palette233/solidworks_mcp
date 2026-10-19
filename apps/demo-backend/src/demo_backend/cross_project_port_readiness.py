"""Audit cross-project semantic-port readiness without inventing missing CAD evidence."""

from __future__ import annotations

from typing import Any, Iterable


def audit_cross_project_port_readiness(
    catalog: dict[str, Any], project_ids: Iterable[str]
) -> dict[str, Any]:
    ports = {
        str(port.get("globalPortId") or ""): port
        for port in catalog.get("semanticPorts") or []
    }
    compatibility = catalog.get("compatibility") or []
    compatible_port_ids = {
        str(row.get(field) or "")
        for row in compatibility
        for field in ("portAId", "portBId")
    }
    projects: list[dict[str, Any]] = []
    for raw_project_id in project_ids:
        project_id = str(raw_project_id).strip().lower()
        rows: list[dict[str, Any]] = []
        for definition in catalog.get("moduleDefinitions") or []:
            aliases = [
                alias
                for alias in definition.get("projectAliases") or []
                if str(alias.get("projectId") or "").lower() == project_id
            ]
            for alias in aliases:
                port_ids = [str(value) for value in definition.get("portIds") or []]
                portable = [
                    port_id for port_id in port_ids if bool((ports.get(port_id) or {}).get("portable"))
                ]
                compatible = [port_id for port_id in port_ids if port_id in compatible_port_ids]
                blockers = []
                if not port_ids:
                    blockers.append("NO_SEMANTIC_PORT")
                elif not compatible:
                    blockers.append("NO_COMPATIBILITY_EDGE")
                rows.append({
                    "moduleToken": alias.get("moduleToken"),
                    "moduleDefinitionId": definition.get("moduleDefinitionId"),
                    "displayName": definition.get("displayName"),
                    "category": definition.get("category"),
                    "portCount": len(port_ids),
                    "portablePortCount": len(portable),
                    "compatiblePortCount": len(compatible),
                    "naturalLanguageSearchable": True,
                    "semanticGraphReady": not blockers,
                    "blockers": blockers,
                })
        blockers: list[str] = []
        if not rows:
            blockers.append("NO_PROJECT_MODULE_PROFILE")
        unready = [row["moduleToken"] for row in rows if not row["semanticGraphReady"]]
        if unready:
            blockers.append("MODULE_PORT_COVERAGE_INCOMPLETE")
        projects.append({
            "projectId": project_id,
            "moduleCount": len(rows),
            "searchableModuleCount": sum(row["naturalLanguageSearchable"] for row in rows),
            "semanticGraphReadyModuleCount": sum(row["semanticGraphReady"] for row in rows),
            "unreadyModuleTokens": unready,
            "status": "ready_for_natural_language_graph_demo" if rows and not unready else "blocked",
            "blockers": blockers,
            "modules": rows,
        })
    ready = [row["projectId"] for row in projects if row["status"].startswith("ready")]
    blocked = [row["projectId"] for row in projects if row["status"] == "blocked"]
    return {
        "schemaVersion": "cross-project-semantic-port-readiness/v1",
        "status": "partial" if ready and blocked else "ready" if ready else "blocked",
        "readyProjectIds": ready,
        "blockedProjectIds": blocked,
        "collisionGateRequired": False,
        "claimBoundary": (
            "ready表示自然语言识别和语义图连接覆盖，不等于跨项目CAD配合端点均已现场重建。"
        ),
        "projects": projects,
    }

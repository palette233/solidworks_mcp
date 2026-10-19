"""Recommend an immutable portable relation release for an existing graph.

The resolver deliberately matches stable semantic port ids instead of project
tokens or prototype poses.  It never mutates the source context: callers must
show the preview and explicitly commit a derived context.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .global_assembly_context import context_digest, validate_global_assembly_context
from .global_relation_catalog_release import (
    GlobalRelationCatalogReleaseError,
    load_relation_catalog_release,
    relation_catalog_release_binding,
)
from .global_relation_semantics import normalize_template_relation_profile


PREVIEW_SCHEMA = "portable-relation-release-recommendation/v1"


class PortableReleaseRecommendationError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _version(release_id: str) -> int:
    match = re.search(r"(?:^|-)v(\d+)(?:-|$)", release_id.casefold())
    return int(match.group(1)) if match else 0


def _authorized_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in (manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or []
        if str(value).strip()
    }


def _match_orientation(
    template: dict[str, Any], port_a_id: str, port_b_id: str
) -> str | None:
    candidates_a = {str(value) for value in template.get("candidatePortIdsA") or []}
    candidates_b = {str(value) for value in template.get("candidatePortIdsB") or []}
    if port_a_id in candidates_a and port_b_id in candidates_b:
        return "same"
    if port_a_id in candidates_b and port_b_id in candidates_a:
        return "swapped"
    return None


def _release_candidate(
    workspace: Path,
    manifest_path: Path,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        catalog, manifest = load_relation_catalog_release(
            manifest_path, workspace_root=workspace
        )
        binding = relation_catalog_release_binding(
            manifest,
            manifest_path=manifest_path,
            workspace_root=workspace,
        )
    except (GlobalRelationCatalogReleaseError, OSError, ValueError, TypeError):
        return None

    definition_ids = {
        str(row.get("moduleDefinitionId") or "")
        for row in catalog.get("moduleDefinitions") or []
    }
    missing_definitions = sorted(
        {
            str(instance.get("moduleDefinitionId") or "")
            for instance in context.get("instances") or []
        }
        - definition_ids
    )
    if missing_definitions:
        return None

    authorized = _authorized_ids(manifest)
    templates = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
        if str(row.get("globalTemplateId") or "") in authorized
    }
    replacements: list[dict[str, Any]] = []
    for connection in context.get("connections") or []:
        port_a_id = str(connection.get("portAId") or "")
        port_b_id = str(connection.get("portBId") or "")
        purpose = str(connection.get("purpose") or "installation")
        matches: list[tuple[str, dict[str, Any]]] = []
        for template in templates.values():
            if purpose not in {str(value) for value in template.get("purposes") or []}:
                continue
            effect = template.get("constraintEffect") or {}
            if effect.get("fullyLocatesAddedComponent") is not True:
                continue
            orientation = _match_orientation(template, port_a_id, port_b_id)
            if orientation:
                matches.append((orientation, template))
        if len(matches) != 1:
            return None
        orientation, template = matches[0]
        replacements.append(
            {
                "connectionId": connection.get("connectionId"),
                "sourceTemplateId": connection.get("globalTemplateId"),
                "portableTemplateId": template.get("globalTemplateId"),
                "orientation": orientation,
                "mateStepCount": len(template.get("mateSteps") or []),
            }
        )

    if not replacements:
        return None
    return {
        "releaseId": manifest.get("releaseId"),
        "releaseVersion": _version(str(manifest.get("releaseId") or "")),
        "releaseManifestPath": binding["releaseManifestPath"],
        "releaseDigest": manifest.get("releaseDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "authorizedTemplateCount": len(authorized),
        "relationReleaseBinding": binding,
        "replacements": replacements,
    }


def recommend_portable_relation_release(
    workspace: Path, context: dict[str, Any]
) -> dict[str, Any]:
    validate_global_assembly_context(context)
    release_root = workspace.resolve() / "demo/global_assembly_catalog/releases"
    candidates = [
        candidate
        for path in sorted(release_root.glob("*/release-manifest.json"))
        if (candidate := _release_candidate(workspace.resolve(), path, context))
        is not None
    ]
    candidates.sort(
        key=lambda row: (
            int(row["authorizedTemplateCount"]),
            -int(row["releaseVersion"]),
            str(row["releaseId"]),
        )
    )
    result = {
        "schemaVersion": PREVIEW_SCHEMA,
        "status": "ready" if candidates else "blocked",
        "sourceContextId": context.get("contextId"),
        "sourceContextRevision": context.get("revision"),
        "sourceContextDigest": context.get("contextDigest"),
        "recommendation": deepcopy(candidates[0]) if candidates else None,
        "alternatives": deepcopy(candidates[1:10]),
        "blockers": []
        if candidates
        else [
            {
                "code": "NO_SINGLE_PORTABLE_RELEASE_COVERS_CONTEXT",
                "detail": (
                    "没有单一不可变发布能以相同语义端口覆盖当前全部连接并独立封闭位姿。"
                ),
            }
        ],
        "selectionPolicy": (
            "先选授权模板数最少的发布，再选版本号最高者；不按项目编号猜测。"
        ),
        "executionBoundary": {
            "sourceContextMutated": False,
            "solidWorksExecuted": False,
            "requiresExplicitCommit": True,
        },
    }
    result["previewDigest"] = _digest(result)
    return result


def build_portable_release_context(
    workspace: Path,
    context: dict[str, Any],
    *,
    expected_preview_digest: str,
    release_id: str,
    target_context_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    preview = recommend_portable_relation_release(workspace, context)
    if preview.get("previewDigest") != expected_preview_digest:
        raise PortableReleaseRecommendationError(
            "便携发布推荐已变化，请刷新预览后重新确认。"
        )
    rows = [preview.get("recommendation"), *(preview.get("alternatives") or [])]
    selected = next(
        (row for row in rows if row and row.get("releaseId") == release_id), None
    )
    if selected is None:
        raise PortableReleaseRecommendationError("所选发布不在当前有效推荐中。")
    target_context_id = str(target_context_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", target_context_id):
        raise PortableReleaseRecommendationError("targetContextId格式非法。")

    manifest_path = workspace.resolve() / str(selected["releaseManifestPath"])
    catalog, manifest = load_relation_catalog_release(
        manifest_path, workspace_root=workspace.resolve()
    )
    binding = relation_catalog_release_binding(
        manifest,
        manifest_path=manifest_path,
        workspace_root=workspace.resolve(),
    )
    templates = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    replacements = {
        str(row["connectionId"]): row for row in selected["replacements"]
    }
    upgraded = deepcopy(context)
    upgraded["contextId"] = target_context_id
    upgraded["displayName"] = f"{context.get('displayName') or context.get('contextId')} · 便携配合发布"
    upgraded["catalogDigest"] = catalog["catalogDigest"]
    upgraded["relationReleaseBinding"] = binding
    for connection in upgraded.get("connections") or []:
        replacement = replacements[str(connection.get("connectionId") or "")]
        if replacement["orientation"] == "swapped":
            connection["instanceAId"], connection["instanceBId"] = (
                connection["instanceBId"],
                connection["instanceAId"],
            )
            connection["portAId"], connection["portBId"] = (
                connection["portBId"],
                connection["portAId"],
            )
        template_id = str(replacement["portableTemplateId"])
        connection["globalTemplateId"] = template_id
        connection["relationProfile"] = normalize_template_relation_profile(
            templates[template_id]
        )
        connection["executionStatus"] = "planned_not_executed_in_cad"

    timestamp = datetime.now(timezone.utc).isoformat()
    source_digest = str(context.get("contextDigest") or "")
    upgraded["revision"] = int(context.get("revision") or 0) + 1
    upgraded["updatedAt"] = timestamp
    upgraded["sourceContext"] = {
        "contextId": context.get("contextId"),
        "revision": context.get("revision"),
        "contextDigest": source_digest,
        "migrationKind": "explicit_portable_release_binding",
    }
    upgraded.setdefault("history", []).append(
        {
            "revision": upgraded["revision"],
            "sourceContextDigest": source_digest,
            "requirement": "将已确认装配图绑定到可独立定位的便携关系发布。",
            "previewDigest": expected_preview_digest,
            "operation": "BIND_PORTABLE_RELATION_RELEASE",
            "releaseId": release_id,
            "timestamp": timestamp,
        }
    )
    upgraded["contextDigest"] = context_digest(upgraded)
    validate_global_assembly_context(upgraded)
    evidence = {
        "schemaVersion": "portable-relation-release-binding/v1",
        "sourceContextId": context.get("contextId"),
        "sourceContextDigest": source_digest,
        "targetContextId": target_context_id,
        "targetContextDigest": upgraded["contextDigest"],
        "releaseId": release_id,
        "releaseDigest": manifest.get("releaseDigest"),
        "previewDigest": expected_preview_digest,
        "replacements": deepcopy(selected["replacements"]),
        "solidWorksExecuted": False,
        "createdAt": timestamp,
    }
    evidence["evidenceDigest"] = _digest(evidence)
    return upgraded, evidence

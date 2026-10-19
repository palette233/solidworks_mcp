"""Prepare one evidence-bound Project05 complete cumulative chain release.

The chain intentionally excludes K000 because the current user-visible scope is:
transport, scanner, CCD, calibration/weighing, cleaning, waste cup and gantry.
All selected modules connect independently to the A000 fixed environment.  The
module never runs SolidWorks; it only combines already published semantic-port
definitions and their existing CAD evidence into one immutable release input.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .global_module_catalog import (
    build_global_module_catalog,
    validate_global_module_catalog,
)


SCHEMA = "project05-complete-cumulative-chain-preparation/v1"
BASE_RELEASE_ID = "relation-v28-project05-all-eight-addon-portable-driving-20261011"
G000_RELEASE_ID = "relation-v58-project05-g000-static-four-relation-driving-20261014"
D000_RELEASE_ID = "relation-v60-project05-d000-deterministic-driving-20261014"
DEFAULT_RELEASE_ID = "relation-v61-project05-complete-seven-addon-driving-20261014"
D000_REFRESH_LEGACY_ID = "D000_to_A000_deterministic_three_mate_v3"

# The order is mechanical/demo intent, not a hidden parser sequence.  Every
# template targets A000, so another supported order may be compiled separately.
MODULE_ORDER = ("D000", "F000", "M000", "G000", "N000", "P000", "B000")

NATURAL_LANGUAGE_REQUIREMENTS = (
    "请建立项目05的设备机架，作为后续模组的固定安装环境。",
    "在当前机架上安装项目05的产品传输模组。",
    "继续安装项目05的双读头条码扫描模组。",
    "继续安装项目05的产品定位CCD模组。",
    "继续安装项目05的喷嘴校准与称重组合模组。",
    "继续安装项目05的自动针头清洁模组。",
    "继续安装项目05的双杯排胶模组。",
    "最后安装项目05的龙门与双阀Z轴运动组。",
)


class Project05CompleteChainError(ValueError):
    pass


def build_d000_deterministic_candidate(
    semantic_catalog: dict[str, Any],
    effective_graph: dict[str, Any],
    *,
    semantic_catalog_path: str,
    endpoint_catalog_path: str,
    effective_graph_path: str,
    initial_placement_variant: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Upgrade the proven D000 mate bundle to an explicit non-source start.

    No face, mate type, distance or width option is changed.  Only the template
    identity/provenance and the insertion experiment policy are refreshed.
    """

    semantic = deepcopy(semantic_catalog)
    graph = deepcopy(effective_graph)
    templates = semantic.get("connectionTemplates") or []
    if len(templates) != 1:
        raise Project05CompleteChainError("D000候选必须只包含一个连接模板。")
    template = templates[0]
    if str(template.get("templateId") or "") != "D000_to_A000_scoped_driving_v2":
        raise Project05CompleteChainError("D000来源模板不是已验证的v2三配合束。")
    template["templateId"] = D000_REFRESH_LEGACY_ID
    template["constraintEffect"] = {
        **(template.get("constraintEffect") or {}),
        "purpose": "Locate D000 from a deterministic non-source initial pose with the proven three-mate bundle.",
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "closed_by_exact_three_mate_bundle",
        "externalPlacementWitnessRequired": True,
        "parameterAuthority": "prototype_source_relation",
        "productionReady": False,
    }
    semantic["catalogPurpose"] = (
        "Project05 A000/D000 deterministic non-source-pose candidate; geometry and "
        "mate parameters are unchanged from the proven v2 bundle."
    )
    semantic["endpointCatalogPath"] = endpoint_catalog_path
    semantic["effectiveMateGraphPath"] = effective_graph_path
    semantic["drivingScope"] = {
        **(semantic.get("drivingScope") or {}),
        "status": "candidate_pending_nonprototype_repeatability",
        "initialPlacementMode": "deterministic",
        "initialPlacementVariant": initial_placement_variant,
        "semanticCatalogPath": semantic_catalog_path,
    }
    policy_key = "EditPolicy" if "EditPolicy" in graph else "editPolicy"
    policy = graph.setdefault(policy_key, {})
    policy["initialPlacementMode"] = "deterministic"
    policy["initialPlacementVariant"] = initial_placement_variant
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    graph["NonPrototypePlacementAudit"] = {
        "mode": "deterministic",
        "variant": initial_placement_variant,
        "sourcePoseAllowed": False,
        "casePoseAnchorAllowed": False,
        "targetLeafPoseAnchorCount": 0,
    }
    return semantic, graph


_SELECTIONS: dict[str, dict[str, Any]] = {
    "D000": {
        "legacyTemplateId": D000_REFRESH_LEGACY_ID,
        "globalTemplateId": "template/project05/d000-to-a000-deterministic-three-mate-v3/741d02e8d3",
        "expectedMateCount": 3,
    },
    "F000": {
        "legacyTemplateId": "F000_to_A000_nonanchor_driving_v1",
        "globalTemplateId": "template/project05/f000-to-a000-nonanchor-driving-v1/d32b6acf6d",
        "expectedMateCount": 3,
    },
    "M000": {
        "legacyTemplateId": "M000_to_A000_nonanchor_driving_v1",
        "globalTemplateId": "template/project05/m000-to-a000-nonanchor-driving-v1/7d60e7bfb4",
        "expectedMateCount": 3,
    },
    "G000": {
        "legacyTemplateId": "G000_to_A000_static_four_relation_v2",
        "globalTemplateId": "template/project05/g000-to-a000-static-four-relation-v2/f738bc665b",
        "expectedMateCount": 4,
    },
    "N000": {
        "legacyTemplateId": "N000_to_A000_nonanchor_driving_v2",
        "globalTemplateId": "template/project05/n000-to-a000-nonanchor-driving-v2/a5c9d7e56f",
        "expectedMateCount": 4,
    },
    "P000": {
        "legacyTemplateId": "P000_to_A000_nonanchor_driving_v2",
        "globalTemplateId": "template/project05/p000-to-a000-nonanchor-driving-v2/fa4ffa064d",
        "expectedMateCount": 4,
    },
    "B000": {
        "legacyTemplateId": "B000_to_A000_nonanchor_driving_v1",
        "globalTemplateId": "template/project05/b000-to-a000-nonanchor-driving-v1/c7e0568d1a",
        "expectedMateCount": 3,
    },
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Project05CompleteChainError(f"JSON根节点必须为对象：{path}")
    return value


def _relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _release_root(workspace: Path, release_id: str) -> Path:
    return workspace / "demo" / "global_assembly_catalog" / "releases" / release_id


def build_candidate_catalog(workspace: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a deterministic catalog containing exactly the current seven drivers."""

    workspace = workspace.resolve()
    v28_root = _release_root(workspace, BASE_RELEASE_ID)
    v58_root = _release_root(workspace, G000_RELEASE_ID)
    v60_root = _release_root(workspace, D000_RELEASE_ID)
    v28_catalog = _read(v28_root / "global_module_catalog.json")
    v58_catalog = _read(v58_root / "global_module_catalog.json")
    v60_catalog = _read(v60_root / "global_module_catalog.json")
    v28_evidence = _read(v28_root / "driving-release-evidence.json")
    v58_evidence = _read(v58_root / "driving-release-evidence.json")
    v60_evidence = _read(v60_root / "driving-release-evidence.json")

    sources_by_id = {
        str(row.get("globalTemplateId") or ""): row
        for row in v28_catalog.get("connectionTemplates") or []
    }
    sources_by_id.update(
        {
            str(row.get("globalTemplateId") or ""): row
            for row in v58_catalog.get("connectionTemplates") or []
        }
    )
    sources_by_id.update(
        {
            str(row.get("globalTemplateId") or ""): row
            for row in v60_catalog.get("connectionTemplates") or []
        }
    )
    semantic_paths: list[Path] = []
    for token in MODULE_ORDER:
        template_id = _SELECTIONS[token]["globalTemplateId"]
        source = sources_by_id.get(template_id)
        if source is None:
            raise Project05CompleteChainError(f"发布目录缺少{token}模板：{template_id}")
        semantic_value = str((source.get("provenance") or {}).get("semanticCatalogPath") or "")
        semantic_path = (workspace / semantic_value).resolve()
        if not semantic_path.is_file():
            raise Project05CompleteChainError(f"{token}语义端口文件不存在：{semantic_path}")
        semantic_paths.append(semantic_path)

    candidate = build_global_module_catalog(
        workspace,
        additional_semantic_catalog_paths=semantic_paths,
    )
    validate_global_module_catalog(candidate)
    candidate_ids = {
        str(row.get("globalTemplateId") or "")
        for row in candidate.get("connectionTemplates") or []
    }
    missing = [
        _SELECTIONS[token]["globalTemplateId"]
        for token in MODULE_ORDER
        if _SELECTIONS[token]["globalTemplateId"] not in candidate_ids
    ]
    if missing:
        raise Project05CompleteChainError(f"候选目录没有保留所选模板：{missing}")

    evidence_sources = {
        **(v28_evidence.get("sourceEvidence") or {}),
        **(v58_evidence.get("sourceEvidence") or {}),
        **(v60_evidence.get("sourceEvidence") or {}),
    }
    provenance = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_immutable_release",
        "baseModuleToken": "A000",
        "moduleOrder": list(MODULE_ORDER),
        "optionalExcludedModules": ["K000"],
        "sourceReleaseIds": [BASE_RELEASE_ID, G000_RELEASE_ID, D000_RELEASE_ID],
        "semanticCatalogPaths": [_relative(workspace, path) for path in semantic_paths],
        "candidateCatalogDigest": candidate["catalogDigest"],
        "collisionStatus": "not_evaluated",
        "dynamicProcessStatus": "not_evaluated",
        "evidenceSources": evidence_sources,
    }
    return candidate, provenance


def build_release_spec(
    workspace: Path,
    *,
    release_id: str,
    candidate_catalog_path: Path,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    v28_evidence = _read(
        _release_root(workspace, BASE_RELEASE_ID) / "driving-release-evidence.json"
    ).get("sourceEvidence") or {}
    v58_evidence = _read(
        _release_root(workspace, G000_RELEASE_ID) / "driving-release-evidence.json"
    ).get("sourceEvidence") or {}
    v60_evidence = _read(
        _release_root(workspace, D000_RELEASE_ID) / "driving-release-evidence.json"
    ).get("sourceEvidence") or {}
    source_evidence = {**v28_evidence, **v58_evidence, **v60_evidence}
    entries = []
    for token in MODULE_ORDER:
        selection = dict(_SELECTIONS[token])
        legacy_id = selection["legacyTemplateId"]
        evidence_key = f"{legacy_id}CheckpointPath"
        evidence_path = source_evidence.get(evidence_key)
        if not evidence_path:
            raise Project05CompleteChainError(f"缺少{token} CAD证据：{evidence_key}")
        entry = {
            **selection,
            "evidencePath": evidence_path,
            "requireDeclaredClosed": True,
        }
        baseline_key = f"{legacy_id}RepeatabilityBaselinePath"
        if source_evidence.get(baseline_key):
            entry["repeatabilityBaselineEvidencePath"] = source_evidence[baseline_key]
        entries.append(entry)
    return {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": release_id,
        "projectId": "project05",
        "drivingScope": "project05_A000_complete_seven_addon_cumulative_chain",
        "catalogPath": _relative(workspace, candidate_catalog_path),
        "templates": entries,
        "authorizedTemplateCombinationIds": [],
    }


def build_scenario(release_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": "natural-language-cumulative-chain-scenario/v1",
        "scenarioId": "project05-complete-seven-addon-v1",
        "releaseId": release_id,
        "baseModuleToken": "A000",
        "expectedPacketOrder": list(MODULE_ORDER),
        "naturalLanguageRequirements": list(NATURAL_LANGUAGE_REQUIREMENTS),
        "acceptance": {
            "nonPrototypeInitialPosePerPacket": True,
            "realMateCreationPerPacket": True,
            "saveCloseReopenPerPacket": True,
            "sourceAssemblyUnchangedPerPacket": True,
            "collisionOrBrepRequired": False,
            "dynamicProcessRequired": False,
        },
        "excludedOptionalModules": [
            {
                "moduleToken": "K000",
                "reason": "双工位顶升定位模组不在本轮用户指定的七类附加模组内。",
            }
        ],
    }


def audit_complete_chain_manifest(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    expected_release_id: str,
    expected_order: tuple[str, ...] = MODULE_ORDER,
) -> dict[str, Any]:
    """Reject source-pose/anchor shortcuts before an expensive CAD run."""

    workspace = workspace.resolve()
    release = manifest.get("relationReleaseBinding") or {}
    authorized = set(release.get("authorizedDrivingTemplateIds") or [])
    packets = manifest.get("packets") or []
    packet_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    actual_order: list[str] = []
    for index, packet in enumerate(packets, start=1):
        aliases = packet.get("targetProjectAliases") or []
        token = str((aliases[0] if aliases else {}).get("moduleToken") or "").upper()
        actual_order.append(token)
        connections = packet.get("connections") or []
        connection = connections[0] if len(connections) == 1 else {}
        template_id = str(connection.get("globalTemplateId") or "")
        graph_value = str(connection.get("effectiveMateGraphCandidate") or "")
        graph_path = Path(graph_value)
        if not graph_path.is_absolute():
            graph_path = (workspace / graph_path).resolve()
        graph = _read(graph_path) if graph_path.is_file() else {}
        policy = graph.get("EditPolicy") or graph.get("editPolicy") or {}
        initial_mode = str(policy.get("initialPlacementMode") or "")
        case_anchors = list(policy.get("caseAnchoredModuleTokens") or [])
        leaf_anchors = list(policy.get("targetLeafPoseAnchors") or [])
        expected_input = "base_module_source" if index == 1 else "previous_transaction_checkpoint"
        packet_blockers: list[str] = []
        if len(connections) != 1:
            packet_blockers.append("packet_must_have_exactly_one_connection")
        if template_id not in authorized:
            packet_blockers.append("template_not_authorized_by_release")
        if initial_mode not in {"deterministic", "deterministic_non_source_pose"}:
            packet_blockers.append(f"forbidden_initial_placement_mode:{initial_mode or 'missing'}")
        if case_anchors:
            packet_blockers.append("case_pose_anchor_present")
        if leaf_anchors:
            packet_blockers.append("target_leaf_pose_anchor_present")
        if not graph_path.is_file():
            packet_blockers.append("effective_graph_missing")
        if (packet.get("cumulativeInput") or {}).get("kind") != expected_input:
            packet_blockers.append("cumulative_input_kind_mismatch")
        if packet.get("blockers"):
            packet_blockers.append("packet_has_compiler_blockers")
        blockers.extend(f"packet-{index:03d}:{value}" for value in packet_blockers)
        packet_rows.append(
            {
                "packetId": packet.get("packetId"),
                "moduleToken": token,
                "globalTemplateId": template_id,
                "effectiveGraphPath": str(graph_path),
                "initialPlacementMode": initial_mode,
                "casePoseAnchorCount": len(case_anchors),
                "targetLeafPoseAnchorCount": len(leaf_anchors),
                "cumulativeInputKind": (packet.get("cumulativeInput") or {}).get("kind"),
                "passed": not packet_blockers,
                "blockers": packet_blockers,
            }
        )
    expected = [str(value).upper() for value in expected_order]
    if actual_order != expected:
        blockers.append("module_order_mismatch")
    if release.get("releaseId") != expected_release_id:
        blockers.append("release_id_mismatch")
    collision_statuses = sorted(
        {
            str((packet.get("collisionAssessment") or {}).get("status") or "unknown")
            for packet in packets
        }
    )
    return {
        "schemaVersion": "complete-cumulative-chain-preflight-audit/v1",
        "status": "passed" if not blockers else "blocked",
        "releaseId": release.get("releaseId"),
        "expectedModuleOrder": expected,
        "actualModuleOrder": actual_order,
        "packetCount": len(packets),
        "packets": packet_rows,
        "collisionStatus": (
            collision_statuses[0]
            if len(collision_statuses) == 1
            else "mixed"
        ),
        "collisionIncludedInPreflightDecision": False,
        "blockers": blockers,
    }


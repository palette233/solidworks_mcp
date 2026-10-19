"""Publish immutable driving-relation releases from a declarative evidence list.

The publisher replaces project- and chain-length-specific evidence scripts.  It
does not run SolidWorks; it verifies already captured CAD evidence, the catalog
semantics and optional inventory classification before authorizing templates.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .global_cad_driving_evidence import (
    assess_driving_insert_evidence,
    assess_external_placement_repeatability,
)
from .global_module_catalog import validate_global_module_catalog
from .global_relation_catalog_release import (
    build_relation_catalog_release,
    finalize_relation_catalog_release,
)
from .global_relation_semantics import normalize_template_relation_profile


SCHEMA = "driving-relation-release-publication/v1"
SPEC_SCHEMA = "driving-relation-release-spec/v1"


class DrivingRelationReleasePublisherError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrivingRelationReleasePublisherError(
            f"无法读取发布输入：{path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise DrivingRelationReleasePublisherError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(workspace: Path, value: str, field: str) -> Path:
    if not str(value or "").strip():
        raise DrivingRelationReleasePublisherError(f"{field}不能为空。")
    candidate = Path(value)
    result = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    if not result.is_file():
        raise DrivingRelationReleasePublisherError(f"{field}文件不存在：{result}")
    return result


def _relative_or_absolute(workspace: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def publish_driving_relation_release(
    workspace: Path,
    spec: dict[str, Any],
    *,
    output_root: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    if spec.get("schemaVersion") != SPEC_SCHEMA:
        raise DrivingRelationReleasePublisherError("不支持的驱动关系发布规格版本。")
    release_id = str(spec.get("releaseId") or "").strip()
    project_id = str(spec.get("projectId") or "").strip()
    driving_scope = str(spec.get("drivingScope") or "").strip()
    if not release_id or not project_id or not driving_scope:
        raise DrivingRelationReleasePublisherError(
            "releaseId、projectId和drivingScope不能为空。"
        )
    catalog_path = _resolve(workspace, str(spec.get("catalogPath") or ""), "catalogPath")
    catalog = _read(catalog_path)
    validate_global_module_catalog(catalog)
    template_by_id = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    combination_by_id = {
        str(row.get("globalCombinationId") or ""): row
        for row in catalog.get("templateCombinations") or []
    }

    inventory = None
    inventory_candidates: set[str] | None = None
    inventory_value = str(spec.get("inventoryPath") or "").strip()
    inventory_path = None
    if inventory_value:
        inventory_path = _resolve(workspace, inventory_value, "inventoryPath")
        inventory = _read(inventory_path)
        inventory_candidates = {
            str(row.get("globalTemplateId") or "")
            for row in inventory.get("templates") or []
            if row.get("cadEvidenceState") == "release_candidate"
        }

    entries = spec.get("templates")
    if not isinstance(entries, list) or not entries:
        raise DrivingRelationReleasePublisherError("templates必须是非空数组。")
    checks: dict[str, bool] = {}
    if inventory is not None:
        checks["catalogDigestMatchesInventory"] = (
            inventory.get("catalogDigest") == catalog.get("catalogDigest")
        )
    derivations = []
    assessments: dict[str, dict[str, Any]] = {}
    evidence_paths: list[Path] = []
    authorized_ids: list[str] = []
    source_evidence: dict[str, Any] = {}
    if inventory_path is not None:
        source_evidence["inventoryPath"] = _relative_or_absolute(
            workspace, inventory_path
        )

    topology_audit_path = None
    topology_audit_project = None
    topology_value = str(spec.get("relationTopologyAuditPath") or "").strip()
    required_mechanical_edges = spec.get("requiredMechanicalEdges") or []
    if required_mechanical_edges and not topology_value:
        raise DrivingRelationReleasePublisherError(
            "requiredMechanicalEdges必须同时提供relationTopologyAuditPath。"
        )
    if topology_value:
        topology_audit_path = _resolve(
            workspace, topology_value, "relationTopologyAuditPath"
        )
        topology_audit = _read(topology_audit_path)
        if topology_audit.get("schemaVersion") != (
            "cross-project-relation-topology-audit/v1"
        ):
            raise DrivingRelationReleasePublisherError("关系拓扑审计版本不受支持。")
        topology_audit_project = next(
            (
                row
                for row in topology_audit.get("projects") or []
                if str(row.get("projectId") or "").lower() == project_id.lower()
            ),
            None,
        )
        if topology_audit_project is None:
            raise DrivingRelationReleasePublisherError(
                f"关系拓扑审计缺少项目：{project_id}"
            )
        source_evidence["relationTopologyAuditPath"] = _relative_or_absolute(
            workspace, topology_audit_path
        )
        mechanical_edges = {
            tuple(sorted(str(value).upper() for value in row.get("moduleTokens") or [])): row
            for row in topology_audit_project.get("mechanicalEdges") or []
            if len(row.get("moduleTokens") or []) == 2
        }
        for index, requirement in enumerate(required_mechanical_edges, start=1):
            if not isinstance(requirement, dict):
                raise DrivingRelationReleasePublisherError(
                    f"requiredMechanicalEdges[{index}]必须是对象。"
                )
            tokens = tuple(
                sorted(str(value).upper() for value in requirement.get("moduleTokens") or [])
            )
            if len(tokens) != 2 or tokens[0] == tokens[1]:
                raise DrivingRelationReleasePublisherError(
                    f"requiredMechanicalEdges[{index}].moduleTokens必须包含两个不同模组。"
                )
            edge = mechanical_edges.get(tokens)
            key = f"mechanicalEdge:{tokens[0]}+{tokens[1]}"
            checks[f"{key}:observed"] = edge is not None
            if requirement.get("requirePoseAnchorFreeEvidence", True):
                checks[f"{key}:poseAnchorFree"] = bool(
                    edge and edge.get("hasPoseAnchorFreeEvidence") is True
                )

    seen_ids: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise DrivingRelationReleasePublisherError(
                f"templates[{index}]必须是对象。"
            )
        template_id = str(entry.get("globalTemplateId") or "").strip()
        legacy_id = str(entry.get("legacyTemplateId") or "").strip()
        if not template_id or not legacy_id:
            raise DrivingRelationReleasePublisherError(
                f"templates[{index}]缺少globalTemplateId或legacyTemplateId。"
            )
        if template_id in seen_ids:
            raise DrivingRelationReleasePublisherError(f"模板重复：{template_id}")
        seen_ids.add(template_id)
        template = template_by_id.get(template_id)
        if template is None:
            raise DrivingRelationReleasePublisherError(f"候选目录缺少模板：{template_id}")
        if str(template.get("legacyTemplateId") or "") != legacy_id:
            raise DrivingRelationReleasePublisherError(
                f"模板编号与legacyTemplateId不匹配：{template_id}"
            )
        evidence_path = _resolve(
            workspace, str(entry.get("evidencePath") or ""), "evidencePath"
        )
        expected_mate_count = int(entry.get("expectedMateCount") or 0)
        if expected_mate_count <= 0:
            raise DrivingRelationReleasePublisherError(
                f"{legacy_id}的expectedMateCount必须大于0。"
            )
        assessment = assess_driving_insert_evidence(
            _read(evidence_path), expected_mate_count=expected_mate_count
        )
        repeatability_assessment = None
        baseline_value = str(entry.get("repeatabilityBaselineEvidencePath") or "").strip()
        if baseline_value:
            baseline_path = _resolve(
                workspace,
                baseline_value,
                "repeatabilityBaselineEvidencePath",
            )
            confirmation_payload = _read(evidence_path)
            confirmation_graph_path = _resolve(
                workspace,
                str(confirmation_payload.get("executionEffectiveGraphPath") or ""),
                "confirmation.executionEffectiveGraphPath",
            )
            repeatability_assessment = assess_external_placement_repeatability(
                _read(baseline_path),
                confirmation_payload,
                _read(confirmation_graph_path),
                expected_mate_count=expected_mate_count,
            )
            checks[f"{legacy_id}:externalPlacementRepeatability"] = (
                repeatability_assessment.get("passed") is True
            )
            evidence_paths.append(baseline_path)
            source_evidence[
                f"{legacy_id}RepeatabilityBaselinePath"
            ] = _relative_or_absolute(workspace, baseline_path)
        profile = normalize_template_relation_profile(template)
        explanation = profile.get("constraintExplanation") or {}
        checks[f"{legacy_id}:drivesPlacement"] = (
            profile.get("drivesPlacement") is True
        )
        if bool(entry.get("requireDeclaredClosed", True)):
            checks[f"{legacy_id}:declaredClosed"] = (
                explanation.get("state") == "declared_closed"
                and explanation.get("expectedResidualDof") == 0
            )
        checks[f"{legacy_id}:checkpointPassed"] = (
            assessment.get("checkpointPassed") is True
        )
        if bool((template.get("constraintEffect") or {}).get("internalFlexibilityPreserved")):
            checks[f"{legacy_id}:externalPlacementEquivalence"] = (
                assessment.get("portablePlacementProven") is True
            )
        if inventory_candidates is not None:
            checks[f"{legacy_id}:inventoryCandidate"] = (
                template_id in inventory_candidates
            )
        if repeatability_assessment is not None:
            assessment = dict(assessment)
            assessment["externalPlacementRepeatability"] = repeatability_assessment
        assessments[legacy_id] = assessment
        evidence_paths.append(evidence_path)
        authorized_ids.append(template_id)
        derivations.append(
            {
                "entry": {
                    "mode": "register_scoped_driving_bundle",
                    "sourceProjectId": project_id,
                    "legacyTemplateId": legacy_id,
                },
                "result": {
                    "derivedGlobalTemplateId": template_id,
                    "drivingScope": driving_scope,
                },
            }
        )
        source_evidence[f"{legacy_id}CheckpointPath"] = _relative_or_absolute(
            workspace, evidence_path
        )

    # One real CAD checkpoint may prove an exact multi-template bundle.  Keep
    # the per-template assessments above, but publish the immutable evidence
    # file only once so the release manifest reflects the number of distinct
    # CAD runs rather than the number of template members.
    evidence_paths = list(dict.fromkeys(path.resolve() for path in evidence_paths))
    authorized_combination_ids = sorted(
        {
            str(value).strip()
            for value in spec.get("authorizedTemplateCombinationIds") or []
            if str(value).strip()
        }
    )
    for combination_id in authorized_combination_ids:
        combination = combination_by_id.get(combination_id)
        checks[f"{combination_id}:exists"] = combination is not None
        if combination is None:
            continue
        members = {
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        }
        checks[f"{combination_id}:membersAuthorized"] = bool(members) and members.issubset(
            set(authorized_ids)
        )
        checks[f"{combination_id}:exactClosed"] = bool(
            combination.get("exactMemberSetRequired") is True
            and combination.get("fullyLocatesAddedComponent") is True
            and int(combination.get("expectedResidualDof", -1)) == 0
        )

    candidate = {
        "schemaVersion": "generic-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if all(checks.values()) else "blocked",
        "projectId": project_id,
        "drivingScope": driving_scope,
        "sourceCatalogPath": _relative_or_absolute(workspace, catalog_path),
        "outputCatalogDigest": catalog["catalogDigest"],
        "authorizedDrivingTemplateIds": sorted(authorized_ids),
        "authorizedTemplateCombinationIds": authorized_combination_ids,
        "checks": checks,
        "derivations": derivations,
        "sourceEvidence": source_evidence,
        "relationTopologyAudit": {
            "schemaVersion": "relation-topology-release-attestation/v1",
            "path": _relative_or_absolute(workspace, topology_audit_path),
            "fileSha256": _file_sha256(topology_audit_path),
            "projectId": project_id,
            "projectTopologyDigest": _digest(topology_audit_project),
            "requiredMechanicalEdges": required_mechanical_edges,
            "portableNonStarMechanicalEdgeCount": topology_audit_project.get(
                "portableNonStarMechanicalEdgeCount"
            ),
        }
        if topology_audit_path is not None
        else None,
        "cadAssessments": assessments,
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
        "specDigest": _digest(spec),
        "statement": (
            "仅发布已通过非原型初始位姿、配合求解、保存关闭重开与源文件不变检查的驱动模板。"
        ),
    }
    if candidate["status"] != "ready":
        raise DrivingRelationReleasePublisherError(
            "驱动证据未通过："
            + ", ".join(key for key, value in checks.items() if value is not True)
        )

    destination_root = (output_root or workspace / "demo/global_assembly_catalog/releases").resolve()
    output = destination_root / release_id
    if output.exists() and not overwrite:
        raise DrivingRelationReleasePublisherError(
            f"发布目录已存在；不可变发布禁止覆盖：{output}"
        )
    output.mkdir(parents=True, exist_ok=True)
    evidence_output = output / "driving-release-evidence.json"
    catalog_output = output / "global_module_catalog.json"
    manifest_output = output / "release-manifest.json"
    _write(evidence_output, candidate)
    released_catalog, manifest = build_relation_catalog_release(
        catalog_path=catalog_path,
        derivation_evidence_path=evidence_output,
        validation_evidence_paths=evidence_paths,
        release_id=release_id,
        authorized_driving_template_ids=authorized_ids,
        authorized_template_combination_ids=(
            candidate["authorizedTemplateCombinationIds"]
        ),
    )
    _write(catalog_output, released_catalog)
    manifest = finalize_relation_catalog_release(
        manifest,
        released_catalog_path=catalog_output,
        workspace_root=workspace,
    )
    _write(manifest_output, manifest)
    report = {
        "schemaVersion": SCHEMA,
        "success": True,
        "status": manifest["status"],
        "releaseId": release_id,
        "projectId": project_id,
        "catalogDigest": manifest["catalogDigest"],
        "authorizedDrivingTemplateIds": sorted(authorized_ids),
        "authorizedTemplateCombinationIds": candidate[
            "authorizedTemplateCombinationIds"
        ],
        "templateCount": len(authorized_ids),
        "validationEvidenceCount": len(evidence_paths),
        "candidateEvidencePath": str(evidence_output),
        "catalogPath": str(catalog_output),
        "manifestPath": str(manifest_output),
        "releaseDigest": manifest["releaseDigest"],
        "relationTopologyAttested": bool(candidate.get("relationTopologyAudit")),
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
    }
    _write(output / "publication-report.json", report)
    return report

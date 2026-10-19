"""Build an immutable demo release for registered relation templates."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .global_module_catalog import validate_global_module_catalog
from .global_relation_semantics import normalize_template_relation_profile
from .relation_execution_policy import (
    DATUM_PLACEMENT_DEMO,
    DIRECT_INSTALLATION,
    SUPPORTED_RELATION_EXECUTION_MODES,
    template_evidence_class,
)


class GlobalRelationCatalogReleaseError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _validation_passed(payload: dict[str, Any]) -> bool:
    if payload.get("status") == "passed":
        checks = payload.get("checks") or {}
        return bool(checks) and all(value is True for value in checks.values())
    if payload.get("success") is True:
        if payload.get("schemaVersion") == "context-incremental-insert-run/v1":
            tool = payload.get("toolResult") or {}
            requested = int(tool.get("RequestedMateCount") or 0)
            created = int(tool.get("CreatedMateCount") or 0)
            mate_results = tool.get("MateResults") or []
            verifications = tool.get("MateVerifications") or []
            return bool(
                tool.get("Success") is True
                and tool.get("ExecutionMode") == "context_incremental_insert"
                and tool.get("IndependentComponentInserted") is True
                and requested > 0
                and created == requested
                and tool.get("Reopened") is True
                and tool.get("ReopenedMateParametersMatch") is True
                and tool.get("TargetConstraintStateAccepted") is True
                and tool.get("MateSolveClean") is True
                and tool.get("ComponentSemanticsMatch") is True
                and len(mate_results) == requested
                and all(row.get("Success") is True for row in mate_results)
                and len(verifications) == requested
                and all(
                    row.get("Found") is True
                    and row.get("TypeMatches") is True
                    and row.get("AlignmentMatches") is True
                    and row.get("DistanceMatches") is True
                    and row.get("AngleMatches") is True
                    and row.get("AdvancedOptionsMatch") is True
                    for row in verifications
                )
            )
        if payload.get("schemaVersion") == "context-direct-mate-edit-run/v1":
            tool = payload.get("toolResult") or {}
            requested = int(tool.get("RequestedMateCount") or 0)
            created = int(tool.get("CreatedMateCount") or 0)
            mate_results = tool.get("MateResults") or []
            verifications = tool.get("MateVerifications") or []
            return bool(
                payload.get("published") is True
                and payload.get("sourceAssemblyUnchanged") is True
                and tool.get("Success") is True
                and requested > 0
                and created == requested
                and tool.get("Reopened") is True
                and tool.get("ReopenedMateParametersMatch") is True
                and tool.get("TargetFullyConstrained") is True
                and tool.get("ComponentSemanticsMatch") is True
                and len(mate_results) == requested
                and all(row.get("Success") is True for row in mate_results)
                and len(verifications) == requested
                and all(
                    row.get("Found") is True
                    and row.get("TypeMatches") is True
                    and row.get("AlignmentMatches") is True
                    and row.get("DistanceMatches") is True
                    and row.get("AngleMatches") is True
                    and row.get("AdvancedOptionsMatch") is True
                    for row in verifications
                )
            )
        if payload.get("schemaVersion") == "checkpoint-selected-face-context-insert-run/v1":
            tool = payload.get("toolResult") or {}
            requested = int(tool.get("RequestedMateCount") or 0)
            created = int(tool.get("CreatedMateCount") or 0)
            mate_results = tool.get("MateResults") or []
            verifications = tool.get("MateVerifications") or []
            return bool(
                payload.get("sourceAssemblyUnchanged") is True
                and payload.get("outputAssemblySha256")
                and payload.get("outputClosedAfterVerification") is True
                # A target source document that was already open before the
                # checkpoint must remain open; cleanliness, not forced close,
                # is the invariant.  Newly opened target sources are still
                # closed by the checkpoint runner before this flag is set.
                and payload.get("targetSourceSessionClean") is True
                and tool.get("Success") is True
                and tool.get("ExecutionMode") == "context_incremental_insert"
                and tool.get("OriginalComponentRemoved") is True
                and tool.get("IndependentComponentInserted") is True
                and tool.get("TargetCaseAnchored") is False
                and requested > 0
                and created == requested
                and tool.get("Reopened") is True
                and tool.get("ReopenedMateParametersMatch") is True
                and tool.get("TargetConstraintStateAccepted") is True
                and tool.get("MateSolveClean") is True
                and tool.get("ComponentSemanticsMatch") is True
                and len(mate_results) == requested
                and all(row.get("Success") is True for row in mate_results)
                and len(verifications) == requested
                and all(
                    row.get("Found") is True
                    and row.get("TypeMatches") is True
                    and row.get("AlignmentMatches") is True
                    and row.get("DistanceMatches") is True
                    and row.get("AngleMatches") is True
                    and row.get("AdvancedOptionsMatch") is True
                    for row in verifications
                )
            )
        rows = payload.get("validationResults") or []
        return bool(rows) and all(
            row.get("EndpointsResolved") is True and row.get("Passed") is True
            for row in rows
        )
    return False


def _driving_initial_pose_validation_passed(payload: dict[str, Any]) -> bool:
    """Require proof that mates, rather than a fixed/source pose, locate the target."""

    if payload.get("schemaVersion") in {
        "checkpoint-selected-face-context-insert-run/v1",
        "context-incremental-insert-run/v1",
    }:
        tool = payload.get("toolResult") or {}
        return bool(
            _validation_passed(payload)
            and tool.get("OriginalComponentRemoved") is True
            and tool.get("IndependentComponentInserted") is True
            and tool.get("TargetCaseAnchored") is False
        )
    if payload.get("schemaVersion") != "context-direct-mate-edit-run/v1":
        return False
    tool = payload.get("toolResult") or {}
    displacement = tool.get("InitialDisplacementMaximumElementDelta")
    return_error = tool.get("ReturnToSourcePoseMaximumElementError")
    return bool(
        _validation_passed(payload)
        and tool.get("TargetComponentExplicitlyDisplaced") is True
        and isinstance(displacement, (int, float))
        and float(displacement) > 1e-8
        and tool.get("TargetReturnedToSourcePose") is True
        and isinstance(return_error, (int, float))
        and float(return_error) <= 1e-8
    )


def build_relation_catalog_release(
    *,
    catalog_path: Path,
    derivation_evidence_path: Path,
    validation_evidence_paths: list[Path],
    release_id: str,
    authorized_driving_template_ids: list[str] | None = None,
    authorized_template_combination_ids: list[str] | None = None,
    release_metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog_path = catalog_path.resolve()
    derivation_evidence_path = derivation_evidence_path.resolve()
    validation_evidence_paths = [path.resolve() for path in validation_evidence_paths]
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    derivation = json.loads(derivation_evidence_path.read_text(encoding="utf-8-sig"))
    validate_global_module_catalog(catalog)
    if derivation.get("status") != "ready":
        raise GlobalRelationCatalogReleaseError("关系派生证据未就绪。")
    if derivation.get("outputCatalogDigest") != catalog.get("catalogDigest"):
        raise GlobalRelationCatalogReleaseError("派生证据与候选目录摘要不一致。")

    validation_rows = []
    for path in validation_evidence_paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        passed = _validation_passed(payload)
        validation_rows.append(
            {
                "path": str(path),
                "fileSha256": _file_sha256(path),
                "schemaVersion": payload.get("schemaVersion"),
                "passed": passed,
                "drivingInitialPoseIndependent": (
                    _driving_initial_pose_validation_passed(payload)
                ),
                "jobId": payload.get("jobId"),
            }
        )
    if not validation_rows or not all(row["passed"] for row in validation_rows):
        raise GlobalRelationCatalogReleaseError("存在未通过的真实CAD关系验证证据。")

    derivations = derivation.get("derivations") or []
    derived_ids = sorted(
        str((row.get("result") or {}).get("derivedGlobalTemplateId") or "")
        for row in derivations
    )
    catalog_ids = {
        str(row.get("globalTemplateId") or "")
        for row in catalog.get("connectionTemplates") or []
    }
    if not derived_ids or any(template_id not in catalog_ids for template_id in derived_ids):
        raise GlobalRelationCatalogReleaseError("候选目录缺少已登记的派生模板。")

    authorized_driving_ids = sorted(
        {
            str(value).strip()
            for value in (authorized_driving_template_ids or [])
            if str(value).strip()
        }
    )
    if any(template_id not in derived_ids for template_id in authorized_driving_ids):
        raise GlobalRelationCatalogReleaseError(
            "驱动授权只能授予本发布版已派生且已验证的模板。"
        )
    template_by_id = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    non_driving = [
        template_id
        for template_id in authorized_driving_ids
        if normalize_template_relation_profile(template_by_id[template_id]).get(
            "drivesPlacement"
        )
        is not True
    ]
    if non_driving:
        raise GlobalRelationCatalogReleaseError(
            f"模板未声明可驱动位姿，不能授权：{', '.join(non_driving)}"
        )
    if authorized_driving_ids and not any(
        row["drivingInitialPoseIndependent"] for row in validation_rows
    ):
        raise GlobalRelationCatalogReleaseError(
            "驱动授权缺少非原型初始位姿CAD证据；原位替换配合不能证明位姿由配合求解。"
        )

    authorized_combination_ids = sorted(
        {
            str(value).strip()
            for value in (authorized_template_combination_ids or [])
            if str(value).strip()
        }
    )
    combination_by_id = {
        str(row.get("globalCombinationId") or ""): row
        for row in catalog.get("templateCombinations") or []
    }
    missing_combinations = [
        value for value in authorized_combination_ids if value not in combination_by_id
    ]
    if missing_combinations:
        raise GlobalRelationCatalogReleaseError(
            "组合授权引用了目录中不存在的模板组合："
            + ", ".join(missing_combinations)
        )
    for combination_id in authorized_combination_ids:
        combination = combination_by_id[combination_id]
        members = {
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        }
        if not members or not members.issubset(set(authorized_driving_ids)):
            raise GlobalRelationCatalogReleaseError(
                "组合授权的全部成员模板必须同时取得逐模板驱动授权。"
            )
        if not members.issubset(set(derived_ids)):
            raise GlobalRelationCatalogReleaseError(
                "组合授权只能引用本发布版已派生模板。"
            )
        if (
            combination.get("exactMemberSetRequired") is not True
            or combination.get("fullyLocatesAddedComponent") is not True
            or int(combination.get("expectedResidualDof", -1)) != 0
        ):
            raise GlobalRelationCatalogReleaseError(
                "组合授权必须声明精确成员集、完整定位和零剩余自由度。"
            )

    manifest_core = {
        "schemaVersion": "global-relation-catalog-release/v1",
        "releaseId": str(release_id),
        "status": "released_for_demo_relation_execution",
        "productionReady": False,
        "catalogDigest": catalog["catalogDigest"],
        "catalogSourcePath": str(catalog_path),
        "catalogSourceFileSha256": _file_sha256(catalog_path),
        "derivationEvidencePath": str(derivation_evidence_path),
        "derivationEvidenceFileSha256": _file_sha256(derivation_evidence_path),
        "derivedTemplateIds": derived_ids,
        "validationEvidence": validation_rows,
        "scope": {
            "naturalLanguageRelationSelection": True,
            "readOnlyCadVerification": True,
            "drivingRelationRelease": bool(authorized_driving_ids),
            "authorizedDrivingTemplateIds": authorized_driving_ids,
            "authorizedTemplateCombinationIds": authorized_combination_ids,
            "collisionOrBrepRelease": False,
        },
    }
    if release_metadata is not None:
        metadata = deepcopy(release_metadata)
        _validate_release_metadata(
            metadata,
            template_by_id=template_by_id,
            authorized_template_ids=authorized_driving_ids,
        )
        manifest_core["releaseMetadata"] = metadata
    topology_attestation = derivation.get("relationTopologyAudit")
    if topology_attestation is not None:
        if topology_attestation.get("schemaVersion") != (
            "relation-topology-release-attestation/v1"
        ):
            raise GlobalRelationCatalogReleaseError("关系拓扑发布证明版本不受支持。")
        manifest_core["relationTopologyAttestation"] = deepcopy(topology_attestation)
    manifest = dict(manifest_core)
    manifest["releaseDigest"] = _digest(manifest_core)
    return catalog, manifest


def finalize_relation_catalog_release(
    manifest: dict[str, Any],
    *,
    released_catalog_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    """Bind a release manifest to the immutable catalog copy written to disk.

    The builder intentionally does not know where callers will publish the
    catalog.  Finalization adds both an absolute audit path and a repository-
    relative portable path, hashes the published bytes, and then recomputes the
    release digest over the complete manifest.
    """

    released_catalog_path = released_catalog_path.resolve()
    workspace_root = workspace_root.resolve()
    if not released_catalog_path.is_file():
        raise GlobalRelationCatalogReleaseError("发布目录文件不存在。")
    try:
        relative_path = released_catalog_path.relative_to(workspace_root)
    except ValueError as exc:
        raise GlobalRelationCatalogReleaseError("发布目录必须位于工作区内。") from exc

    catalog = json.loads(released_catalog_path.read_text(encoding="utf-8-sig"))
    validate_global_module_catalog(catalog)
    if catalog.get("catalogDigest") != manifest.get("catalogDigest"):
        raise GlobalRelationCatalogReleaseError("发布目录与清单摘要不一致。")

    result = deepcopy(manifest)
    result.pop("releaseDigest", None)
    result["releasedCatalogPath"] = str(released_catalog_path)
    result["releasedCatalogRelativePath"] = relative_path.as_posix()
    result["releasedCatalogFileSha256"] = _file_sha256(released_catalog_path)
    result["releaseDigest"] = _digest(result)
    return result


def load_relation_catalog_release(
    manifest_path: Path,
    *,
    workspace_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and verify one finalized relation catalog release."""

    manifest_path = manifest_path.resolve()
    workspace_root = workspace_root.resolve()
    try:
        manifest_path.relative_to(workspace_root)
    except ValueError as exc:
        raise GlobalRelationCatalogReleaseError("关系发布清单必须位于工作区内。") from exc
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalRelationCatalogReleaseError(f"无法读取关系发布清单：{exc}") from exc
    if manifest.get("schemaVersion") != "global-relation-catalog-release/v1":
        raise GlobalRelationCatalogReleaseError("不支持的关系发布清单版本。")
    if manifest.get("status") != "released_for_demo_relation_execution":
        raise GlobalRelationCatalogReleaseError("关系目录尚未发布为Demo可执行版本。")

    expected_release_digest = _digest(
        {key: value for key, value in manifest.items() if key != "releaseDigest"}
    )
    if manifest.get("releaseDigest") != expected_release_digest:
        raise GlobalRelationCatalogReleaseError("关系发布清单摘要不匹配。")

    topology = manifest.get("relationTopologyAttestation")
    if topology is not None:
        if topology.get("schemaVersion") != "relation-topology-release-attestation/v1":
            raise GlobalRelationCatalogReleaseError("关系拓扑发布证明版本不受支持。")
        topology_path_value = str(topology.get("path") or "").strip()
        if not topology_path_value:
            raise GlobalRelationCatalogReleaseError("关系拓扑发布证明缺少路径。")
        topology_path = Path(topology_path_value)
        if not topology_path.is_absolute():
            topology_path = (workspace_root / topology_path).resolve()
        try:
            topology_path.relative_to(workspace_root)
        except ValueError as exc:
            raise GlobalRelationCatalogReleaseError("关系拓扑审计路径越出工作区。") from exc
        if not topology_path.is_file() or _file_sha256(topology_path) != topology.get(
            "fileSha256"
        ):
            raise GlobalRelationCatalogReleaseError("关系拓扑审计文件缺失或摘要不匹配。")
        topology_payload = json.loads(topology_path.read_text(encoding="utf-8-sig"))
        project_id = str(topology.get("projectId") or "").lower()
        project_row = next(
            (
                row
                for row in topology_payload.get("projects") or []
                if str(row.get("projectId") or "").lower() == project_id
            ),
            None,
        )
        if project_row is None or _digest(project_row) != topology.get(
            "projectTopologyDigest"
        ):
            raise GlobalRelationCatalogReleaseError("关系拓扑项目证明缺失或摘要不匹配。")

    relative_value = str(manifest.get("releasedCatalogRelativePath") or "").strip()
    if not relative_value:
        raise GlobalRelationCatalogReleaseError("关系发布清单缺少可迁移目录路径。")
    catalog_path = (workspace_root / Path(relative_value)).resolve()
    try:
        catalog_path.relative_to(workspace_root)
    except ValueError as exc:
        raise GlobalRelationCatalogReleaseError("发布目录路径越出工作区。") from exc
    if not catalog_path.is_file():
        raise GlobalRelationCatalogReleaseError("发布目录文件不存在。")
    if _file_sha256(catalog_path) != manifest.get("releasedCatalogFileSha256"):
        raise GlobalRelationCatalogReleaseError("发布目录文件摘要不匹配。")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    validate_global_module_catalog(catalog)
    if catalog.get("catalogDigest") != manifest.get("catalogDigest"):
        raise GlobalRelationCatalogReleaseError("发布目录语义摘要与清单不一致。")
    catalog_ids = {
        str(row.get("globalTemplateId") or "")
        for row in catalog.get("connectionTemplates") or []
    }
    derived_ids = [str(value) for value in manifest.get("derivedTemplateIds") or []]
    if not derived_ids or any(value not in catalog_ids for value in derived_ids):
        raise GlobalRelationCatalogReleaseError("发布目录缺少清单声明的关系模板。")
    scope = manifest.get("scope") or {}
    authorized_ids = [
        str(value) for value in scope.get("authorizedDrivingTemplateIds") or []
    ]
    if any(value not in derived_ids for value in authorized_ids):
        raise GlobalRelationCatalogReleaseError("发布清单包含越权的驱动关系模板。")
    if bool(authorized_ids) != (scope.get("drivingRelationRelease") is True):
        raise GlobalRelationCatalogReleaseError("驱动发布开关与逐模板授权清单不一致。")
    template_by_id = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    if any(
        normalize_template_relation_profile(template_by_id[value]).get("drivesPlacement")
        is not True
        for value in authorized_ids
    ):
        raise GlobalRelationCatalogReleaseError("驱动授权模板不具备位姿驱动语义。")
    metadata = manifest.get("releaseMetadata")
    if metadata is not None:
        _validate_release_metadata(
            metadata,
            template_by_id=template_by_id,
            authorized_template_ids=authorized_ids,
        )
    combination_by_id = {
        str(row.get("globalCombinationId") or ""): row
        for row in catalog.get("templateCombinations") or []
    }
    authorized_combination_ids = [
        str(value)
        for value in scope.get("authorizedTemplateCombinationIds") or []
    ]
    if len(authorized_combination_ids) != len(set(authorized_combination_ids)):
        raise GlobalRelationCatalogReleaseError("模板组合授权清单存在重复编号。")
    for combination_id in authorized_combination_ids:
        combination = combination_by_id.get(combination_id)
        if combination is None:
            raise GlobalRelationCatalogReleaseError("发布目录缺少获授权的模板组合。")
        members = {
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        }
        if not members.issubset(set(authorized_ids)):
            raise GlobalRelationCatalogReleaseError(
                "模板组合成员未全部取得逐模板驱动授权。"
            )
        if (
            combination.get("exactMemberSetRequired") is not True
            or combination.get("fullyLocatesAddedComponent") is not True
            or int(combination.get("expectedResidualDof", -1)) != 0
        ):
            raise GlobalRelationCatalogReleaseError("获授权模板组合不满足闭合语义。")
    if authorized_ids:
        live_validation_payloads: list[dict[str, Any]] = []
        for row in manifest.get("validationEvidence") or []:
            evidence_path = Path(str(row.get("path") or "")).resolve()
            try:
                evidence_path.relative_to(workspace_root)
            except ValueError as exc:
                raise GlobalRelationCatalogReleaseError("关系验证证据越出工作区。") from exc
            if not evidence_path.is_file() or _file_sha256(evidence_path) != row.get("fileSha256"):
                raise GlobalRelationCatalogReleaseError("关系验证证据缺失或摘要不匹配。")
            payload = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
            if not _validation_passed(payload):
                raise GlobalRelationCatalogReleaseError("关系验证证据当前未通过。")
            live_validation_payloads.append(payload)
        if not any(
            _driving_initial_pose_validation_passed(payload)
            for payload in live_validation_payloads
        ):
            raise GlobalRelationCatalogReleaseError(
                "驱动发布缺少非原型初始位姿CAD证据，授权已失效。"
            )
    return catalog, manifest


def relation_catalog_release_binding(
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    """Build the portable, immutable binding carried by executable artifacts."""

    manifest_path = manifest_path.resolve()
    workspace_root = workspace_root.resolve()
    try:
        relative_manifest = manifest_path.relative_to(workspace_root)
    except ValueError as exc:
        raise GlobalRelationCatalogReleaseError(
            "关系发布清单必须位于工作区内。"
        ) from exc
    scope = manifest.get("scope") or {}
    authorized = sorted(
        {
            str(value).strip()
            for value in scope.get("authorizedDrivingTemplateIds") or []
            if str(value).strip()
        }
    )
    authorized_combinations = sorted(
        {
            str(value).strip()
            for value in scope.get("authorizedTemplateCombinationIds") or []
            if str(value).strip()
        }
    )
    if scope.get("drivingRelationRelease") is not True or not authorized:
        raise GlobalRelationCatalogReleaseError(
            "关系发布清单没有逐模板驱动授权。"
        )
    binding = {
        "releaseId": manifest["releaseId"],
        "releaseDigest": manifest["releaseDigest"],
        "releaseManifestPath": relative_manifest.as_posix(),
        "catalogDigest": manifest["catalogDigest"],
        "releasedCatalogRelativePath": manifest["releasedCatalogRelativePath"],
        "derivedTemplateIds": sorted(manifest.get("derivedTemplateIds") or []),
        "authorizedDrivingTemplateIds": authorized,
    }
    metadata = manifest.get("releaseMetadata")
    if metadata is not None:
        binding["releaseMetadata"] = deepcopy(metadata)
    if authorized_combinations:
        binding["authorizedTemplateCombinationIds"] = authorized_combinations
    return binding


def _validate_release_metadata(
    metadata: dict[str, Any],
    *,
    template_by_id: dict[str, dict[str, Any]],
    authorized_template_ids: list[str],
) -> None:
    """Validate optional execution-class metadata without changing v1 releases."""

    if not isinstance(metadata, dict):
        raise GlobalRelationCatalogReleaseError("发布证据类别元数据必须是对象。")
    mode = str(metadata.get("relationExecutionMode") or "").strip().casefold()
    if mode not in SUPPORTED_RELATION_EXECUTION_MODES:
        raise GlobalRelationCatalogReleaseError("发布元数据包含不受支持的关系执行模式。")
    classes = metadata.get("templateEvidenceClasses")
    if not isinstance(classes, dict) or not classes:
        raise GlobalRelationCatalogReleaseError("发布元数据缺少逐模板证据类别。")
    authorized = set(authorized_template_ids)
    if set(classes) != authorized:
        raise GlobalRelationCatalogReleaseError(
            "发布元数据必须覆盖全部且仅覆盖已授权模板。"
        )
    for template_id, evidence_class in classes.items():
        normalized = str(evidence_class or "").strip().casefold()
        if normalized not in SUPPORTED_RELATION_EXECUTION_MODES:
            raise GlobalRelationCatalogReleaseError("逐模板证据类别不受支持。")
        template = template_by_id.get(template_id)
        if template is None or template_evidence_class(template) != normalized:
            raise GlobalRelationCatalogReleaseError(
                "发布元数据与目录模板的证据类别不一致。"
            )
    unique_classes = set(classes.values())
    if len(unique_classes) != 1 or mode not in unique_classes:
        raise GlobalRelationCatalogReleaseError(
            "隔离发布必须只包含与声明执行模式相同的证据类别。"
        )
    direct_compatible = metadata.get("directMechanicalInterfaceCompatible")
    if mode == DATUM_PLACEMENT_DEMO and direct_compatible is not False:
        raise GlobalRelationCatalogReleaseError(
            "基准放置Demo发布必须明确声明不代表机械接口直接兼容。"
        )
    if mode == DIRECT_INSTALLATION and direct_compatible is not True:
        raise GlobalRelationCatalogReleaseError(
            "直接安装发布必须明确声明机械接口直接兼容。"
        )


def load_bound_relation_catalog_release(
    binding: dict[str, Any],
    *,
    workspace_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Revalidate a recorded release binding against live immutable evidence."""

    if not isinstance(binding, dict):
        raise GlobalRelationCatalogReleaseError("关系发布绑定必须是对象。")
    relative_value = str(binding.get("releaseManifestPath") or "").strip()
    if not relative_value:
        raise GlobalRelationCatalogReleaseError("关系发布绑定缺少发布清单路径。")
    workspace_root = workspace_root.resolve()
    manifest_path = (workspace_root / Path(relative_value)).resolve()
    try:
        manifest_path.relative_to(workspace_root)
    except ValueError as exc:
        raise GlobalRelationCatalogReleaseError("关系发布绑定路径越出工作区。") from exc
    catalog, manifest = load_relation_catalog_release(
        manifest_path,
        workspace_root=workspace_root,
    )
    expected = relation_catalog_release_binding(
        manifest,
        manifest_path=manifest_path,
        workspace_root=workspace_root,
    )
    if binding != expected:
        raise GlobalRelationCatalogReleaseError(
            "关系发布清单已变化或执行产物中的发布绑定被修改。"
        )
    return catalog, manifest

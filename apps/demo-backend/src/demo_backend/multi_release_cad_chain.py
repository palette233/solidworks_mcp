"""Compose separately authorized CAD manifests into one staged cumulative chain."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .global_cad_packet_executor import validate_cad_manifest_release_authority


SCHEMA = "multi-release-cad-transaction-chain/v1"


class MultiReleaseCadChainError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _inside(workspace: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as exc:
        raise MultiReleaseCadChainError("多发布链路证据必须位于工作区内。") from exc
    return resolved


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiReleaseCadChainError(f"无法读取链路证据：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MultiReleaseCadChainError("链路证据根节点必须是对象。")
    return value


def _verify_manifest_digest(manifest: dict[str, Any]) -> None:
    if manifest.get("schemaVersion") != "global-cad-transaction-manifest/v1":
        raise MultiReleaseCadChainError("只能组合全局CAD事务清单。")
    actual = _digest(
        {key: value for key, value in manifest.items() if key != "manifestDigest"}
    )
    if manifest.get("manifestDigest") != actual:
        raise MultiReleaseCadChainError("CAD事务清单摘要不一致。")


def rebase_single_packet_manifest_for_external_checkpoint(
    manifest: dict[str, Any],
    *,
    source_stage_id: str,
) -> dict[str, Any]:
    """Turn a first-packet manifest into an append-only stage.

    The relation release, target, ports, endpoints and mates stay unchanged.
    Only the cumulative input is changed from the registered base source to the
    preceding stage's committed assembly checkpoint.
    """

    _verify_manifest_digest(manifest)
    packets = manifest.get("packets") or []
    if len(packets) != 1 or int(manifest.get("packetCount") or 0) != 1:
        raise MultiReleaseCadChainError("当前只允许将单包清单转为跨发布追加阶段。")
    packet = packets[0]
    cumulative = packet.get("cumulativeInput") or {}
    if cumulative.get("kind") != "base_module_source":
        raise MultiReleaseCadChainError("追加清单的原始首包必须以登记基座为输入。")
    source_stage_id = str(source_stage_id or "").strip()
    if not source_stage_id:
        raise MultiReleaseCadChainError("source_stage_id不能为空。")

    result = copy.deepcopy(manifest)
    target_packet = result["packets"][0]
    target_packet["cumulativeInput"] = {
        "kind": "previous_transaction_checkpoint",
        "packetId": f"{source_stage_id}:final",
        "externalStageId": source_stage_id,
    }
    target_packet.pop("packetDigest", None)
    target_packet["packetDigest"] = _digest(target_packet)
    result["externalCheckpointContract"] = {
        "schemaVersion": "external-stage-checkpoint-contract/v1",
        "sourceStageId": source_stage_id,
        "requiresPassedClosure": True,
        "requiresExistingAssembly": True,
        "requiresAssemblySha256Match": True,
        "statement": (
            "只替换累计输入来源；关系发布、语义端口、配合参数和"
            "目标模组均保持不变。"
        ),
    }
    result.pop("manifestDigest", None)
    result["manifestDigest"] = _digest(result)
    return result


def build_multi_release_cad_chain(
    workspace: Path,
    *,
    direct_manifest_path: Path,
    direct_closure_path: Path,
    append_manifest_path: Path,
    chain_id: str,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    direct_manifest_path = _inside(workspace, direct_manifest_path)
    direct_closure_path = _inside(workspace, direct_closure_path)
    append_manifest_path = _inside(workspace, append_manifest_path)
    direct = _read(direct_manifest_path)
    append = _read(append_manifest_path)
    closure = _read(direct_closure_path)
    _verify_manifest_digest(direct)
    _verify_manifest_digest(append)
    direct_authority = validate_cad_manifest_release_authority(workspace, direct)
    append_authority = validate_cad_manifest_release_authority(workspace, append)

    if closure.get("status") != "passed" or not all(
        value is True for value in (closure.get("checks") or {}).values()
    ):
        raise MultiReleaseCadChainError("直接安装前置阶段的真实CAD闭合证据未通过。")
    checkpoint = Path(str(closure.get("finalAssemblyPath") or "")).resolve()
    if not checkpoint.is_file():
        raise MultiReleaseCadChainError("前置阶段最终装配体不存在。")
    expected_checkpoint_sha = str(closure.get("finalAssemblySha256") or "").lower()
    if not expected_checkpoint_sha or _file_sha256(checkpoint).lower() != expected_checkpoint_sha:
        raise MultiReleaseCadChainError("前置阶段最终装配体摘要不匹配。")
    contract = append.get("externalCheckpointContract") or {}
    if contract.get("sourceStageId") != "direct-installation-stage":
        raise MultiReleaseCadChainError("追加阶段未绑定预期的前置阶段。")
    if (append.get("packets") or [{}])[0].get("cumulativeInput", {}).get(
        "kind"
    ) != "previous_transaction_checkpoint":
        raise MultiReleaseCadChainError("追加阶段必须使用上一阶段检查点。")

    def stage(
        stage_id: str,
        manifest_path: Path,
        manifest: dict[str, Any],
        authority: dict[str, Any],
        *,
        input_policy: str,
    ) -> dict[str, Any]:
        binding = authority.get("binding") or {}
        return {
            "stageId": stage_id,
            "manifestPath": manifest_path.relative_to(workspace).as_posix(),
            "manifestFileSha256": _file_sha256(manifest_path),
            "manifestDigest": manifest["manifestDigest"],
            "releaseId": binding.get("releaseId"),
            "releaseDigest": binding.get("releaseDigest"),
            "relationExecutionMode": (
                (binding.get("releaseMetadata") or {}).get("relationExecutionMode")
                or "direct_installation"
            ),
            "packetCount": manifest.get("packetCount"),
            "inputPolicy": input_policy,
            "authorizedTemplateIds": authority.get("authorizedDrivingTemplateIds")
            or [],
            "usedTemplateIds": authority.get("usedDrivingTemplateIds") or [],
        }

    result = {
        "schemaVersion": SCHEMA,
        "chainId": str(chain_id),
        "status": "ready_for_staged_execution",
        "stageCount": 2,
        "packetCount": int(direct.get("packetCount") or 0)
        + int(append.get("packetCount") or 0),
        "stages": [
            stage(
                "direct-installation-stage",
                direct_manifest_path,
                direct,
                direct_authority,
                input_policy="registered_base_then_internal_checkpoints",
            ),
            stage(
                "optional-datum-demo-stage",
                append_manifest_path,
                append,
                append_authority,
                input_policy="previous_stage_committed_checkpoint",
            ),
        ],
        "checkpointBinding": {
            "sourceStageId": "direct-installation-stage",
            "targetStageId": "optional-datum-demo-stage",
            "assemblyPath": str(checkpoint),
            "assemblySha256": expected_checkpoint_sha,
            "closureEvidencePath": direct_closure_path.relative_to(workspace).as_posix(),
            "closureEvidenceFileSha256": _file_sha256(direct_closure_path),
        },
        "executionBoundary": {
            "cadStarted": False,
            "collisionOrBrep": "not_evaluated",
            "statement": (
                "两个阶段各自维持不可变发布授权；Demo级关系未混入"
                "默认直接安装发布。"
            ),
        },
    }
    result["chainDigest"] = _digest(result)
    return result


def validate_multi_release_cad_chain(
    workspace: Path, chain: dict[str, Any]
) -> None:
    if chain.get("schemaVersion") != SCHEMA:
        raise MultiReleaseCadChainError("多发布链路版本不受支持。")
    expected = _digest(
        {key: value for key, value in chain.items() if key != "chainDigest"}
    )
    if chain.get("chainDigest") != expected:
        raise MultiReleaseCadChainError("多发布链路摘要不一致。")
    rebuilt = build_multi_release_cad_chain(
        workspace,
        direct_manifest_path=workspace / chain["stages"][0]["manifestPath"],
        direct_closure_path=workspace
        / chain["checkpointBinding"]["closureEvidencePath"],
        append_manifest_path=workspace / chain["stages"][1]["manifestPath"],
        chain_id=str(chain.get("chainId") or ""),
    )
    if rebuilt != chain:
        raise MultiReleaseCadChainError("多发布链路现场证据已变化。")

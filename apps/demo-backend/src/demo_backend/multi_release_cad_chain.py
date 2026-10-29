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
    direct_manifest_path: Path | None = None,
    direct_closure_path: Path | None = None,
    append_manifest_path: Path | None = None,
    chain_id: str,
    stages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if stages is not None:
        if any(value is not None for value in (
            direct_manifest_path, direct_closure_path, append_manifest_path
        )):
            raise MultiReleaseCadChainError("有序阶段与旧两阶段参数不能混用。")
        return _build_ordered_chain(workspace, stages=stages, chain_id=chain_id)
    if any(value is None for value in (
        direct_manifest_path, direct_closure_path, append_manifest_path
    )):
        raise MultiReleaseCadChainError("旧两阶段调用必须同时提供三个证据路径。")
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
    if chain.get("stagePlanMode") == "ordered_independent_releases":
        rebuilt = _build_ordered_chain(
            workspace,
            stages=[{"stageId": row["stageId"], "manifestPath": row["manifestPath"]}
                    for row in chain["stages"]],
            chain_id=str(chain.get("chainId") or ""),
        )
        if rebuilt != chain:
            raise MultiReleaseCadChainError("有序阶段清单或发布授权已变化。")
        return
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


def _build_ordered_chain(
    workspace: Path, *, stages: list[dict[str, Any]], chain_id: str
) -> dict[str, Any]:
    """Plan ordered, separately authorized stages; no CAD or checkpoint is invented."""
    workspace = workspace.resolve()
    if not stages or not str(chain_id).strip():
        raise MultiReleaseCadChainError("有序链需要非空chain_id和stages。")
    rows = []
    seen = set()
    for index, spec in enumerate(stages):
        stage_id = str(spec.get("stageId") or "").strip()
        if not stage_id or stage_id in seen or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for char in stage_id
        ):
            raise MultiReleaseCadChainError("stageId必须唯一且只包含字母数字、连字符或下划线。")
        seen.add(stage_id)
        path = Path(str(spec.get("manifestPath") or ""))
        path = _inside(workspace, path if path.is_absolute() else workspace / path)
        manifest = _read(path)
        _verify_manifest_digest(manifest)
        packets = manifest.get("packets") or []
        if not packets or len(packets) != manifest.get("packetCount"):
            raise MultiReleaseCadChainError("阶段清单的包数量不一致。")
        if (packets[0].get("cumulativeInput") or {}).get("kind") != "base_module_source":
            raise MultiReleaseCadChainError("阶段原始清单必须以登记基座为输入，由准备函数重基。")
        if index and len(packets) != 1:
            raise MultiReleaseCadChainError("非首阶段必须是单包，禁止隐式重排多个追加步骤。")
        authority = validate_cad_manifest_release_authority(workspace, manifest)
        binding = authority.get("binding") or {}
        if (authority.get("status") != "verified"
                or not str(binding.get("releaseId") or "").strip()
                or not str(binding.get("releaseDigest") or "").strip()):
            raise MultiReleaseCadChainError(
                "有序阶段必须绑定已验证的不可变发布（releaseId和releaseDigest）；不接受legacy_unbound。"
            )
        rows.append({
            "stageId": stage_id,
            "manifestPath": path.relative_to(workspace).as_posix(),
            "manifestFileSha256": _file_sha256(path),
            "manifestDigest": manifest["manifestDigest"],
            "packetCount": len(packets),
            "releaseId": binding.get("releaseId"),
            "releaseDigest": binding.get("releaseDigest"),
            "relationExecutionMode": (binding.get("releaseMetadata") or {}).get(
                "relationExecutionMode", "direct_installation"
            ),
            "sourceStageId": rows[-1]["stageId"] if rows else None,
            "inputPolicy": "previous_stage_committed_checkpoint" if index else
                           "registered_base_then_internal_checkpoints",
        })
    result = {
        "schemaVersion": SCHEMA,
        "stagePlanMode": "ordered_independent_releases",
        "chainId": str(chain_id),
        "status": "ready_for_staged_execution",
        "stageCount": len(rows),
        "packetCount": sum(row["packetCount"] for row in rows),
        "stages": rows,
        "executionBoundary": {
            "cadStarted": False, "collisionOrBrep": "not_evaluated",
            "actualFasteningMethod": "not_verified",
            "statement": "逐阶段保留发布授权；仅在前置检查点验证后启动追加，不限制Demo阶段必须最后执行。",
        },
    }
    result["chainDigest"] = _digest(result)
    return result


def _ordered_stage(workspace: Path, chain: dict, stage_id: str) -> dict:
    validate_multi_release_cad_chain(workspace, chain)
    if chain.get("stagePlanMode") != "ordered_independent_releases":
        raise MultiReleaseCadChainError("此接口仅用于有序独立发布阶段。")
    rows = [row for row in chain["stages"] if row["stageId"] == stage_id]
    if len(rows) != 1:
        raise MultiReleaseCadChainError("请求阶段不在链路中。")
    return rows[0]


def _write_new_or_equal(path: Path, value: dict) -> None:
    if path.exists():
        if _read(path) != value:
            raise MultiReleaseCadChainError(f"拒绝覆盖已有不同内容：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _verified_stage_checkpoint(workspace: Path, chain: dict, stage: dict, path: Path) -> dict:
    path = _inside(workspace, path)
    closure = _read(path)
    if closure.get("closureDigest") != _digest({
        key: value for key, value in closure.items() if key != "closureDigest"
    }):
        raise MultiReleaseCadChainError("前置阶段闭合证据摘要不匹配。")
    if (closure.get("chainDigest") != chain["chainDigest"]
            or closure.get("stageId") != stage["sourceStageId"]
            or closure.get("status") != "passed"
            or not closure.get("checks")
            or not all(value is True for value in closure["checks"].values())):
        raise MultiReleaseCadChainError("前置阶段闭合证据未通过或绑定了不同链路/阶段。")
    assembly = _inside(workspace, Path(str(closure.get("finalAssemblyPath") or "")))
    if not assembly.is_file() or _file_sha256(assembly) != closure.get("finalAssemblySha256"):
        raise MultiReleaseCadChainError("前置阶段检查点缺失或文件摘要发生变化。")
    evidence = _inside(workspace, Path(str(closure.get("executionEnvelopePath") or "")))
    if not evidence.is_file() or _file_sha256(evidence) != closure.get("executionEnvelopeSha256"):
        raise MultiReleaseCadChainError("前置阶段执行证据缺失或文件摘要发生变化。")
    return closure


def _source_command_audit(workspace: Path, manifest_path: Path, manifest: dict) -> dict:
    """Keep the actual NL/context/DAG trace when the execution copy is rebased."""
    from .global_cad_manifest_orchestrator import _build_command_audit_binding

    audit = _build_command_audit_binding(
        workspace, manifest_path, manifest, list(manifest.get("packets") or [])
    )
    # The audit sources bind the unmodified compiler output, not its execution
    # copy. Missing sources remain unavailable; no synthetic NL history is added.
    audit["sources"]["manifestSha256"] = _file_sha256(manifest_path)
    context_id = str(manifest.get("contextId") or "")
    report_path = manifest_path.with_name(f"{context_id}.natural-language-compilation.json")
    if report_path.is_file():
        report = _read(report_path)
        if (report.get("success") is not True or report.get("contextId") != context_id
                or Path(str(report.get("manifestPath") or "")).resolve() != manifest_path.resolve()):
            raise MultiReleaseCadChainError("原始自然语言编译报告与源清单绑定不一致。")
        audit["naturalLanguageCompilation"] = {
            "path": str(report_path.resolve()), "fileSha256": _file_sha256(report_path),
            "requirements": report.get("requirements") or [],
            "originalRequirements": report.get("originalRequirements") or [],
            "timingSeconds": report.get("timingSeconds") or {},
        }
    return audit


def _validate_source_command_audit(audit: dict) -> None:
    sources = audit.get("sources") or {}
    for key, expected in sources.items():
        if not key.endswith("Sha256") or not expected:
            continue
        path = Path(str(sources.get(key.removesuffix("Sha256") + "Path") or ""))
        if not path.is_file() or _file_sha256(path) != expected:
            raise MultiReleaseCadChainError(f"原始自然语言审计输入已变化：{key}")
    compilation = audit.get("naturalLanguageCompilation")
    if compilation:
        path = Path(compilation["path"])
        if not path.is_file() or _file_sha256(path) != compilation.get("fileSha256"):
            raise MultiReleaseCadChainError("原始自然语言编译报告已变化。")


def prepare_multi_release_stage_job(
    workspace: Path, chain: dict, stage_id: str, store, artifacts_root: Path,
    *, previous_closure_path: Path | None = None,
) -> dict:
    """Prepare one existing durable manifest job; never run CAD here.

    A source manifest is immutable. Only its append input is rebased. The seed
    identity participates in the plan/idempotency key, so a new checkpoint
    cannot silently reuse an older stage job.
    """
    from .global_cad_manifest_orchestrator import build_manifest_job_plan

    stage = _ordered_stage(workspace, chain, stage_id)
    source_path = workspace / stage["manifestPath"]
    manifest = _read(source_path)
    source_audit = _source_command_audit(workspace, source_path, manifest)
    closure = None
    if stage["sourceStageId"]:
        if previous_closure_path is None:
            raise MultiReleaseCadChainError("追加阶段必须提供前置闭合证据。")
        closure = _verified_stage_checkpoint(workspace, chain, stage, previous_closure_path)
        manifest = rebase_single_packet_manifest_for_external_checkpoint(
            manifest, source_stage_id=stage["sourceStageId"]
        )
    elif previous_closure_path is not None:
        raise MultiReleaseCadChainError("首阶段不得继承外部检查点。")
    path = _inside(workspace, artifacts_root / stage_id / "cad-transaction-manifest.json")
    _write_new_or_equal(path, manifest)
    plan = build_manifest_job_plan(workspace, path)
    plan["sourceCommandAudit"] = source_audit
    plan["sourceCommandAuditProvenance"] = {
        "sourceManifestDigest": stage["manifestDigest"],
        "executionManifestDigest": manifest["manifestDigest"],
        "change": "cumulative_input_rebased" if closure else "unchanged_manifest_copy",
        "statement": "原始自然语言、实例、端口与配合关系不变；只替换累计输入，源审计不冒充新的会话历史。",
    }
    plan["multiReleaseStageBinding"] = {
        "chainId": chain["chainId"], "chainDigest": chain["chainDigest"],
        "stageId": stage_id, "sourceStageId": stage["sourceStageId"],
        "sourceManifestDigest": stage["manifestDigest"],
        "sourceCheckpoint": None if closure is None else {
            "assemblyPath": closure["finalAssemblyPath"],
            "assemblySha256": closure["finalAssemblySha256"],
            "closurePath": str(previous_closure_path.resolve()),
            "closureFileSha256": _file_sha256(previous_closure_path),
        },
    }
    if closure is not None:
        plan["requiresSeedCheckpoint"] = True
    plan.pop("planDigest", None)
    plan["planDigest"] = _digest(plan)
    job = store.create(plan, execution_mode="generic_cad_manifest")
    if job["plan"] != plan:
        raise MultiReleaseCadChainError("已有任务计划与当前阶段不一致。")
    _write_new_or_equal(store._dir(job["jobId"]) / "source-command-audit.json", source_audit)
    if closure is not None and not job.get("initialCommittedCheckpoint"):
        job = store.seed_verified_checkpoint(
            job["jobId"], step_id=f'{stage["sourceStageId"]}:final',
            module_token=str(closure["moduleToken"]),
            assembly_path=Path(closure["finalAssemblyPath"]),
            evidence_path=previous_closure_path,
        )
    return job


def guard_multi_release_stage_runner(workspace: Path, chain: dict, stage_id: str, store, runner):
    """Guard the existing runner, preserving its retry paths and failure rollback."""
    stage = _ordered_stage(workspace, chain, stage_id)

    def run(job: dict, step: dict, previous: Path | None) -> dict:
        _ordered_stage(workspace, chain, stage_id)
        binding = (job.get("plan") or {}).get("multiReleaseStageBinding") or {}
        if binding.get("chainDigest") != chain["chainDigest"] or binding.get("stageId") != stage_id:
            raise MultiReleaseCadChainError("任务与有序阶段绑定不一致。")
        _validate_source_command_audit((job.get("plan") or {}).get("sourceCommandAudit") or {})
        seed = binding.get("sourceCheckpoint")
        if seed:
            closure_path = Path(seed["closurePath"])
            if _file_sha256(closure_path) != seed["closureFileSha256"]:
                raise MultiReleaseCadChainError("任务创建后前置闭合证据已变化。")
            _verified_stage_checkpoint(workspace, chain, stage, closure_path)
        before_sha = None
        if previous is not None:
            checkpoint = job.get("lastCommittedCheckpoint") or {}
            if previous.resolve() != Path(checkpoint.get("assemblyPath", "")).resolve():
                raise MultiReleaseCadChainError("执行输入不是最后已提交检查点。")
            if checkpoint.get("externalVerifiedSeed"):
                expected_sha = (seed or {}).get("assemblySha256")
            else:
                evidence = _read(Path(checkpoint["evidencePath"]))
                envelope = _read(Path(evidence["executionEnvelopePath"]))
                expected_sha = envelope.get("outputAssemblySha256")
            before_sha = _file_sha256(previous)
            if not expected_sha or expected_sha != before_sha:
                raise MultiReleaseCadChainError("执行前检查点SHA-256不匹配。")
        run_dir = store._dir(job["jobId"]) / "packet-runs" / (
            f'{step["stepId"]}-attempt-{int(step.get("attemptCount") or 1):02d}'
        )
        if run_dir.exists() and any(run_dir.iterdir()):
            raise MultiReleaseCadChainError("本次尝试目录非空，拒绝覆盖旧产物。")
        try:
            result = runner(job, step, previous)
        finally:
            if previous is not None and _file_sha256(previous) != before_sha:
                raise MultiReleaseCadChainError("追加执行修改了前置检查点，禁止提交新检查点。")
        output = Path(str(result.get("assemblyPath") or "")).resolve()
        if previous is not None and output == previous.resolve():
            raise MultiReleaseCadChainError("追加输出不能覆盖输入检查点。")
        return result

    return run


def build_multi_release_stage_closure(
    workspace: Path, chain: dict, stage_id: str, store, job_id: str,
) -> dict:
    """Bridge a succeeded manifest job to the next stage, without rerunning it."""
    _ordered_stage(workspace, chain, stage_id)
    job = store.load(job_id)
    binding = job.get("plan", {}).get("multiReleaseStageBinding") or {}
    if (job.get("status") != "succeeded" or not job.get("steps")
            or not all(step.get("status") == "succeeded" for step in job["steps"])
            or binding.get("chainDigest") != chain["chainDigest"]
            or binding.get("stageId") != stage_id):
        raise MultiReleaseCadChainError("阶段任务未成功或链路绑定错误，不能推进检查点。")
    _validate_source_command_audit(job.get("plan", {}).get("sourceCommandAudit") or {})
    checkpoint = job["lastCommittedCheckpoint"]
    evidence = _read(Path(checkpoint["evidencePath"]))
    envelope_path = Path(str(evidence.get("executionEnvelopePath") or ""))
    envelope = _read(envelope_path)
    assembly = Path(checkpoint["assemblyPath"]).resolve()
    checks = {
        "jobSucceeded": True,
        "packetAccepted": evidence.get("accepted") is True and envelope.get("success") is True,
        "sourceUnchanged": envelope.get("sourceAssemblyUnchanged") is True
            and envelope.get("executionSourceUnchanged") is True,
        "packetIdentityMatches": envelope.get("packetDigest") == checkpoint.get("packetDigest")
            and envelope.get("packetId") == checkpoint.get("packetId"),
        "outputIdentityMatches": Path(str(envelope.get("outputAssemblyPath") or "")).resolve() == assembly,
        "outputSha256Matches": assembly.is_file()
            and _file_sha256(assembly) == envelope.get("outputAssemblySha256"),
    }
    if not all(checks.values()):
        raise MultiReleaseCadChainError("任务检查点与真实执行证据不一致，不能推进下一阶段。")
    result = {
        "schemaVersion": "multi-release-cad-stage-closure/v1",
        "status": "passed", "chainDigest": chain["chainDigest"], "stageId": stage_id,
        "jobId": job_id, "moduleToken": checkpoint["moduleToken"],
        "manifestDigest": job["plan"]["manifestDigest"],
        "finalAssemblyPath": str(assembly), "finalAssemblySha256": _file_sha256(assembly),
        "executionEnvelopePath": str(envelope_path.resolve()),
        "executionEnvelopeSha256": _file_sha256(envelope_path), "checks": checks,
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "collisionOrBrep": "not_evaluated", "actualFasteningMethod": "not_verified",
    }
    result["closureDigest"] = _digest(result)
    return result

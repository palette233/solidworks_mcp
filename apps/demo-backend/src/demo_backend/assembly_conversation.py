"""Durable turn ledger for multi-turn natural-language CAD assembly.

The global assembly context is the source of truth for the semantic graph.  This
module deliberately stores execution provenance in a sidecar so binding a CAD
job never changes the context digest that was confirmed by the user.
"""

from __future__ import annotations

import json
import hashlib
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


CONVERSATION_SCHEMA = "assembly-conversation/v1"
CONTINUABLE_VALIDATION_PROFILES = frozenset(
    {
        "demo",
        "generic-cad-transaction-manifest-v1",
    }
)
_LOCK = threading.RLock()


class AssemblyConversationError(ValueError):
    pass


def _is_continuable_job_binding(job: dict[str, Any]) -> bool:
    """Return whether a persisted CAD result is a safe cumulative seed.

    Collision/B-rep is deliberately an optional downstream engineering check
    on the current mainline.  An explicitly rejected result is never
    continuable, while ``not_evaluated`` does not erase otherwise complete
    save/close/reopen CAD evidence.
    """

    checkpoint = job.get("demoCheckpoint")
    return bool(
        job.get("validationProfile") in CONTINUABLE_VALIDATION_PROFILES
        and job.get("status") == "succeeded"
        and job.get("assemblyStatus") == "assembled"
        and job.get("collisionStatus") != "rejected"
        and isinstance(checkpoint, dict)
        and checkpoint.get("assemblyPath")
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def conversation_path(context_path: Path) -> Path:
    return context_path.with_suffix(".conversation.json")


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _new(context: dict[str, Any]) -> dict[str, Any]:
    timestamp = _now()
    current_revision = int(context.get("revision") or 0)
    migrated_turns = []
    for row in context.get("history") or []:
        revision = int(row.get("revision") or 0)
        if revision <= 0:
            continue
        migrated_turns.append(
            {
                "turnId": f"turn-{revision:04d}",
                "contextRevision": revision,
                "requirement": str(row.get("requirement") or ""),
                "previewDigest": str(row.get("previewDigest") or ""),
                "contextDigest": (
                    str(context.get("contextDigest") or "")
                    if revision == current_revision
                    else "unavailable-pre-ledger"
                ),
                "operation": row.get("operation"),
                "moduleDefinitionId": None,
                "instanceId": None,
                "connectionId": None,
                "graphStatus": "committed",
                "jobs": [],
                "recordedAt": str(row.get("timestamp") or timestamp),
                "migratedFromContextHistory": True,
            }
        )
    return {
        "schemaVersion": CONVERSATION_SCHEMA,
        "contextId": str(context["contextId"]),
        "turns": migrated_turns,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def reset_conversation(context_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    ledger = _new(context)
    with _LOCK:
        _write(conversation_path(context_path), ledger)
    return ledger


def load_conversation(context_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    path = conversation_path(context_path)
    if not path.is_file():
        return _new(context)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssemblyConversationError(f"无法读取装配会话台账：{path}: {exc}") from exc
    if ledger.get("schemaVersion") != CONVERSATION_SCHEMA:
        raise AssemblyConversationError("不支持的装配会话台账版本。")
    if ledger.get("contextId") != context.get("contextId"):
        raise AssemblyConversationError("装配会话台账与上下文编号不一致。")
    if not isinstance(ledger.get("turns"), list):
        raise AssemblyConversationError("装配会话台账缺少turns数组。")
    return ledger


def record_graph_turn(
    context_path: Path,
    context: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    revision = int(context.get("revision") or 0)
    if revision <= 0:
        raise AssemblyConversationError("只有已提交的图修订可以写入会话台账。")
    patch = preview.get("proposedPatch") or {}
    relation_after = patch.get("after") or {}
    turn = {
        "turnId": f"turn-{revision:04d}",
        "contextRevision": revision,
        "requirement": str(preview.get("requirement") or ""),
        "previewDigest": str(preview.get("previewDigest") or ""),
        "sourceContextDigest": str(preview.get("sourceContextDigest") or ""),
        "contextDigest": str(context.get("contextDigest") or ""),
        "operation": patch.get("operation"),
        "moduleDefinitionId": (patch.get("instance") or {}).get("moduleDefinitionId"),
        "instanceId": (patch.get("instance") or {}).get("instanceId"),
        "connectionId": (
            (patch.get("connection") or {}).get("connectionId")
            or relation_after.get("connectionId")
            or patch.get("connectionId")
        ),
        "graphStatus": "committed",
        "jobs": [],
        "recordedAt": str(context.get("updatedAt") or _now()),
    }
    path = conversation_path(context_path)
    with _LOCK:
        ledger = load_conversation(context_path, context)
        existing = next(
            (
                row
                for row in ledger["turns"]
                if int(row.get("contextRevision") or -1) == revision
            ),
            None,
        )
        if existing is not None:
            if existing.get("previewDigest") != turn["previewDigest"]:
                raise AssemblyConversationError(
                    f"修订{revision}已绑定不同的自然语言预览。"
                )
            return ledger
        ledger["turns"].append(turn)
        ledger["turns"].sort(key=lambda row: int(row.get("contextRevision") or 0))
        ledger["updatedAt"] = _now()
        _write(path, ledger)
    return ledger


def rollback_latest_graph_turn(
    context_path: Path,
    context: dict[str, Any],
    *,
    expected_revision: int,
    expected_context_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove the newest graph-only turn from the durable conversation ledger.

    A turn that already owns a CAD job or a direct CAD edit is deliberately not
    eligible: rolling back only the semantic graph would otherwise leave the
    persisted SolidWorks result and the graph describing different assemblies.
    """

    revision = int(context.get("revision") or 0)
    if revision <= 0:
        raise AssemblyConversationError("当前装配会话还没有可撤销的已提交轮次。")
    if revision != int(expected_revision):
        raise AssemblyConversationError("装配会话修订已变化，请刷新后重新确认撤销。")
    if str(context.get("contextDigest") or "") != str(expected_context_digest or ""):
        raise AssemblyConversationError("装配会话摘要已变化，请刷新后重新确认撤销。")

    path = conversation_path(context_path)
    with _LOCK:
        ledger = load_conversation(context_path, context)
        latest = next(
            (
                row
                for row in reversed(ledger["turns"])
                if int(row.get("contextRevision") or -1) == revision
            ),
            None,
        )
        if latest is None:
            raise AssemblyConversationError(
                f"会话台账中找不到当前修订{revision}，不能安全撤销。"
            )
        if latest.get("jobs"):
            raise AssemblyConversationError(
                "最新一轮已经绑定CAD任务；请先处理或另存实体结果，不能只回退语义图。"
            )
        if latest.get("cadEdits"):
            raise AssemblyConversationError(
                "最新一轮已经产生实体修改证据；不能只回退语义图。"
            )

        removed = deepcopy(latest)
        removed["rolledBackAt"] = _now()
        ledger["turns"] = [
            row
            for row in ledger["turns"]
            if int(row.get("contextRevision") or -1) != revision
        ]
        ledger.setdefault("rolledBackTurns", []).append(removed)
        ledger["updatedAt"] = _now()
        _write(path, ledger)
    return ledger, removed


def bind_job(
    context_path: Path,
    context: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    plan = job.get("plan") or {}
    revision = int(plan.get("contextRevision") or 0)
    revision_source = "explicit_plan"
    if revision <= 0:
        if (
            str(plan.get("contextId") or "") == str(context.get("contextId") or "")
            and str(plan.get("contextDigest") or "")
            == str(context.get("contextDigest") or "")
            and int(context.get("revision") or 0) > 0
        ):
            revision = int(context["revision"])
            revision_source = "exact_context_digest_backfill"
        else:
            raise AssemblyConversationError(
                "CAD任务缺少contextRevision，且上下文编号/摘要不能唯一回填修订。"
            )
    binding = {
        "jobId": str(job["jobId"]),
        "projectId": str(job.get("projectId") or ""),
        "validationProfile": str(job.get("validationProfile") or "demo"),
        "status": str(job.get("status") or "queued"),
        "assemblyStatus": str(job.get("assemblyStatus") or "pending"),
        "collisionStatus": str(job.get("collisionStatus") or "not_evaluated"),
        "sourceJobId": ((plan.get("executionScope") or {}).get("seedJobId")),
        "executionScope": deepcopy(plan.get("executionScope") or {}),
        "bindingRevisionSource": revision_source,
        "demoCheckpoint": deepcopy(job.get("demoCheckpoint")),
        "createdAt": job.get("createdAt"),
        "updatedAt": job.get("updatedAt"),
    }
    path = conversation_path(context_path)
    with _LOCK:
        ledger = load_conversation(context_path, context)
        turn = next(
            (
                row
                for row in ledger["turns"]
                if int(row.get("contextRevision") or -1) == revision
            ),
            None,
        )
        if turn is None:
            raise AssemblyConversationError(f"找不到CAD任务对应的图修订{revision}。")
        jobs = turn.setdefault("jobs", [])
        existing = next((row for row in jobs if row.get("jobId") == binding["jobId"]), None)
        if existing is None:
            jobs.append(binding)
        else:
            existing.update(binding)
        ledger["updatedAt"] = _now()
        _write(path, ledger)
    return ledger


def bind_attested_checkpoint(
    context_path: Path,
    context: dict[str, Any],
    job: dict[str, Any],
    attestation: dict[str, Any],
    *,
    attestation_path: Path,
) -> dict[str, Any]:
    """Bind a pre-ledger successful job after an immutable evidence attestation."""

    revision = int(context.get("revision") or 0)
    if revision <= 0:
        raise AssemblyConversationError("空装配上下文不能导入历史检查点。")
    if attestation.get("contextId") != context.get("contextId"):
        raise AssemblyConversationError("历史检查点签认属于其他上下文。")
    if int(attestation.get("contextRevision") or -1) != revision:
        raise AssemblyConversationError("历史检查点签认的上下文修订已过期。")
    if attestation.get("contextDigest") != context.get("contextDigest"):
        raise AssemblyConversationError("历史检查点签认的上下文摘要已过期。")
    if attestation.get("jobId") != job.get("jobId"):
        raise AssemblyConversationError("历史检查点签认的任务编号不匹配。")
    if attestation.get("status") != "ready_for_import":
        raise AssemblyConversationError("历史检查点评估尚未通过。")
    checkpoint = job.get("demoCheckpoint")
    if not isinstance(checkpoint, dict) or not checkpoint.get("assemblyPath"):
        raise AssemblyConversationError("历史任务没有可导入的Demo检查点。")
    binding = {
        "jobId": str(job["jobId"]),
        "projectId": str(job.get("projectId") or ""),
        "validationProfile": "demo",
        "status": "succeeded",
        "assemblyStatus": str(job.get("assemblyStatus") or "assembled"),
        "collisionStatus": str(job.get("collisionStatus") or "not_evaluated"),
        "sourceJobId": None,
        "executionScope": {"kind": "historical_attested_import"},
        "demoCheckpoint": deepcopy(checkpoint),
        "createdAt": job.get("createdAt"),
        "updatedAt": job.get("updatedAt"),
        "bindingKind": "historical_attested_import",
        "attestationDigest": attestation.get("assessmentDigest"),
        "attestationPath": str(attestation_path),
        "checkpointAssemblyIdentity": deepcopy(
            attestation.get("checkpointAssemblyIdentity")
        ),
        "componentInventoryIdentity": deepcopy(
            attestation.get("componentInventoryIdentity")
        ),
    }
    path = conversation_path(context_path)
    with _LOCK:
        ledger = load_conversation(context_path, context)
        turn = next(
            (
                row
                for row in ledger["turns"]
                if int(row.get("contextRevision") or -1) == revision
            ),
            None,
        )
        if turn is None:
            raise AssemblyConversationError(
                f"找不到当前上下文修订{revision}对应的命令轮次。"
            )
        jobs = turn.setdefault("jobs", [])
        existing = next(
            (row for row in jobs if row.get("jobId") == binding["jobId"]), None
        )
        if existing is not None:
            if existing.get("bindingKind") != "historical_attested_import":
                raise AssemblyConversationError(
                    "该任务已经通过其他方式绑定到当前会话。"
                )
            if existing.get("attestationDigest") != binding["attestationDigest"]:
                raise AssemblyConversationError("该历史任务已绑定不同的签认证据。")
            existing.update(binding)
        else:
            jobs.append(binding)
        ledger["updatedAt"] = _now()
        _write(path, ledger)
    return ledger


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bind_direct_mate_execution(
    context_path: Path,
    context: dict[str, Any],
    execution: dict[str, Any],
    *,
    execution_path: Path,
) -> dict[str, Any]:
    """Promote one attested direct mate edit to the latest conversation turn.

    This does not mutate the semantic context digest.  It only advances the
    physical CAD continuation checkpoint after source/output identities and the
    SolidWorks save/reopen evidence have been verified.
    """

    if execution.get("schemaVersion") != "context-direct-mate-edit-run/v1":
        raise AssemblyConversationError("不支持的直接配合执行证据版本。")
    if not bool(execution.get("success")) or not bool(execution.get("published")):
        raise AssemblyConversationError("失败或未发布的直接配合执行不能推进会话检查点。")
    tool = execution.get("toolResult") or {}
    if str(tool.get("ExecutionMode") or tool.get("executionMode") or "") != (
        "direct_existing_component_mate_edit"
    ):
        raise AssemblyConversationError("执行证据不是现有组件直接配合编辑模式。")
    required_truths = (
        "Reopened",
        "ReopenedMateParametersMatch",
        "ComponentSemanticsMatch",
    )
    for key in required_truths:
        value = tool.get(key, tool.get(key[0].lower() + key[1:]))
        if value is not True:
            raise AssemblyConversationError(f"直接配合执行缺少权威复核：{key}。")
    if tool.get("TargetComponentReinserted", tool.get("targetComponentReinserted")) is not False:
        raise AssemblyConversationError("直接配合执行意外重新插入了目标模组。")
    if tool.get(
        "TargetComponentExplicitlyDisplaced", tool.get("targetComponentExplicitlyDisplaced")
    ) is not False:
        raise AssemblyConversationError("直接配合执行意外主动移动了目标模组。")

    source = Path(str(execution.get("sourceAssemblyPath") or "")).resolve()
    output = Path(str(execution.get("outputAssemblyPath") or "")).resolve()
    if not source.is_file() or not output.is_file():
        raise AssemblyConversationError("直接配合执行的源或输出装配体不存在。")
    if _sha256_file(source) != str(execution.get("sourceAssemblySha256After") or ""):
        raise AssemblyConversationError("直接配合执行源装配体哈希已变化。")
    if _sha256_file(output) != str(execution.get("outputAssemblySha256") or ""):
        raise AssemblyConversationError("直接配合执行输出装配体哈希不匹配。")

    revision = int(context.get("revision") or 0)
    path = conversation_path(context_path)
    with _LOCK:
        ledger = load_conversation(context_path, context)
        turn = next(
            (
                row
                for row in ledger["turns"]
                if int(row.get("contextRevision") or -1) == revision
            ),
            None,
        )
        if turn is None:
            raise AssemblyConversationError(f"找不到当前上下文修订{revision}对应的命令轮次。")

        prior_job_bindings = [
            job
            for row in ledger["turns"]
            for job in row.get("jobs") or []
            if _is_continuable_job_binding(job)
        ]
        prior_checkpoints = [job.get("demoCheckpoint") or {} for job in prior_job_bindings]
        prior_edits = [
            edit
            for row in ledger["turns"]
            for edit in row.get("cadEdits") or []
            if edit.get("status") == "succeeded"
        ]
        accepted_sources = {
            str(Path(str(item.get("assemblyPath") or "")).resolve()).casefold()
            for item in prior_checkpoints
            if item.get("assemblyPath")
        }
        accepted_sources.update(
            str(Path(str(item.get("assemblyPath") or "")).resolve()).casefold()
            for item in prior_edits
            if item.get("assemblyPath")
        )
        if str(source).casefold() not in accepted_sources:
            raise AssemblyConversationError(
                "直接配合执行的源装配体不是当前会话中已签认的检查点。"
            )
        source_job = next(
            (
                job
                for job in reversed(prior_job_bindings)
                if str(
                    Path(str((job.get("demoCheckpoint") or {}).get("assemblyPath") or "")).resolve()
                ).casefold()
                == str(source).casefold()
            ),
            None,
        )
        source_edit = next(
            (
                edit
                for edit in reversed(prior_edits)
                if str(Path(str(edit.get("assemblyPath") or "")).resolve()).casefold()
                == str(source).casefold()
            ),
            None,
        )

        execution_digest = hashlib.sha256(
            execution_path.read_bytes()
        ).hexdigest()
        binding = {
            "editId": "direct-mate-" + execution_digest[:16],
            "bindingKind": "direct_existing_component_mate_edit",
            "status": "succeeded",
            "sourceJobId": (
                source_job.get("jobId") if source_job else (source_edit or {}).get("sourceJobId")
            ),
            "projectId": (
                source_job.get("projectId") if source_job else (source_edit or {}).get("projectId")
            ),
            "targetModuleToken": execution.get("targetModuleToken"),
            "sourceAssemblyPath": str(source),
            "sourceAssemblySha256": execution.get("sourceAssemblySha256After"),
            "assemblyPath": str(output),
            "assemblySha256": execution.get("outputAssemblySha256"),
            "effectiveGraphPath": execution.get("effectiveGraphPath"),
            "effectiveGraphSha256": execution.get("effectiveGraphSha256"),
            "executionEvidencePath": str(execution_path.resolve()),
            "executionEvidenceSha256": execution_digest,
            "createdOrReplacedMateNames": deepcopy(
                tool.get("CreatedOrReplacedMateNames")
                or tool.get("createdOrReplacedMateNames")
                or []
            ),
            "removedOrReplacedSourceMateNames": deepcopy(
                tool.get("RemovedOrReplacedSourceMateNames")
                or tool.get("removedOrReplacedSourceMateNames")
                or []
            ),
            "rigidBodyDofAnalysis": deepcopy(
                (execution.get("preflight") or {}).get("rigidBodyDofAnalysis")
            ),
            "committedAt": execution.get("finishedAtUtc") or _now(),
        }
        edits = turn.setdefault("cadEdits", [])
        existing = next(
            (row for row in edits if row.get("editId") == binding["editId"]), None
        )
        if existing is None:
            edits.append(binding)
        elif existing.get("assemblySha256") != binding["assemblySha256"]:
            raise AssemblyConversationError("同一直接配合证据已绑定不同的输出装配体。")
        else:
            existing.update(binding)
        ledger["updatedAt"] = _now()
        _write(path, ledger)
    return ledger


def find_direct_mate_execution(
    context_path: Path,
    context: dict[str, Any],
    edit_id: str,
) -> dict[str, Any]:
    requested = str(edit_id or "").strip()
    if not requested:
        raise AssemblyConversationError("缺少直接配合实体检查点编号。")
    ledger = load_conversation(context_path, context)
    matches = [
        edit
        for turn in ledger.get("turns") or []
        for edit in turn.get("cadEdits") or []
        if str(edit.get("editId") or "") == requested
    ]
    if len(matches) != 1:
        raise AssemblyConversationError(
            f"直接配合实体检查点{requested}解析到{len(matches)}项，预期唯一一项。"
        )
    result = deepcopy(matches[0])
    if result.get("status") != "succeeded":
        raise AssemblyConversationError("只有成功的直接配合实体检查点可以续装。")
    return result


def conversation_snapshot(
    context_path: Path,
    context: dict[str, Any],
    job_loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return refreshed history and the latest safe Demo continuation seed."""

    path = conversation_path(context_path)
    with _LOCK:
        ledger = load_conversation(context_path, context)
        changed = False
        latest: dict[str, Any] | None = None
        for turn in ledger["turns"]:
            for binding in turn.get("jobs") or []:
                if job_loader is not None:
                    try:
                        current = job_loader(str(binding["jobId"]))
                    except (OSError, ValueError, TypeError) as exc:
                        message = str(exc)
                        if binding.get("lookupError") != message:
                            binding["lookupError"] = message
                            changed = True
                    else:
                        refreshed = {
                            "status": current.get("status"),
                            "assemblyStatus": current.get("assemblyStatus"),
                            "collisionStatus": current.get("collisionStatus"),
                            "demoCheckpoint": deepcopy(current.get("demoCheckpoint")),
                            "updatedAt": current.get("updatedAt"),
                        }
                        for key, value in refreshed.items():
                            if binding.get(key) != value:
                                binding[key] = value
                                changed = True
                        if "lookupError" in binding:
                            binding.pop("lookupError", None)
                            changed = True
                checkpoint = binding.get("demoCheckpoint")
                if _is_continuable_job_binding(binding):
                    candidate = {
                        "jobId": binding["jobId"],
                        "projectId": binding.get("projectId"),
                        "validationProfile": binding.get("validationProfile"),
                        "assemblyStatus": binding.get("assemblyStatus"),
                        "collisionStatus": binding.get("collisionStatus"),
                        "contextRevision": turn["contextRevision"],
                        "contextDigest": turn["contextDigest"],
                        "assemblyPath": checkpoint["assemblyPath"],
                        "committedAt": checkpoint.get("committedAt"),
                    }
                    if latest is None or int(candidate["contextRevision"]) >= int(
                        latest["contextRevision"]
                    ):
                        latest = candidate
            for edit in turn.get("cadEdits") or []:
                if edit.get("status") != "succeeded" or not edit.get("assemblyPath"):
                    continue
                candidate = {
                    "jobId": edit.get("sourceJobId"),
                    "editId": edit.get("editId"),
                    "bindingKind": edit.get("bindingKind"),
                    "projectId": edit.get("projectId"),
                    "contextRevision": turn["contextRevision"],
                    "contextDigest": turn["contextDigest"],
                    "assemblyPath": edit["assemblyPath"],
                    "assemblySha256": edit.get("assemblySha256"),
                    "committedAt": edit.get("committedAt"),
                }
                if latest is None or int(candidate["contextRevision"]) >= int(
                    latest["contextRevision"]
                ):
                    latest = candidate
        if changed:
            ledger["updatedAt"] = _now()
            _write(path, ledger)
    return {
        "success": True,
        "schemaVersion": CONVERSATION_SCHEMA,
        "contextId": context["contextId"],
        "currentContextRevision": int(context.get("revision") or 0),
        "currentContextDigest": context.get("contextDigest"),
        "turnCount": len(ledger["turns"]),
        "turns": deepcopy(ledger["turns"]),
        "latestSuccessfulDemo": latest,
        "continuationReady": latest is not None,
        "ledgerPath": str(path),
    }

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "released-long-chain-cad-closure/v1"
ORDER_COMPATIBILITY_SCHEMA_VERSION = "released-order-compatibility-cad-closure/v1"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cad_result_path(step: dict[str, Any]) -> Path | None:
    checkpoint = step.get("checkpoint") or {}
    matches = [
        Path(str(value))
        for value in checkpoint.get("cadActionEvidencePaths") or []
        if Path(str(value)).name == "cad-result.json"
    ]
    return matches[0] if len(matches) == 1 else None


def _normalized_path(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return str(Path(text).resolve()).casefold()


def _cumulative_links(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = list(job.get("steps") or [])
    links: list[dict[str, Any]] = []
    for index in range(1, len(steps)):
        previous = steps[index - 1]
        current = steps[index]
        previous_checkpoint = previous.get("checkpoint") or {}
        current_checkpoint = current.get("checkpoint") or {}
        cad_path = _cad_result_path(current)
        cad = _read_json(cad_path) if cad_path is not None and cad_path.is_file() else {}
        previous_output = previous_checkpoint.get("assemblyPath")
        current_input = current_checkpoint.get("inputAssemblyPath")
        cad_source = cad.get("sourceAssemblyPath")
        checks = {
            "checkpointConsumesPreviousOutput": (
                _normalized_path(previous_output) == _normalized_path(current_input)
            ),
            "cadConsumesPreviousOutput": (
                _normalized_path(previous_output) == _normalized_path(cad_source)
            ),
            "previousOutputExists": bool(previous_output)
            and Path(str(previous_output)).is_file(),
        }
        links.append(
            {
                "fromStepId": previous.get("stepId"),
                "toStepId": current.get("stepId"),
                "previousOutputAssemblyPath": previous_output,
                "checkpointInputAssemblyPath": current_input,
                "cadSourceAssemblyPath": cad_source,
                "status": "passed" if all(checks.values()) else "blocked",
                "checks": checks,
            }
        )
    return links


def _summarize_step(step: dict[str, Any]) -> dict[str, Any]:
    checkpoint = step.get("checkpoint") or {}
    cad_path = _cad_result_path(step)
    cad = _read_json(cad_path) if cad_path is not None and cad_path.is_file() else {}
    tool = cad.get("toolResult") or {}
    output = Path(str(cad.get("outputAssemblyPath") or checkpoint.get("assemblyPath") or ""))
    output_exists = output.is_file()
    output_digest = _sha256(output) if output_exists else None
    requested = int(tool.get("RequestedMateCount") or 0)
    created = int(tool.get("CreatedMateCount") or 0)
    checks = {
        "stepSucceeded": step.get("status") == "succeeded" and cad.get("success") is True,
        "cadResultPresent": cad_path is not None and cad_path.is_file(),
        "allRequestedMatesCreated": requested > 0 and requested == created,
        "constraintStateAccepted": tool.get("TargetConstraintStateAccepted") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "saveCloseReopenVerified": (
            tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and tool.get("ComponentSemanticsMatch") is True
            and cad.get("outputClosedAfterVerification") is True
        ),
        "sourceAssemblyUnchanged": cad.get("sourceAssemblyUnchanged") is True,
        "targetSourceSessionClean": cad.get("targetSourceSessionClean") is True,
        "noCaseAnchor": tool.get("TargetCaseAnchored") is False,
        "noLeafPoseAnchor": (
            int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
        ),
        "outputAssemblyExists": output_exists,
        "outputDigestMatchesEvidence": (
            bool(cad.get("outputAssemblySha256"))
            and output_digest == cad.get("outputAssemblySha256")
        ),
    }
    return {
        "stepId": step.get("stepId"),
        "moduleToken": step.get("moduleToken"),
        "status": "passed" if all(checks.values()) else "blocked",
        "attemptCount": step.get("attemptCount"),
        "durationSeconds": (step.get("attempts") or [{}])[-1].get("durationSeconds"),
        "assemblyPath": str(output),
        "assemblySha256": output_digest,
        "cadEvidencePath": str(cad_path) if cad_path is not None else None,
        "constraintObservation": {
            "targetFullyConstrained": tool.get("TargetFullyConstrained") is True,
            "targetConstraintStateAccepted": tool.get("TargetConstraintStateAccepted") is True,
            "componentSemanticsMatch": tool.get("ComponentSemanticsMatch") is True,
        },
        "checks": checks,
    }


def build_released_long_chain_closure(
    job_directory: Path,
    *,
    expected_order: Sequence[str],
    expected_release_id: str,
) -> dict[str, Any]:
    directory = job_directory.resolve()
    job_path = directory / "job.json"
    job = _read_json(job_path)
    plan = job.get("plan") or {}
    authority = plan.get("releaseAuthority") or {}
    binding = authority.get("binding") or plan.get("relationReleaseBinding") or {}
    steps = [_summarize_step(step) for step in job.get("steps") or []]
    actual_order = [str(step.get("moduleToken") or "") for step in job.get("steps") or []]
    authorized = set(authority.get("authorizedDrivingTemplateIds") or [])
    used = set(authority.get("usedDrivingTemplateIds") or [])
    final_path = Path(str((job.get("lastCommittedCheckpoint") or {}).get("assemblyPath") or ""))
    checks = {
        "jobSucceeded": job.get("status") == "succeeded",
        "assemblyCompleted": job.get("assemblyStatus") == "assembled",
        "expectedOrderExecuted": actual_order == [str(value).upper() for value in expected_order],
        "releaseAuthorityVerified": authority.get("status") == "verified",
        "expectedReleaseBound": binding.get("releaseId") == expected_release_id,
        "allReleasedTemplatesUsed": bool(authorized) and authorized == used,
        "allPacketsPassed": bool(steps) and all(step["status"] == "passed" for step in steps),
        "finalAssemblyExists": final_path.is_file(),
        "collisionDeliberatelyNotEvaluated": job.get("collisionStatus") == "not_evaluated",
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "jobId": job.get("jobId"),
        "jobPath": str(job_path),
        "projectId": job.get("projectId"),
        "contextId": plan.get("contextId"),
        "releaseId": binding.get("releaseId"),
        "releaseDigest": binding.get("releaseDigest"),
        "expectedOrder": [str(value).upper() for value in expected_order],
        "actualOrder": actual_order,
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "checks": checks,
        "steps": steps,
        "finalAssemblyPath": str(final_path),
        "finalAssemblySha256": _sha256(final_path) if final_path.is_file() else None,
        "collisionStatus": "not_evaluated",
        "statement": (
            "自然语言命令已绑定不可变关系发布，并完成真实CAD逐包累计、"
            "配合求解、保存关闭重开与证据验签；碰撞/B-rep不属于本闭环。"
        ),
    }


def write_released_long_chain_closure(
    job_directory: Path,
    output: Path,
    *,
    expected_order: Sequence[str],
    expected_release_id: str,
) -> Path:
    report = build_released_long_chain_closure(
        job_directory,
        expected_order=expected_order,
        expected_release_id=expected_release_id,
    )
    target = output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)
    return target


def build_released_order_compatibility_closure(
    job_directories: Sequence[Path],
    *,
    expected_orders: Sequence[Sequence[str]],
    expected_release_id: str,
    base_module_token: str,
) -> dict[str, Any]:
    if len(job_directories) < 2:
        raise ValueError("At least two job directories are required")
    if len(job_directories) != len(expected_orders):
        raise ValueError("job_directories and expected_orders must have equal length")

    cases: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    for directory, expected_order in zip(job_directories, expected_orders, strict=True):
        resolved = directory.resolve()
        job = _read_json(resolved / "job.json")
        closure = build_released_long_chain_closure(
            resolved,
            expected_order=expected_order,
            expected_release_id=expected_release_id,
        )
        links = _cumulative_links(job)
        plan = job.get("plan") or {}
        authority = plan.get("releaseAuthority") or {}
        actual_order = [str(value).upper() for value in closure["actualOrder"]]
        semantic_signature = sorted(
            [str(base_module_token).upper(), *actual_order]
        )
        cases.append(
            {
                **closure,
                "semanticModuleSignature": semantic_signature,
                "authorizedDrivingTemplateIds": sorted(
                    authority.get("authorizedDrivingTemplateIds") or []
                ),
                "usedDrivingTemplateIds": sorted(
                    authority.get("usedDrivingTemplateIds") or []
                ),
                "cumulativeLinks": links,
                "allCumulativeLinksPassed": bool(links)
                and all(link["status"] == "passed" for link in links),
            }
        )
        jobs.append(job)

    actual_orders = [tuple(case["actualOrder"]) for case in cases]
    semantic_signatures = [tuple(case["semanticModuleSignature"]) for case in cases]
    release_digests = {case.get("releaseDigest") for case in cases}
    authorized_sets = {
        tuple(case["authorizedDrivingTemplateIds"]) for case in cases
    }
    used_sets = {tuple(case["usedDrivingTemplateIds"]) for case in cases}
    final_digests = [case.get("finalAssemblySha256") for case in cases]
    checks = {
        "allCasesPassed": all(case["status"] == "passed" for case in cases),
        "ordersAreDistinct": len(set(actual_orders)) == len(actual_orders),
        "sameSemanticModuleSet": len(set(semantic_signatures)) == 1,
        "sameReleaseDigest": len(release_digests) == 1 and None not in release_digests,
        "sameAuthorizedTemplateSet": len(authorized_sets) == 1,
        "sameUsedTemplateSet": len(used_sets) == 1,
        "allCumulativeLinksPassed": all(
            case["allCumulativeLinksPassed"] for case in cases
        ),
        "allFinalAssembliesExist": all(
            Path(str(case["finalAssemblyPath"])).is_file() for case in cases
        ),
        "allFinalDigestsRecorded": all(bool(value) for value in final_digests),
        "collisionDeliberatelyNotEvaluated": all(
            job.get("collisionStatus") == "not_evaluated" for job in jobs
        ),
    }
    return {
        "schemaVersion": ORDER_COMPATIBILITY_SCHEMA_VERSION,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "expectedReleaseId": expected_release_id,
        "baseModuleToken": str(base_module_token).upper(),
        "checks": checks,
        "cases": cases,
        "semanticResultEquivalent": (
            checks["allCasesPassed"]
            and checks["sameSemanticModuleSet"]
            and checks["sameReleaseDigest"]
            and checks["sameUsedTemplateSet"]
            and checks["allCumulativeLinksPassed"]
        ),
        "finalAssemblyBinaryIdentical": len(set(final_digests)) == 1,
        "binaryIdentityRequired": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "两种插入顺序均绑定同一不可变发布，逐步消费前一检查点并完成真实CAD"
            "保存关闭重开；语义模组集合与驱动模板集合一致。SLDASM二进制摘要不作为"
            "顺序兼容判据，碰撞/B-rep不属于本闭环。"
        ),
    }


def _order_compatibility_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 跨项目累计装配顺序兼容闭环",
        "",
        f"- 状态：`{report['status']}`",
        f"- 关系发布：`{report['expectedReleaseId']}`",
        f"- 基座模组：`{report['baseModuleToken']}`",
        f"- 语义结果等价：`{str(report['semanticResultEquivalent']).lower()}`",
        f"- 二进制完全一致：`{str(report['finalAssemblyBinaryIdentical']).lower()}`（非验收项）",
        "- 碰撞/B-rep：`not_evaluated`（非本轮验收项）",
        "",
        "## 两种顺序",
        "",
    ]
    for case in report["cases"]:
        order = " → ".join(case["actualOrder"])
        lines.extend(
            [
                f"- `{order}`：`{case['status']}`，耗时 "
                f"`{case.get('executionDurationSeconds')}` 秒",
                f"  - 最终装配体：`{case['finalAssemblyPath']}`",
                f"  - SHA-256：`{case['finalAssemblySha256']}`",
                f"  - 累计链路：`{str(case['allCumulativeLinksPassed']).lower()}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 判定",
            "",
            report["statement"],
            "",
        ]
    )
    return "\n".join(lines)


def write_released_order_compatibility_closure(
    job_directories: Sequence[Path],
    output: Path,
    *,
    expected_orders: Sequence[Sequence[str]],
    expected_release_id: str,
    base_module_token: str,
    markdown_output: Path | None = None,
) -> tuple[Path, Path | None]:
    report = build_released_order_compatibility_closure(
        job_directories,
        expected_orders=expected_orders,
        expected_release_id=expected_release_id,
        base_module_token=base_module_token,
    )
    target = output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)
    markdown_target: Path | None = None
    if markdown_output is not None:
        markdown_target = markdown_output.resolve()
        markdown_target.parent.mkdir(parents=True, exist_ok=True)
        temporary_markdown = markdown_target.with_suffix(
            markdown_target.suffix + ".tmp"
        )
        temporary_markdown.write_text(
            _order_compatibility_markdown(report), encoding="utf-8"
        )
        temporary_markdown.replace(markdown_target)
    return target, markdown_target

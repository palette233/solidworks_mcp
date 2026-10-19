from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _checkpoint(path: Path, expected_target: str, expected_mates: list[str]) -> dict[str, Any]:
    payload = _read(path)
    tool = payload.get("toolResult") or {}
    output = Path(str(payload.get("outputAssemblyPath") or ""))
    source = Path(str(payload.get("sourceAssemblyPath") or ""))
    observed_mates = [str(row.get("MateName") or "") for row in tool.get("MateResults") or []]
    verifications = tool.get("MateVerifications") or []
    checks = {
        "runSucceeded": payload.get("success") is True and tool.get("Success") is True,
        "independentInsert": (
            tool.get("OriginalComponentRemoved") is True
            and tool.get("IndependentComponentInserted") is True
        ),
        "expectedMateBundle": (
            observed_mates == expected_mates
            and int(tool.get("RequestedMateCount") or 0) == len(expected_mates)
            and int(tool.get("CreatedMateCount") or 0) == len(expected_mates)
        ),
        "mateVerificationsPassed": (
            len(verifications) == len(expected_mates)
            and all(row.get("Found") is True for row in verifications)
        ),
        "fullyConstrained": tool.get("TargetFullyConstrained") is True,
        "constraintStateAccepted": tool.get("TargetConstraintStateAccepted") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "saveCloseReopenVerified": (
            tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and tool.get("ComponentSemanticsMatch") is True
        ),
        "noCaseAnchor": tool.get("TargetCaseAnchored") is False,
        "noLeafPoseAnchor": (
            int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
        ),
        "outputAssemblyExists": output.is_file(),
        "sourceAssemblyStillMatchesRecordedDigest": (
            source.is_file()
            and bool(payload.get("sourceAssemblySha256"))
            and _sha256(source) == payload.get("sourceAssemblySha256")
        ),
        "targetTokenMatches": str(payload.get("targetModuleToken") or "").upper() == expected_target,
    }
    return {
        "targetModuleToken": expected_target,
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": _sha256(source) if source.is_file() else None,
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": _sha256(output) if output.is_file() else None,
        "durationSeconds": payload.get("durationSeconds"),
        "mateNames": observed_mates,
        "evidencePath": str(path.resolve()),
    }


def build_project02_a800_a180_nonanchor_closure(
    a800_result_path: Path,
    a180_result_path: Path,
    rejected_overconstraint_path: Path,
) -> dict[str, Any]:
    a800 = _checkpoint(
        a800_result_path.resolve(),
        "A800",
        ["重合35", "宽度9", "A800_LOCATING_DISTANCE_X"],
    )
    a180 = _checkpoint(
        a180_result_path.resolve(),
        "A180",
        ["重合34", "距离24", "槽口3"],
    )
    rejected = _read(rejected_overconstraint_path.resolve())
    rejected_tool = rejected.get("toolResult") or {}
    rejected_mates = rejected_tool.get("MateResults") or []
    checks = {
        "a800CheckpointPassed": a800["status"] == "passed",
        "a180CheckpointPassed": a180["status"] == "passed",
        "a180ConsumesA800Checkpoint": (
            Path(a180["sourceAssemblyPath"]).resolve()
            == Path(a800["outputAssemblyPath"]).resolve()
            and a180["sourceAssemblySha256"] == a800["outputAssemblySha256"]
        ),
        "overconstraintFeedbackCaptured": (
            rejected.get("success") is False
            and any(
                row.get("ErrorName") == "swAddMateError_OverDefinedAssembly"
                for row in rejected_mates
            )
        ),
        "collisionDeliberatelyNotEvaluated": True,
    }
    return {
        "schemaVersion": "project02-a800-a180-nonanchor-cad-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project02",
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "checkpoints": [a800, a180],
        "rejectedCandidateEvidence": {
            "path": str(rejected_overconstraint_path.resolve()),
            "reason": "A180 source slot bundle was already closed; adding an extra X distance over-defined the assembly.",
            "mateNames": [str(row.get("MateName") or "") for row in rejected_mates],
        },
        "finalAssemblyPath": a180["outputAssemblyPath"],
        "finalAssemblySha256": a180["outputAssemblySha256"],
        "totalCadDurationSeconds": sum(float(row.get("durationSeconds") or 0.0) for row in (a800, a180)),
        "collisionStatus": "not_evaluated",
        "statement": (
            "A800通过原型估计X基准消除长轴滑移；A180恢复原型槽口驱动后无需额外距离。"
            "两步均由非原型初始位姿、零case/叶位姿锚点完成真实CAD保存重开闭环。"
        ),
    }


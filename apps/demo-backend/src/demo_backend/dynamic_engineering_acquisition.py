"""Audit engineering evidence required by the Project02 dynamic gate.

The functions in this module deliberately separate *available CAD snapshots*
from *authoritative motion states*.  A state name alone is not evidence: the
saved assembly must exist, the selected A700 moving roots must have a distinct
module-local pose, and the snapshot must be explicitly accepted by its source
audit.  Likewise, an ordinary distance mate is not promoted to an axis limit.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "project02-dynamic-engineering-source-audit/v1"
A700_MOVING_ROOTS = ("A710", "A720", "A730")


def _pick(row: dict[str, Any], name: str, default: Any = None) -> Any:
    return row.get(name, row.get(name[:1].lower() + name[1:], default))


def _matrix3(values: list[float]) -> list[list[float]]:
    if len(values) != 16:
        raise ValueError("SolidWorks transform must contain 16 values")
    return [
        [float(values[0]), float(values[1]), float(values[2])],
        [float(values[3]), float(values[4]), float(values[5])],
        [float(values[6]), float(values[7]), float(values[8])],
    ]


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [[matrix[column][row] for column in range(3)] for row in range(3)]


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][k] * right[k][column] for k in range(3)) for column in range(3)]
        for row in range(3)
    ]


def _multiply_vector(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(matrix[row][k] * vector[k] for k in range(3)) for row in range(3)]


def _module_local_pose(root: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    root_transform = [float(value) for value in _pick(root, "Transform", [])]
    child_transform = [float(value) for value in _pick(child, "Transform", [])]
    root_rotation = _matrix3(root_transform)
    child_rotation = _matrix3(child_transform)
    inverse_root_rotation = _transpose(root_rotation)
    delta = [child_transform[9 + axis] - root_transform[9 + axis] for axis in range(3)]
    local_translation = _multiply_vector(inverse_root_rotation, delta)
    local_rotation = _multiply(inverse_root_rotation, child_rotation)
    return {
        "translationMeters": [round(value, 8) for value in local_translation],
        "rotation": [round(value, 8) for row in local_rotation for value in row],
        "referencedConfiguration": str(_pick(child, "ReferencedConfiguration", "")),
        "solvingState": str(_pick(child, "SolvingStateName", "")),
    }


def a700_snapshot_fingerprint(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = snapshot.get("components") or []
    root = next((row for row in rows if str(row.get("relativeHierarchyPath")) == "@root"), None)
    if not root:
        raise ValueError("A700 snapshot has no @root component")
    selected: dict[str, Any] = {}
    for token in A700_MOVING_ROOTS:
        matches = [
            row
            for row in rows
            if int(row.get("depthFromModuleRoot", -1)) == 1
            and token.casefold() in str(row.get("relativeHierarchyPath") or "").casefold()
        ]
        if len(matches) != 1:
            raise ValueError(f"A700 snapshot resolves {token} to {len(matches)} roots")
        selected[token] = _module_local_pose(root, matches[0])
    canonical = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "movingRootLocalPoses": selected,
    }


def audit_a700_state_sources(
    candidates: list[dict[str, Any]],
    *,
    required_state_ids: tuple[str, ...] = ("cleaning", "weighing", "maintenance"),
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    accepted_fingerprints: set[str] = set()
    accepted_state_ids: set[str] = set()
    for candidate in candidates:
        state_id = str(candidate.get("stateId") or "").strip()
        snapshot_path = Path(str(candidate.get("snapshotPath") or ""))
        assembly_path = Path(str(candidate.get("assemblyPath") or ""))
        reasons: list[str] = []
        fingerprint_payload: dict[str, Any] | None = None
        if state_id not in required_state_ids:
            reasons.append("stateId不属于要求的三个工程状态")
        if not snapshot_path.is_file():
            reasons.append("姿态快照不存在")
        if not assembly_path.is_file():
            reasons.append("对应装配体不存在")
        if candidate.get("sourceAuditAccepted") is not True:
            reasons.append("来源审计尚未明确接受")
        if not reasons:
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
                fingerprint_payload = a700_snapshot_fingerprint(snapshot)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                reasons.append(f"无法形成模块局部姿态指纹：{exc}")
        fingerprint = (fingerprint_payload or {}).get("fingerprint")
        if fingerprint and fingerprint in accepted_fingerprints:
            reasons.append("与另一已接受状态的A710/A720/A730局部姿态相同")
        if state_id and state_id in accepted_state_ids:
            reasons.append("同一状态被重复登记")
        accepted = not reasons
        if accepted:
            accepted_fingerprints.add(str(fingerprint))
            accepted_state_ids.add(state_id)
        rows.append(
            {
                "stateId": state_id or None,
                "acceptedAsDistinctRealState": accepted,
                "snapshotPath": str(snapshot_path.resolve()) if snapshot_path else None,
                "assemblyPath": str(assembly_path.resolve()) if assembly_path else None,
                "fingerprint": fingerprint,
                "movingRootLocalPoses": (fingerprint_payload or {}).get("movingRootLocalPoses"),
                "reasons": reasons,
            }
        )
    missing = [state for state in required_state_ids if state not in accepted_state_ids]
    complete = not missing and len(accepted_fingerprints) == len(required_state_ids)
    return {
        "requiredStateIds": list(required_state_ids),
        "candidateCount": len(rows),
        "acceptedDistinctStateCount": len(accepted_fingerprints),
        "complete": complete,
        "missingStateIds": missing,
        "states": rows,
    }


def audit_a100_limit_source(source: dict[str, Any]) -> dict[str, Any]:
    mate_type = str(source.get("mateType") or "")
    limit_kind = str(source.get("limitKind") or "")
    lower = source.get("minimumMeters")
    upper = source.get("maximumMeters")
    finite_range = bool(
        isinstance(lower, (int, float))
        and isinstance(upper, (int, float))
        and math.isfinite(float(lower))
        and math.isfinite(float(upper))
        and float(lower) < float(upper)
    )
    accepted = bool(
        source.get("sourceReference")
        and source.get("authority") in {"vendor-confirmed", "measured-limits"}
        and finite_range
        and (limit_kind in {"mechanical-stop", "software-limit", "limit-mate"})
        and (mate_type != "swMateDISTANCE" or limit_kind != "limit-mate")
    )
    reasons: list[str] = []
    if not source.get("sourceReference"):
        reasons.append("缺少可追溯来源编号")
    if source.get("authority") not in {"vendor-confirmed", "measured-limits"}:
        reasons.append("来源不是厂商确认或机械限位实测")
    if not finite_range:
        reasons.append("未提供有效[min,max]范围")
    if limit_kind not in {"mechanical-stop", "software-limit", "limit-mate"}:
        reasons.append("未证明它是机械端点、软件限位或限位配合")
    if mate_type == "swMateDISTANCE" and limit_kind == "limit-mate":
        reasons.append("普通距离配合不能作为限位配合")
    return {"accepted": accepted, "reasons": reasons, **source}


def build_dynamic_source_audit(
    a700_candidates: list[dict[str, Any]],
    a100_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    a700 = audit_a700_state_sources(a700_candidates)
    a100_rows = [audit_a100_limit_source(row) for row in a100_sources]
    accepted_a100 = [row for row in a100_rows if row["accepted"]]
    return {
        "schemaVersion": SCHEMA,
        "projectId": "project02",
        "a700": a700,
        "a100": {
            "candidateCount": len(a100_rows),
            "acceptedLimitSourceCount": len(accepted_a100),
            "complete": len(accepted_a100) >= 6,
            "required": "left/right valve x/y/z; each axis needs a traceable [min,max] source",
            "sources": a100_rows,
        },
        "productionEvidenceReady": a700["complete"] and len(accepted_a100) >= 6,
    }

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .parameter_authority_registry import audit_parameter_authorities


SCHEMA_VERSION = "project02-inferred-positioning-standard/v1"
PRODUCTION_AUTHORITIES = {"vendor-confirmed", "engineer-confirmed"}
BASELINE_AUTHORITIES = {
    "cad-mate-measured",
    "cad-geometry-inferred",
    "prototype-calibrated",
    "requirements-derived",
    "temporary-estimate",
}


class Project02PositioningStandardError(ValueError):
    pass


def positioning_standard_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "project_profiles"
        / "project02_positioning_standard.json"
    )


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Project02PositioningStandardError(f"{label}必须为对象。")
    return value


def _require_non_empty_string(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise Project02PositioningStandardError(f"{label}不能为空。")
    return result


def _validate_authority(value: Any, label: str) -> str:
    authority = _require_non_empty_string(value, label)
    if authority not in PRODUCTION_AUTHORITIES | BASELINE_AUTHORITIES:
        raise Project02PositioningStandardError(f"{label}不受支持：{authority}")
    return authority


def _validate_working_distance(profile: dict[str, Any]) -> None:
    distance = _require_mapping(profile.get("workingDistanceMeters"), "A180工作距离")
    try:
        minimum = float(distance["minimum"])
        preferred = float(distance["preferred"])
        maximum = float(distance["maximum"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Project02PositioningStandardError(
            "A180工作距离必须包含数值minimum/preferred/maximum。"
        ) from exc
    if not (0 < minimum <= preferred <= maximum):
        raise Project02PositioningStandardError(
            "A180工作距离必须满足0 < minimum <= preferred <= maximum。"
        )


def validate_project02_positioning_standard(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise Project02PositioningStandardError("不支持的Project02定位标准版本。")
    if str(payload.get("projectId") or "").lower() != "project02":
        raise Project02PositioningStandardError("定位标准projectId必须为project02。")
    _require_non_empty_string(payload.get("standardVersion"), "standardVersion")

    authority_policy = payload.get("authorityPolicy")
    if not isinstance(authority_policy, list) or not authority_policy:
        raise Project02PositioningStandardError("authorityPolicy必须为非空数组。")
    ranks: list[int] = []
    authorities: set[str] = set()
    for item in authority_policy:
        row = _require_mapping(item, "authorityPolicy条目")
        authority = _validate_authority(row.get("authority"), "authorityPolicy.authority")
        if authority in authorities:
            raise Project02PositioningStandardError(f"权威等级重复：{authority}")
        authorities.add(authority)
        try:
            ranks.append(int(row["rank"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise Project02PositioningStandardError("authorityPolicy.rank必须为整数。") from exc
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise Project02PositioningStandardError("authorityPolicy.rank必须从1连续排列。")

    frame = _require_mapping(payload.get("coordinateFrame"), "coordinateFrame")
    if frame.get("baseModule") != "A600":
        raise Project02PositioningStandardError("Project02定位坐标系必须以A600为基座。")
    axes = _require_mapping(frame.get("axes"), "coordinateFrame.axes")
    if set(axes) != {"X", "Y", "Z"}:
        raise Project02PositioningStandardError("定位坐标系必须显式定义X/Y/Z三轴。")

    modules = _require_mapping(payload.get("modules"), "modules")
    if set(modules) != {"A800", "A180"}:
        raise Project02PositioningStandardError("当前定位标准必须且只能定义A800和A180。")

    a800 = _require_mapping(modules["A800"], "modules.A800")
    a800_mechanical = _require_mapping(a800.get("mechanical"), "A800机械定位")
    if a800_mechanical.get("baseModule") != "A600":
        raise Project02PositioningStandardError("A800机械定位基座必须为A600。")
    mate_names = {
        str(row.get("mateName"))
        for row in a800_mechanical.get("drivingRelations") or []
        if isinstance(row, dict)
    }
    if not {"重合35", "宽度9"}.issubset(mate_names):
        raise Project02PositioningStandardError("A800必须保留重合35和宽度9两条驱动关系。")
    residual = _require_mapping(a800_mechanical.get("residualDofClosure"), "A800剩余自由度")
    if residual.get("dof") != "translation-along-X":
        raise Project02PositioningStandardError("A800必须显式记录沿X方向的剩余平移自由度。")
    _validate_authority(residual.get("authority"), "A800剩余自由度权威")
    anchor = residual.get("anchorPointFrameMeters")
    if not isinstance(anchor, list) or len(anchor) != 3:
        raise Project02PositioningStandardError("A800剩余自由度必须提供三维案例锚点。")
    try:
        [float(value) for value in anchor]
    except (TypeError, ValueError) as exc:
        raise Project02PositioningStandardError("A800案例锚点必须为三个数值。") from exc

    a180 = _require_mapping(modules["A180"], "modules.A180")
    a180_mechanical = _require_mapping(a180.get("mechanical"), "A180机械定位")
    if a180_mechanical.get("baseModule") != "A600":
        raise Project02PositioningStandardError("A180机械定位基座必须为A600。")
    a180_relations = {
        str(row.get("mateName")): row
        for row in a180_mechanical.get("drivingRelations") or []
        if isinstance(row, dict)
    }
    if not {"重合34", "距离24"}.issubset(a180_relations):
        raise Project02PositioningStandardError("A180必须保留重合34和距离24两条驱动关系。")
    try:
        distance = float(a180_relations["距离24"]["distanceMeters"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Project02PositioningStandardError("A180距离24缺少有效距离值。") from exc
    if distance <= 0:
        raise Project02PositioningStandardError("A180距离24必须大于0。")
    _validate_authority(
        _require_mapping(a180_mechanical.get("residualDofClosure"), "A180剩余自由度").get(
            "authority"
        ),
        "A180剩余自由度权威",
    )

    functional = _require_mapping(a180.get("functional"), "A180功能定位")
    if functional.get("targetModule") != "A800":
        raise Project02PositioningStandardError("A180扫码功能目标必须为A800。")
    if functional.get("sourcePortId") != "A180.scan_optical":
        raise Project02PositioningStandardError("A180扫码功能源端口不正确。")
    if functional.get("targetPortId") != "A800.barcode_target":
        raise Project02PositioningStandardError("A180扫码功能目标端口不正确。")
    _validate_working_distance(functional)
    if not isinstance(functional.get("opticalAxisSignConfirmed"), bool):
        raise Project02PositioningStandardError("A180必须显式记录光轴方向符号是否确认。")

    result = deepcopy(payload)
    result["standardDigest"] = _digest(payload)
    return result


def load_project02_positioning_standard(
    path: Path | None = None,
) -> dict[str, Any]:
    source = (path or positioning_standard_path()).resolve()
    if not source.is_file():
        raise Project02PositioningStandardError(f"Project02定位标准不存在：{source}")
    try:
        raw = json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise Project02PositioningStandardError(f"Project02定位标准JSON无效：{source}") from exc
    if not isinstance(raw, dict):
        raise Project02PositioningStandardError("Project02定位标准根节点必须为对象。")
    result = validate_project02_positioning_standard(raw)
    result["standardPath"] = str(source)
    return result


def positioning_standard_binding(
    standard: dict[str, Any], module_token: str
) -> dict[str, Any]:
    token = str(module_token or "").upper()
    modules = standard.get("modules") or {}
    if token not in modules:
        raise Project02PositioningStandardError(f"定位标准未定义模组：{token}")
    module = modules[token]
    return {
        "schemaVersion": standard["schemaVersion"],
        "standardVersion": standard["standardVersion"],
        "standardDigest": standard["standardDigest"],
        "moduleToken": token,
        "ruleId": module["ruleId"],
        "authorityRequirementIds": list(module.get("authorityRequirementIds") or []),
        "coarseLayoutUseAllowed": bool(
            (standard.get("releaseBoundary") or {}).get("coarseLayoutUseAllowed")
        ),
        "productionUseAllowed": bool(
            (standard.get("releaseBoundary") or {}).get("productionUseAllowed")
        ),
    }


def audit_project02_positioning_standard(
    workspace: Path,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    standard = load_project02_positioning_standard(path)
    evidence_rows: list[dict[str, Any]] = []
    for module_token, module in standard["modules"].items():
        for raw_path in module.get("evidencePaths") or []:
            evidence_path = Path(str(raw_path))
            resolved = evidence_path if evidence_path.is_absolute() else workspace / evidence_path
            evidence_rows.append(
                {
                    "moduleToken": module_token,
                    "path": str(resolved.resolve()),
                    "exists": resolved.is_file(),
                }
            )

    authority_audit = audit_parameter_authorities(workspace, "project02")
    authority_rows = {
        row["requirementId"]: row for row in authority_audit["requirements"]
    }
    required_ids = {
        requirement_id
        for module in standard["modules"].values()
        for requirement_id in module.get("authorityRequirementIds") or []
    }
    unknown_ids = sorted(required_ids - set(authority_rows))
    if unknown_ids:
        raise Project02PositioningStandardError(
            "定位标准引用未知参数权威要求：" + "、".join(unknown_ids)
        )

    missing_evidence = [row for row in evidence_rows if not row["exists"]]
    coarse_allowed = bool(
        (standard.get("releaseBoundary") or {}).get("coarseLayoutUseAllowed")
    )
    coarse_ready = coarse_allowed and not missing_evidence
    pending_authority = sorted(
        requirement_id
        for requirement_id in required_ids
        if not authority_rows[requirement_id]["productionAccepted"]
    )
    provisional_items = []
    if standard["modules"]["A800"]["mechanical"]["residualDofClosure"]["authority"] not in PRODUCTION_AUTHORITIES:
        provisional_items.append("A800沿传输方向仍由Project02原型案例锚点封闭")
    if not standard["modules"]["A180"]["functional"]["opticalAxisSignConfirmed"]:
        provisional_items.append("A180光轴方向符号尚未由厂商或工程师确认")
    if standard["modules"]["A180"]["mechanical"]["readOnlyRelations"]:
        provisional_items.append("A180槽口3仍为只读证据，尚未作为驱动配合")

    production_ready = (
        coarse_ready and not pending_authority and not provisional_items
    )
    return {
        "schemaVersion": "project02-positioning-standard-audit/v1",
        "projectId": "project02",
        "standardVersion": standard["standardVersion"],
        "standardDigest": standard["standardDigest"],
        "coarseLayoutReady": coarse_ready,
        "productionReady": production_ready,
        "evidence": evidence_rows,
        "missingEvidence": missing_evidence,
        "pendingAuthorityRequirementIds": pending_authority,
        "provisionalItems": provisional_items,
        "modules": [
            {
                "moduleToken": token,
                "ruleId": module["ruleId"],
                "mechanicalPositioningDefined": True,
                "functionalPositioningDefined": token != "A180" or bool(module.get("functional")),
                "authorityRequirementIds": list(module.get("authorityRequirementIds") or []),
            }
            for token, module in standard["modules"].items()
        ],
        "resultStatus": (
            "PRODUCTION_POSITIONING_AUTHORITY_ACCEPTED"
            if production_ready
            else "PROJECT02_INFERRED_POSITIONING_STANDARD_READY_FOR_COARSE_LAYOUT"
            if coarse_ready
            else "PROJECT02_POSITIONING_STANDARD_BLOCKED"
        ),
    }

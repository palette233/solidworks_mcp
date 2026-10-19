"""Fail-closed process preflight for a discovered cross-project scanner slot.

Mechanical mounting geometry is necessary but insufficient for a scanner.  A
candidate must also expose a scanner optical origin/axis and a barcode target
with an authoritative working-distance range.  This module deliberately runs
before CAD insertion and never infers missing process geometry from hole
spacing.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


SCHEMA = "cross-project-scanner-process-preflight/v1"


class CrossProjectScannerProcessPreflightError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _belongs_to(port: dict[str, Any], project_id: str, module_token: str) -> bool:
    expected = module_token.upper()
    return any(
        str(row.get("projectId") or "") == project_id
        and str(row.get("moduleToken") or "").upper() == expected
        for row in port.get("provenance") or []
    )


def _functional_ports(
    catalog: dict[str, Any], project_id: str, module_token: str
) -> list[dict[str, Any]]:
    return [
        port
        for port in catalog.get("semanticPorts") or []
        if port.get("category") == "functional"
        and _belongs_to(port, project_id, module_token)
    ]


def _scanner_optical_port(ports: list[dict[str, Any]]) -> dict[str, Any] | None:
    for port in ports:
        geometry = port.get("functionalGeometry") or {}
        if geometry.get("geometryType") == "point_axis":
            return port
    return None


def _barcode_target_port(ports: list[dict[str, Any]]) -> dict[str, Any] | None:
    for port in ports:
        geometry = port.get("functionalGeometry") or {}
        searchable = " ".join(
            [
                str(port.get("displayName") or ""),
                str(geometry.get("portId") or ""),
                *(str(alias) for alias in port.get("aliases") or []),
            ]
        ).lower()
        if geometry.get("geometryType") in {"point", "point_plane"} and any(
            word in searchable for word in ("barcode", "条码", "扫码目标")
        ):
            return port
    return None


def build_scanner_process_preflight(
    discovery: dict[str, Any],
    endpoint_recovery: dict[str, Any],
    global_catalog: dict[str, Any],
    *,
    target_process_module_token: str,
) -> dict[str, Any]:
    """Evaluate whether a mechanical slot may proceed to CAD validation."""

    if discovery.get("schemaVersion") != "cross-project-scanner-slot-discovery/v1":
        raise CrossProjectScannerProcessPreflightError(
            "不支持的扫描槽位发现报告版本。"
        )
    if endpoint_recovery.get("schemaVersion") != (
        "cross-project-scanner-slot-endpoint-recovery/v1"
    ):
        raise CrossProjectScannerProcessPreflightError("不支持的端点恢复证据版本。")
    if global_catalog.get("schemaVersion") != "global-module-catalog/v1":
        raise CrossProjectScannerProcessPreflightError("不支持的全局目录版本。")
    selected = discovery.get("selectedCandidate") or {}
    if not selected or not selected.get("directFit"):
        raise CrossProjectScannerProcessPreflightError(
            "没有满足严格机械公差的扫描槽位候选。"
        )
    if endpoint_recovery.get("discoveryDigest") != discovery.get("discoveryDigest"):
        raise CrossProjectScannerProcessPreflightError(
            "端点恢复证据与槽位发现报告不匹配。"
        )

    relation = discovery.get("sourceRelation") or {}
    source_project = str(relation.get("sourceProjectId") or "")
    source_token = str(relation.get("sourceModuleToken") or "")
    target_project = str(relation.get("targetProjectId") or "")
    scanner_ports = _functional_ports(global_catalog, source_project, source_token)
    target_ports = _functional_ports(
        global_catalog, target_project, target_process_module_token
    )
    optical = _scanner_optical_port(scanner_ports)
    barcode = _barcode_target_port(target_ports)
    optical_geometry = (optical or {}).get("functionalGeometry") or {}
    parameters = optical_geometry.get("parameters") or {}
    has_range = all(
        isinstance(parameters.get(name), (int, float))
        and float(parameters[name]) >= 0
        for name in ("minWorkingDistanceMeters", "maxWorkingDistanceMeters")
    ) and float(parameters.get("maxWorkingDistanceMeters") or 0) > float(
        parameters.get("minWorkingDistanceMeters") or 0
    )
    checks = {
        "mechanicalCandidateDirectFit": bool(selected.get("directFit")),
        "selectedEndpointsRecovered": bool(endpoint_recovery.get("allRecovered")),
        "scannerOpticalOriginAndAxisDefined": optical is not None,
        "workingDistanceRangeDefined": has_range,
        "barcodeTargetDefined": barcode is not None,
        "candidatePoseTransformSolved": False,
        "opticalAxisIntersectsTarget": False,
        "targetWithinWorkingDistance": False,
    }
    missing = []
    if optical is None:
        missing.append("scanner_optical_origin_and_axis")
    if not has_range:
        missing.append("scanner_working_distance_range")
    if barcode is None:
        missing.append("target_transport_barcode_point")
    if not endpoint_recovery.get("allRecovered"):
        missing.append("stable_mechanical_endpoint_recovery")
    ready_for_pose = not missing
    status = (
        "ready_for_candidate_pose_and_optical_geometry_evaluation"
        if ready_for_pose
        else "blocked_before_cad_missing_functional_semantics"
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "sourceScanner": {
            "projectId": source_project,
            "moduleToken": source_token,
            "opticalPortId": (optical or {}).get("globalPortId"),
        },
        "targetProcessContext": {
            "projectId": target_project,
            "moduleToken": target_process_module_token,
            "barcodeTargetPortId": (barcode or {}).get("globalPortId"),
        },
        "mechanicalCandidate": {
            "discoveryDigest": discovery.get("discoveryDigest"),
            "endpointRecoveryDigest": endpoint_recovery.get("evidenceDigest"),
            "nativeStationDisplacementMeters": selected.get(
                "nativeStationDisplacementMeters"
            ),
            "selectedCandidate": deepcopy(selected),
        },
        "checks": checks,
        "missingEvidence": missing,
        "cadInsertionAllowed": False,
        "semanticPortPublished": False,
        "nextAction": (
            "solve-candidate-pose-then-evaluate-axis-distance-and-target"
            if ready_for_pose
            else "capture-scanner-optical-port-working-distance-and-barcode-target"
        ),
        "limitations": [
            "孔距匹配不能替代光轴、条码目标点或工作距离。",
            "候选机械位姿尚未求解，因此不能计算真实扫码距离与夹角。",
            "本阶段在CAD前失败关闭，不执行配合、保存或B-rep。",
        ],
        "project06Included": False,
    }
    return {**core, "preflightDigest": _digest(core)}

#!/usr/bin/env python3
"""Build scanner mechanical contracts while keeping optical semantics read-only."""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    SCANNER_CATALOG_SCHEMA,
    _digest,
    build_plane_two_hole_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


SM00 = ROOT / "demo/semantic_ports/project01_SM00_third_increment_v1"
AI00 = ROOT / "demo/semantic_ports/project03_AI00_third_increment_v1"
PROCESS = ROOT / "demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.json"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
OUTPUT = ROOT / "demo/cross_project_substitution/scanner-interface-contract-v1"
FAMILY = "scanner_plane_two_hole_mount/v1"
RECIPE = "recipe/scanner-plane-two-hole-rigid-mount/v1"
ALIASES = {"locating_hole_1": "primary_locating_hole", "locating_hole_2": "secondary_locating_hole"}
DRIVING_ROLES = {"support_plane", "locating_hole_1", "locating_hole_2"}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def select_port(catalog: dict, port_id: str) -> dict:
    rows = [row for row in catalog.get("ports") or [] if row.get("portId") == port_id]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select port {port_id}")
    result = copy.deepcopy(rows[0])
    result["endpointBindings"] = [
        row for row in result.get("endpointBindings") or [] if row.get("role") in DRIVING_ROLES
    ]
    return result


def spacing(port: dict, face_catalog: dict) -> float:
    ids = [
        row["endpointId"] for row in port["endpointBindings"]
        if row.get("role") in {"locating_hole_1", "locating_hole_2"}
    ]
    endpoints = {row["EndpointId"]: row for row in face_catalog.get("Endpoints") or []}
    if len(ids) != 2 or any(endpoint_id not in endpoints for endpoint_id in ids):
        raise ValueError("scanner locating endpoints cannot be resolved")
    centers = [endpoints[endpoint_id]["Endpoint"]["FaceCenterLocal"] for endpoint_id in ids]
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(*centers)))


def release(name: str) -> dict:
    return read(RELEASES / name / "release-manifest.json")


def pair_evidence(module_id: str, slot_id: str, manifest: dict) -> dict:
    if not any(row.get("passed") and row.get("drivingInitialPoseIndependent") for row in manifest.get("validationEvidence") or []):
        raise ValueError("scanner pair release lacks non-prototype CAD evidence")
    return {
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "releaseId": manifest["releaseId"],
        "releaseDigest": manifest["releaseDigest"],
        "nonPrototypeCadValidated": True,
    }


def build() -> dict:
    sm_summary, sm_ports, sm_faces = (
        read(SM00 / "work_packet_summary.json"), read(SM00 / "semantic_port_catalog.json"), read(SM00 / "face_endpoint_catalog.json")
    )
    ai_summary, ai_ports, ai_faces = (
        read(AI00 / "work_packet_summary.json"), read(AI00 / "semantic_port_catalog.json"), read(AI00 / "face_endpoint_catalog.json")
    )
    process = read(PROCESS)
    r50 = release("relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014")
    r48 = release("relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012")
    sm_module, sm_slot = select_port(sm_ports, "SM00.frame_installation"), select_port(sm_ports, "JJ00.scanner_installation")
    ai_module, ai_slot = select_port(ai_ports, "AI00.frame_installation"), select_port(ai_ports, "AA00.ai00_installation")
    sm_spacing, ai_spacing = spacing(sm_module, sm_faces), spacing(ai_module, ai_faces)

    def make(port: dict, summary: dict, manifest: dict, side: str, definition: str, axis_spacing: float) -> dict:
        return build_plane_two_hole_contract(
            port=port, summary=summary, release_manifest=manifest, side=side,
            module_role="Scanner" if side == "moving_module" else "Base",
            module_definition_id=definition,
            accepted_module_roles=["Scanner"] if side == "base_slot" else None,
            interface_family=FAMILY, recipe_id=RECIPE,
            locating_axis_spacing_meters=axis_spacing, role_aliases=ALIASES,
            axis_parallel_score=1.0, axis_relation_to_primary=1.0,
        )

    contracts = [
        make(sm_module, sm_summary, r50, "moving_module", "project01::SM00", sm_spacing),
        make(sm_slot, sm_summary, r50, "base_slot", "project01::JJ00", sm_spacing),
        make(ai_module, ai_summary, r48, "moving_module", "project03::AI00", ai_spacing),
        make(ai_slot, ai_summary, r48, "base_slot", "project03::AA00", ai_spacing),
    ]
    pair_rows = [
        pair_evidence("project01::SM00", "project01::JJ00", r50),
        pair_evidence("project03::AI00", "project03::AA00", r48),
    ]
    pair_index = {(row["moduleDefinitionId"], row["slotDefinitionId"]): row for row in pair_rows}
    modules = [row for row in contracts if row["side"] == "moving_module"]
    slots = [row for row in contracts if row["side"] == "base_slot"]
    matrix, templates = [], []
    for module in modules:
        for slot in slots:
            match = match_interface_contracts(
                module, slot,
                pair_release_evidence=pair_index.get((module["moduleDefinitionId"], slot["moduleDefinitionId"])),
            )
            matrix.append(match)
            if match["compatible"]:
                templates.append(instantiate_connection_template(match, module, slot))

    process_ports = [
        {
            "moduleDefinitionId": "project01::SM00",
            "relationType": "read_only_optical_validation",
            "drivesMechanicalPlacement": False,
            "scannerCount": sm_summary["opticalEvidenceRequired"]["scannerCount"],
            "modeledBeamLengthMeters": sm_summary["opticalEvidenceRequired"]["explicitBeamLengthMeters"],
            "target": "carrier_and_product_barcode_surface_proxies",
        },
        {
            "moduleDefinitionId": "project03::AI00",
            "relationType": "read_only_optical_validation",
            "drivesMechanicalPlacement": False,
            "modeledBeamLengthMeters": process["sourceScanner"]["modeledNominalWorkingDistanceMeters"],
            "workingDistanceRangeMeters": [
                process["readOnlyChecks"]["workingDistanceRangeEvidence"]["minimumMeters"],
                process["readOnlyChecks"]["workingDistanceRangeEvidence"]["maximumMeters"],
            ],
            "target": "barcode_lane_proxy",
            "engineeringProcessValidationPassed": process["engineeringProcessValidationPassed"],
        },
    ]
    compatible_count = sum(row["compatible"] for row in matrix)
    core = {
        "schemaVersion": SCANNER_CATALOG_SCHEMA,
        "role": "Scanner",
        "contracts": contracts,
        "releasedPairEvidence": pair_rows,
        "processPorts": process_ports,
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "summary": {
            "modulePortCount": 2, "baseSlotCount": 2,
            "compatiblePairCount": compatible_count,
            "incompatiblePairCount": len(matrix) - compatible_count,
            "releasedPairCount": sum(row["existingPairReleaseReusable"] for row in matrix),
            "mechanicalDrivingPortCount": 4,
            "readOnlyProcessPortCount": 2,
            "projectIdentityUsedForCompatibility": False,
            "sm00SpacingMeters": sm_spacing,
            "ai00SpacingMeters": ai_spacing,
        },
        "claimBoundary": (
            "Mechanical placement uses support plus two locating axes only. Optical axis, barcode target and "
            "working distance are read-only process validation. The 22 mm and 200 mm native interfaces are "
            "mechanically incompatible; no cross-slot CAD release is claimed."
        ),
    }
    report = {**core, "catalogDigest": _digest(core)}
    validate_contract_catalog(report)
    return report


def main() -> int:
    report = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path, md_path = OUTPUT / "interface-contract-catalog.json", OUTPUT / "README-CN.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 扫描模组接口契约", "", "机械安装与扫码工艺关系分层表达。", "", "| 扫描模组 | 基座槽位 | 孔距差 | 结果 |", "|---|---|---:|---|"]
    for row in report["compatibilityMatrix"]:
        lines.append(f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | {row['checks']['spacingDifferenceMeters']*1000:.3f} mm | {row['status']} |")
    lines += [
        "", "- SM00/JJ00为22 mm原生接口；AI00/AA00为200 mm原生接口。",
        "- 两条交叉方向因178 mm定位间距差失败关闭，不启动CAD。",
        "- 光轴、条码目标与工作距离只做只读工艺验证，不生成驱动配合。",
        "- `GET /api/demo/mechanical-interface-contracts/scanner`",
        "- `GET /api/demo/mechanical-interface-contracts/scanner/plan?moduleDefinitionId=project03::AI00`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(json_path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

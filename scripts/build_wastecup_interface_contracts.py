#!/usr/bin/env python3
"""Build reusable WasteCup contracts without conflating interface families."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    NATIVE_WASTECUP_TWO_DISTANCE_FAMILY,
    WASTECUP_CATALOG_SCHEMA,
    _digest,
    build_support_position_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


A600 = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-demo-v2/semantic-package-v3"
AA00 = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project03-v1/support-position-demo-v1/semantic-package-v1"
NATIVE_A300 = ROOT / "demo/semantic_ports/project02_service_installations_v1/A300"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
OUTPUT = ROOT / "demo/cross_project_substitution/wastecup-interface-contract-v1"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def release(name: str) -> dict:
    return read(RELEASES / name / "release-manifest.json")


def port(catalog: dict, port_id: str) -> dict:
    rows = [row for row in catalog.get("ports") or [] if row.get("portId") == port_id]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select port {port_id}")
    return rows[0]


def pair_evidence(
    module_id: str,
    slot_id: str,
    manifest: dict,
    module_contract: dict,
    slot_contract: dict,
) -> dict:
    if not any(row.get("passed") and row.get("drivingInitialPoseIndependent") for row in manifest.get("validationEvidence") or []):
        raise ValueError("wastecup pair lacks non-prototype CAD evidence")
    return {
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "releaseId": manifest["releaseId"],
        "releaseDigest": manifest["releaseDigest"],
        "nonPrototypeCadValidated": True,
        "moduleContractId": module_contract["contractId"],
        "slotContractId": slot_contract["contractId"],
    }


def build() -> dict:
    a600_catalog = read(A600 / "semantic_port_catalog.json")
    aa00_catalog = read(AA00 / "semantic_port_catalog.json")
    a300_catalog = read(NATIVE_A300 / "semantic_port_catalog.json")
    a600_policy = a600_catalog["supportPositionDemoPolicy"]
    aa00_policy = aa00_catalog["supportPositionDemoPolicy"]
    r_a600 = release("relation-p000-support-position-demo-20261023-v1")
    r_aa00 = release("relation-p000-aa00-support-position-demo-20261023-v1")
    r_a300 = release("relation-v36-project02-nine-addon-portable-driving-20261011")
    contracts = [
        build_support_position_contract(
            port=port(a600_catalog, "P000.cross_project_wastecup_datum"),
            release_manifest=r_a600, side="moving_module", module_role="WasteCup",
            module_definition_id="project05::P000",
        ),
        build_support_position_contract(
            port=port(a600_catalog, "A600.cross_project_wastecup_datum_slot"),
            release_manifest=r_a600, side="base_slot", module_role="Base",
            module_definition_id="project02::A600", accepted_module_roles=["WasteCup"],
            position_parameters_meters=a600_policy["positionParametersMeters"],
        ),
        build_support_position_contract(
            port=port(aa00_catalog, "AA00.cross_project_wastecup_datum_slot"),
            release_manifest=r_aa00, side="base_slot", module_role="Base",
            module_definition_id="project03::AA00", accepted_module_roles=["WasteCup"],
            position_parameters_meters=aa00_policy["positionParametersMeters"],
        ),
        build_support_position_contract(
            port=port(a300_catalog, "A300.frame_installation"),
            release_manifest=r_a300,
            side="moving_module",
            module_role="WasteCup",
            module_definition_id="project02::A300",
            interface_family=NATIVE_WASTECUP_TWO_DISTANCE_FAMILY,
            role_aliases={
                "距离19-target-0": "longitudinal_datum",
                "距离20-target-0": "lateral_datum",
                "重合39-target-0": "support_datum",
            },
        ),
        build_support_position_contract(
            port=port(a300_catalog, "A600.a300_installation"),
            release_manifest=r_a300,
            side="base_slot",
            module_role="Base",
            module_definition_id="project02::A600",
            accepted_module_roles=["WasteCup"],
            position_parameters_meters={
                "longitudinal": 0.080,
                "lateral": 0.390,
                "supportGap": 0.0,
            },
            distance_flip_dimensions={
                "longitudinal": False,
                "lateral": False,
                "supportGap": False,
            },
            interface_family=NATIVE_WASTECUP_TWO_DISTANCE_FAMILY,
            role_aliases={
                "距离19-context-0": "longitudinal_datum",
                "距离20-context-0": "lateral_datum",
                "重合39-context-0": "support_datum",
            },
        ),
    ]
    contract_index = {
        (row["side"], row["moduleDefinitionId"], row["interfaceFamily"]): row
        for row in contracts
    }
    pair_rows = [
        pair_evidence(
            "project05::P000",
            "project02::A600",
            r_a600,
            contract_index[("moving_module", "project05::P000", "support_plane_two_offset_position/v1")],
            contract_index[("base_slot", "project02::A600", "support_plane_two_offset_position/v1")],
        ),
        pair_evidence(
            "project05::P000",
            "project03::AA00",
            r_aa00,
            contract_index[("moving_module", "project05::P000", "support_plane_two_offset_position/v1")],
            contract_index[("base_slot", "project03::AA00", "support_plane_two_offset_position/v1")],
        ),
        pair_evidence(
            "project02::A300",
            "project02::A600",
            r_a300,
            contract_index[("moving_module", "project02::A300", NATIVE_WASTECUP_TWO_DISTANCE_FAMILY)],
            contract_index[("base_slot", "project02::A600", NATIVE_WASTECUP_TWO_DISTANCE_FAMILY)],
        ),
    ]
    modules = [row for row in contracts if row["side"] == "moving_module"]
    slots = [row for row in contracts if row["side"] == "base_slot"]
    pair_index = {(row["moduleDefinitionId"], row["slotDefinitionId"]): row for row in pair_rows}
    matrix, templates = [], []
    for module in modules:
        for slot in slots:
            match = match_interface_contracts(
                module,
                slot,
                pair_release_evidence=pair_index.get(
                    (module["moduleDefinitionId"], slot["moduleDefinitionId"])
                ),
            )
            matrix.append(match)
            if match["compatible"]:
                templates.append(instantiate_connection_template(match, module, slot))
    core = {
        "schemaVersion": WASTECUP_CATALOG_SCHEMA,
        "role": "WasteCup",
        "contracts": contracts,
        "releasedPairEvidence": pair_rows,
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "summary": {
            "modulePortCount": len(modules),
            "baseSlotCount": len(slots),
            "compatiblePairCount": sum(row["compatible"] for row in matrix),
            "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
            "releasedPairCount": sum(
                row["existingPairReleaseReusable"] for row in matrix
            ),
            "projectIdentityUsedForCompatibility": False,
            "actualFixationMethodVerified": False,
            "directMechanicalCompatibilityClaim": False,
        },
        "claimBoundary": (
            "P000 is positioned from a non-prototype pose by one support relation and two explicit offsets. "
            "This is a released datum-placement Demo on A600 and AA00, not evidence of hole-pattern, "
            "fastener or direct mechanical interchangeability."
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
    lines = [
        "# 排胶杯支承定位接口契约", "",
        "P000通过支承面与两个显式位置参数在不同基座上完成Demo定位。", "",
        "| 基座槽位 | 纵向参数 | 横向参数 | CAD证据 |", "|---|---:|---:|---|",
    ]
    contracts = {row["contractId"]: row for row in report["contracts"]}
    for row in report["compatibilityMatrix"]:
        if not row["compatible"]:
            continue
        params = contracts[row["slotContractId"]]["geometrySignature"]["positionParametersMeters"]
        lines.append(
            f"| {row['slotDefinitionId']} | {params['longitudinal']*1000:.1f} mm | "
            f"{params['lateral']*1000:.1f} mm | {(row['pairReleaseEvidence'] or {})['releaseId']} |"
        )
    lines += [
        "", "- A600默认80/390 mm；AA00默认400/200 mm，均为显式Demo设计参数。",
        "- 模板动态生成两条距离配合和一条支承重合配合。",
        "- 实际固定方式、孔槽匹配和直接机械兼容均未验证。",
        "- `GET /api/demo/mechanical-interface-contracts/wastecup`",
        "- `GET /api/demo/mechanical-interface-contracts/wastecup/plan?moduleDefinitionId=project05::P000`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(json_path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

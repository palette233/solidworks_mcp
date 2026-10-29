#!/usr/bin/env python3
"""Build the reusable Project01/03 transport interface-contract matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    TRANSPORT_CATALOG_SCHEMA,
    _digest,
    build_plane_two_hole_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


SS00 = ROOT / "demo/semantic_ports/project01_SS00_first_increment_v1"
AE00 = ROOT / "demo/semantic_ports/project03_AE00_first_increment_v1"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
OUTPUT = ROOT / "demo/cross_project_substitution/transport-interface-contract-v1"
FAMILY = "transport_plane_two_hole_mount/v1"
RECIPE = "recipe/transport-plane-two-hole-rigid-mount/v1"
ALIASES = {
    "locating_hole_1": "primary_locating_hole",
    "locating_hole_2": "secondary_locating_hole",
}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def select_port(catalog: dict, port_id: str) -> dict:
    rows = [row for row in catalog.get("ports") or [] if row.get("portId") == port_id]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select port {port_id}")
    return rows[0]


def release(name: str) -> dict:
    return read(RELEASES / name / "release-manifest.json")


def pair_evidence(module_id: str, slot_id: str, manifest: dict) -> dict:
    if not any(
        row.get("passed") is True
        and row.get("drivingInitialPoseIndependent") is True
        for row in manifest.get("validationEvidence") or []
    ):
        raise ValueError(f"pair release is not non-prototype validated: {manifest.get('releaseId')}")
    return {
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "releaseId": manifest["releaseId"],
        "releaseDigest": manifest["releaseDigest"],
        "nonPrototypeCadValidated": True,
    }


def build() -> dict:
    ss_summary = read(SS00 / "work_packet_summary.json")
    ss_catalog = read(SS00 / "semantic_port_catalog.json")
    ae_summary = read(AE00 / "work_packet_summary.json")
    ae_catalog = read(AE00 / "semantic_port_catalog.json")
    r9 = release("relation-v9-project01-driving-independent-20261011")
    r11 = release("relation-v11-project03-ae00-driving-20261011")
    r43 = release("relation-v43-project01-jj00-project03-ae00-transport-driving-20261012")
    r46 = release("relation-v46-project03-aa00-project01-ss00-transport-driving-20261012")

    def make(*, port: dict, summary: dict, manifest: dict, side: str, definition: str) -> dict:
        return build_plane_two_hole_contract(
            port=port,
            summary=summary,
            release_manifest=manifest,
            side=side,
            module_role="Transport" if side == "moving_module" else "Base",
            module_definition_id=definition,
            accepted_module_roles=["Transport"] if side == "base_slot" else None,
            interface_family=FAMILY,
            recipe_id=RECIPE,
            locating_axis_spacing_meters=summary["locatingHoleSpacingMeters"],
            role_aliases=ALIASES,
            axis_parallel_score=1.0,
            axis_relation_to_primary=1.0,
        )

    contracts = [
        make(port=select_port(ss_catalog, "SS00.frame_installation"), summary=ss_summary,
             manifest=r9, side="moving_module", definition="project01::SS00"),
        make(port=select_port(ss_catalog, "JJ00.transport_installation"), summary=ss_summary,
             manifest=r9, side="base_slot", definition="project01::JJ00"),
        make(port=select_port(ae_catalog, "AE00.frame_installation"), summary=ae_summary,
             manifest=r11, side="moving_module", definition="project03::AE00"),
        make(port=select_port(ae_catalog, "AA00.transport_installation"), summary=ae_summary,
             manifest=r11, side="base_slot", definition="project03::AA00"),
    ]
    pair_rows = [
        pair_evidence("project01::SS00", "project01::JJ00", r9),
        pair_evidence("project01::SS00", "project03::AA00", r46),
        pair_evidence("project03::AE00", "project01::JJ00", r43),
        pair_evidence("project03::AE00", "project03::AA00", r11),
    ]
    pair_index = {(row["moduleDefinitionId"], row["slotDefinitionId"]): row for row in pair_rows}
    modules = [row for row in contracts if row["side"] == "moving_module"]
    slots = [row for row in contracts if row["side"] == "base_slot"]
    matrix, templates = [], []
    for module in modules:
        for slot in slots:
            match = match_interface_contracts(
                module,
                slot,
                pair_release_evidence=pair_index[(module["moduleDefinitionId"], slot["moduleDefinitionId"])],
            )
            matrix.append(match)
            templates.append(instantiate_connection_template(match, module, slot))

    core = {
        "schemaVersion": TRANSPORT_CATALOG_SCHEMA,
        "role": "Transport",
        "contracts": contracts,
        "releasedPairEvidence": pair_rows,
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "summary": {
            "modulePortCount": len(modules),
            "baseSlotCount": len(slots),
            "compatiblePairCount": sum(row["compatible"] for row in matrix),
            "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
            "releasedPairCount": sum(row["existingPairReleaseReusable"] for row in matrix),
            "genericRecipeCount": 1,
            "projectIdentityUsedForCompatibility": False,
            "crossProjectPairReleaseCount": 2,
        },
        "claimBoundary": (
            "All four SS00/AE00 to JJ00/AA00 transport combinations share the same 58 mm "
            "plane/two-axis interface contract and have existing non-prototype CAD releases. "
            "Project identity is traceability only; collision and vendor fastener certification remain outside."
        ),
    }
    report = {**core, "catalogDigest": _digest(core)}
    validate_contract_catalog(report)
    return report


def main() -> int:
    report = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT / "interface-contract-catalog.json"
    md_path = OUTPUT / "README-CN.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 传输模组通用接口契约", "",
        "SS00与AE00均通过同一58 mm平面＋双定位轴契约匹配JJ00、AA00槽位；项目编号只用于追溯。", "",
        "| 传输模组 | 基座槽位 | 接口结果 | 已有非原型CAD发布 |", "|---|---|---|---|",
    ]
    for row in report["compatibilityMatrix"]:
        lines.append(
            f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | {row['status']} | "
            f"{(row.get('pairReleaseEvidence') or {}).get('releaseId', '-')} |"
        )
    lines += [
        "", "## 运行边界", "",
        "- 兼容性由接口拓扑、58 mm定位间距、方向和自由度闭合决定，不由Project编号决定。",
        "- 四种组合均已有独立非原型初始位姿、3/3配合、完全定位与保存重开的发布证据。",
        "- 碰撞/B-rep、紧固件规格和厂商认证仍是独立后验项。",
        "", "## API", "",
        "- `GET /api/demo/mechanical-interface-contracts/transport`",
        "- `GET /api/demo/mechanical-interface-contracts/transport/plan?moduleDefinitionId=project01::SS00`",
        "- 两个兼容槽位并存时必须显式确认槽位；限定当前基座上下文后可唯一选择。",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(json_path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build A180/F000 exact mechanical scanner contracts and process boundaries."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    CONTEXTUAL_SCANNER_CATALOG_SCHEMA,
    SCANNER_DISTANCE_SLOT_FAMILY,
    SCANNER_DISTANCE_SLOT_RECIPE_ID,
    SCANNER_DISTANCE_SLOT_ROLES,
    SCANNER_PLANE_AXIS_FAMILY,
    SCANNER_PLANE_AXIS_RECIPE_ID,
    SCANNER_PLANE_AXIS_ROLES,
    _digest,
    build_exact_three_relation_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


OUTPUT = ROOT / "demo/cross_project_substitution/contextual-scanner-interface-contract-v1"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
A180 = ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/project02-a800-a180-driving-v1/A180"
F000 = ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/project05-nonanchor-driving-v2/F000"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def select_port(catalog: dict, port_id: str) -> dict:
    rows = [row for row in catalog.get("ports") or [] if row.get("portId") == port_id]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select port {port_id}")
    return rows[0]


def release(name: str) -> dict:
    return read(RELEASES / name / "release-manifest.json")


def build() -> dict:
    a_catalog = read(A180 / "semantic_port_catalog.json")
    f_catalog = read(F000 / "semantic_port_catalog.json")
    r30 = release("relation-v30-project02-a800-a180-portable-driving-20261011")
    r20 = release("relation-v20-project05-d000-f000-portable-driving-20261011")

    def exact(*, catalog: dict, port_id: str, manifest: dict, side: str,
              definition: str, family: str, recipe: str, roles: tuple[str, str, str],
              variant: str, aliases: dict[str, str], parameters: dict | None = None) -> dict:
        return build_exact_three_relation_contract(
            port=select_port(catalog, port_id),
            release_manifest=manifest,
            side=side,
            module_role="Scanner" if side == "moving_module" else "Base",
            module_definition_id=definition,
            accepted_module_roles=["Scanner"] if side == "base_slot" else None,
            interface_family=family,
            recipe_id=recipe,
            topology_roles=roles,
            interface_variant_key=variant,
            role_aliases=aliases,
            recipe_parameters=parameters,
        )

    a_module = exact(
        catalog=a_catalog, port_id="A180.frame_installation", manifest=r30,
        side="moving_module", definition="project02::A180",
        family=SCANNER_DISTANCE_SLOT_FAMILY, recipe=SCANNER_DISTANCE_SLOT_RECIPE_ID,
        roles=SCANNER_DISTANCE_SLOT_ROLES, variant="project02_a180_a600_slot/v1",
        aliases={"mate_1_target_1": "support_plane", "mate_2_target_1": "longitudinal_datum", "mate_3_target_1": "slot_locator"},
    )
    a_slot = exact(
        catalog=a_catalog, port_id="A600.a180_installation", manifest=r30,
        side="base_slot", definition="project02::A600",
        family=SCANNER_DISTANCE_SLOT_FAMILY, recipe=SCANNER_DISTANCE_SLOT_RECIPE_ID,
        roles=SCANNER_DISTANCE_SLOT_ROLES, variant="project02_a180_a600_slot/v1",
        aliases={"mate_1_context_1": "support_plane", "mate_2_context_1": "longitudinal_datum", "mate_3_context_1": "slot_locator"},
        parameters={"longitudinalOffsetMeters": 0.272},
    )
    f_module = exact(
        catalog=f_catalog, port_id="F000.frame_installation", manifest=r20,
        side="moving_module", definition="project05::F000",
        family=SCANNER_PLANE_AXIS_FAMILY, recipe=SCANNER_PLANE_AXIS_RECIPE_ID,
        roles=SCANNER_PLANE_AXIS_ROLES, variant="project05_f000_a000_plane_axis/v1",
        aliases={"重合12_target_1": "support_plane", "平行3_target_1": "orientation_datum", "同心15_target_1": "locating_axis"},
    )
    f_slot = exact(
        catalog=f_catalog, port_id="A000.f000_installation", manifest=r20,
        side="base_slot", definition="project05::A000",
        family=SCANNER_PLANE_AXIS_FAMILY, recipe=SCANNER_PLANE_AXIS_RECIPE_ID,
        roles=SCANNER_PLANE_AXIS_ROLES, variant="project05_f000_a000_plane_axis/v1",
        aliases={"重合12_context_1": "support_plane", "平行3_context_1": "orientation_datum", "同心15_context_1": "locating_axis"},
    )
    contracts = [a_module, a_slot, f_module, f_slot]
    pair_rows = [
        {"moduleDefinitionId": "project02::A180", "slotDefinitionId": "project02::A600", "releaseId": r30["releaseId"], "releaseDigest": r30["releaseDigest"], "nonPrototypeCadValidated": True},
        {"moduleDefinitionId": "project05::F000", "slotDefinitionId": "project05::A000", "releaseId": r20["releaseId"], "releaseDigest": r20["releaseDigest"], "nonPrototypeCadValidated": True},
    ]
    pair_index = {(row["moduleDefinitionId"], row["slotDefinitionId"]): row for row in pair_rows}
    matrix, templates = [], []
    for module in (a_module, f_module):
        for slot in (a_slot, f_slot):
            match = match_interface_contracts(
                module, slot,
                pair_release_evidence=pair_index.get((module["moduleDefinitionId"], slot["moduleDefinitionId"])),
            )
            matrix.append(match)
            if match["mateInstantiationAllowed"]:
                templates.append(instantiate_connection_template(match, module, slot))
    process_ports = [
        {
            "moduleDefinitionId": "project02::A180",
            "processPortId": "A180.scan_optical",
            "geometryType": "point_axis",
            "originInModuleBottomFrame": {"u": -0.03650000000000064, "v": -0.22140000000000346, "height": 0.2368000000000019},
            "axisInLayoutFrame": [2.746199854056488e-17, -6.560152800875588e-15, 1.0],
            "axisSignConfirmed": False,
            "status": "cad_inferred_for_coarse_layout",
            "drivesMechanicalPlacement": False,
        },
        {
            "moduleDefinitionId": "project05::F000",
            "processPortId": None,
            "status": "missing_optical_functional_geometry",
            "drivesMechanicalPlacement": False,
        },
    ]
    core = {
        "schemaVersion": CONTEXTUAL_SCANNER_CATALOG_SCHEMA,
        "role": "Scanner",
        "contracts": contracts,
        "releasedPairEvidence": pair_rows,
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "processPorts": process_ports,
        "summary": {
            "modulePortCount": 2,
            "baseSlotCount": 2,
            "compatiblePairCount": sum(row["compatible"] for row in matrix),
            "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
            "releasedPairCount": sum(row["existingPairReleaseReusable"] for row in matrix),
            "mechanicallyCompleteModulePortCount": 2,
            "processPortCount": 2,
            "completeOpticalProcessPortCount": 1,
            "missingOpticalProcessPortCount": 1,
            "projectIdentityUsedForCompatibility": False,
        },
        "claimBoundary": (
            "A180 and F000 have released exact mechanical bundles but different topologies, so direct "
            "cross-project substitution is not inferred. A180 optical geometry is coarse-layout evidence; "
            "F000 optical geometry remains missing. Process ports never drive mechanical placement."
        ),
    }
    report = {**core, "catalogDigest": _digest(core)}
    validate_contract_catalog(report)
    return report


def main() -> int:
    report = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "interface-contract-catalog.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 上下文型扫描接口契约", "",
        "A180与F000都已有完整非原型机械装配证据，但机械拓扑不同；本目录不推断二者可以直接互换。", "",
        "| 扫描模组 | 基座槽位 | 结果 | 原因 |", "|---|---|---|---|",
    ]
    for row in report["compatibilityMatrix"]:
        reasons = "；".join(item["code"] for item in row["blockers"]) or "完整契约且已有配对发布"
        lines.append(f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | {row['status']} | {reasons} |")
    lines += [
        "", "## 功能端口边界", "",
        "- A180：已有粗布局级点＋轴光学端口，但光轴正负方向尚未确认。",
        "- F000：尚未登记光轴、工作距离和目标区，机械安装成功不代表扫码功能闭环。",
        "- 两类光学信息均为只读验证，不生成机械配合。",
    ]
    (OUTPUT / "README-CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

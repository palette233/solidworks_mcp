#!/usr/bin/env python3
"""Build the Project01/03 cleaning-weighing interface-contract matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    CATALOG_SCHEMA,
    CLEANING_SLOT_FAMILY,
    CLEANING_SLOT_RECIPE_ID,
    _digest,
    build_plane_two_hole_contract,
    build_flexible_calibration_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


GN00 = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00/two-hole-candidate-v1"
)
AG00 = ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1"
N000 = ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/project05-nonanchor-driving-v7/N000"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
OUTPUT = ROOT / "demo/cross_project_substitution/cleaning-weighing-interface-contract-v1"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def select_port(catalog: dict, token: str) -> dict:
    matches = [row for row in catalog.get("ports") or [] if token in str(row.get("moduleToken"))]
    if len(matches) != 1:
        raise ValueError(f"cannot uniquely select port for {token}")
    return matches[0]


def pair_evidence(module_id: str, slot_id: str, manifest: dict) -> dict:
    """Bind one exact native pair to its immutable non-prototype release.

    A module and slot that happen to reference the same release are not enough
    for the staged executor.  It must be able to prove which exact pair that
    release authorizes, otherwise another compatible-looking slot could inherit
    authority accidentally.
    """
    if not any(
        row.get("passed") is True
        and row.get("drivingInitialPoseIndependent") is True
        for row in manifest.get("validationEvidence") or []
    ):
        raise ValueError("cleaning/weighing native pair lacks non-prototype CAD evidence")
    return {
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "releaseId": manifest["releaseId"],
        "releaseDigest": manifest["releaseDigest"],
        "nonPrototypeCadValidated": True,
    }


def build() -> dict:
    gn_summary, gn_catalog = read(GN00 / "candidate_summary.json"), read(GN00 / "semantic_port_catalog.json")
    ag_summary, ag_catalog = read(AG00 / "candidate_summary.json"), read(AG00 / "semantic_port_catalog.json")
    n000_catalog = read(N000 / "semantic_port_catalog.json")
    gn_release = read(RELEASES / "relation-v65-project01-gn00-base-only-two-hole-driving-20261022/release-manifest.json")
    ag_release = read(RELEASES / "relation-v54-project03-ag00-three-datum-driving-20261014/release-manifest.json")
    n000_release = read(RELEASES / "relation-v27-project05-seven-addon-portable-driving-20261011/release-manifest.json")
    contracts = [
        build_plane_two_hole_contract(port=select_port(gn_catalog, "GN00"), summary=gn_summary, release_manifest=gn_release,
                                      side="moving_module", module_role="CleaningWeighing", module_definition_id="project01::GN00"),
        build_plane_two_hole_contract(port=select_port(gn_catalog, "JJ00"), summary=gn_summary, release_manifest=gn_release,
                                      side="base_slot", module_role="Base", module_definition_id="project01::JJ00",
                                      accepted_module_roles=["CleaningWeighing"]),
        build_plane_two_hole_contract(port=select_port(ag_catalog, "AG00"), summary=ag_summary, release_manifest=ag_release,
                                      side="moving_module", module_role="CleaningWeighing", module_definition_id="project03::AG00"),
        build_plane_two_hole_contract(port=select_port(ag_catalog, "AA00"), summary=ag_summary, release_manifest=ag_release,
                                      side="base_slot", module_role="Base", module_definition_id="project03::AA00",
                                      accepted_module_roles=["CleaningWeighing"]),
        build_flexible_calibration_contract(
            port=select_port(n000_catalog, "N000"),
            release_manifest=n000_release,
            side="moving_module",
            module_definition_id="project05::N000",
            interface_variant_key="project05_n000_a000_cleaning_slot/v1",
            role_aliases={
                "重合42_target_1": "support_plane",
                "平行13_target_1": "orientation_datum",
                "N000_LOCATING_DISTANCE_X_target_1": "longitudinal_datum",
                "槽口4_target_1": "slot_locator",
            },
            module_role="CleaningWeighing",
            interface_family=CLEANING_SLOT_FAMILY,
            recipe_id=CLEANING_SLOT_RECIPE_ID,
            internal_flexibility_preserved=False,
        ),
        build_flexible_calibration_contract(
            port=select_port(n000_catalog, "A000"),
            release_manifest=n000_release,
            side="base_slot",
            module_definition_id="project05::A000",
            accepted_module_roles=["CleaningWeighing"],
            interface_variant_key="project05_n000_a000_cleaning_slot/v1",
            role_aliases={
                "重合42_context_1": "support_plane",
                "平行13_context_1": "orientation_datum",
                "N000_LOCATING_DISTANCE_X_context_1": "longitudinal_datum",
                "槽口4_context_1": "slot_locator",
            },
            longitudinal_offset_meters=0.4649999999999975,
            module_role="CleaningWeighing",
            interface_family=CLEANING_SLOT_FAMILY,
            recipe_id=CLEANING_SLOT_RECIPE_ID,
            internal_flexibility_preserved=False,
        ),
    ]
    modules = [row for row in contracts if row["side"] == "moving_module"]
    slots = [row for row in contracts if row["side"] == "base_slot"]
    pair_rows = [
        pair_evidence("project01::GN00", "project01::JJ00", gn_release),
        pair_evidence("project03::AG00", "project03::AA00", ag_release),
        pair_evidence("project05::N000", "project05::A000", n000_release),
    ]
    pair_index = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in pair_rows
    }
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
            if match["mateInstantiationAllowed"]:
                templates.append(instantiate_connection_template(match, module, slot))
    core = {
        "schemaVersion": CATALOG_SCHEMA,
        "role": "CleaningWeighing",
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
            "genericRecipeCount": 2,
            "projectIdentityUsedForCompatibility": False,
            "newCrossProjectPairReleased": False,
        },
        "claimBoundary": (
            "The catalog proves project-independent contract matching for GN00, AG00 and N000. "
            "N000 uses a separate support/parallel/distance/slot interface with a prototype-estimated "
            "465 mm Demo parameter. Cross-family pairs remain incompatible."
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
        "# 清洁/称重通用接口契约样板", "",
        "系统依据接口拓扑、孔距、方向和约束闭合性匹配，不使用Project编号决定兼容性。", "",
        "| 模组端口 | 基座槽位 | 孔距差 | 结果 |", "|---|---|---:|---|",
    ]
    for row in report["compatibilityMatrix"]:
        difference = row["checks"]["spacingDifferenceMeters"]
        difference_text = "-" if difference is None else f"{difference * 1000:.3f} mm"
        lines.append(
            f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | "
            f"{difference_text} | {row['status']} |"
        )
    lines += [
        "", "## 边界", "",
        "- 匹配成功只允许实例化通用三配合配方；新的跨项目组合仍需非原型CAD和发布证据。",
        "- GN00/JJ00与AG00/AA00分别复用各自已有发布；两条跨项目方向因34 mm孔距差保持不兼容。",
        "- 直径、紧固件、碰撞和B-rep不由本层推断。",
        "", "## 调用入口", "",
        "- `GET /api/demo/mechanical-interface-contracts/cleaning-weighing`读取合同与矩阵。",
        "- `GET /api/demo/mechanical-interface-contracts/cleaning-weighing/plan?moduleDefinitionId=project01::GN00`自动查找槽位。",
        "- 唯一兼容槽位可自动选择；多个兼容槽位返回待确认；无兼容槽位返回具体阻断原因。",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(json_path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

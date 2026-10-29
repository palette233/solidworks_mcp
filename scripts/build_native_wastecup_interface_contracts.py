#!/usr/bin/env python3
"""Register Project05 P000's native four-relation installation contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    NATIVE_WASTECUP_CATALOG_SCHEMA,
    NATIVE_WASTECUP_FAMILY,
    NATIVE_WASTECUP_RECIPE_ID,
    _digest,
    build_flexible_calibration_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


OUTPUT = ROOT / "demo/cross_project_substitution/native-wastecup-interface-contract-v1"
PACKAGE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v6/P000"
)
RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v61-project05-complete-seven-addon-driving-20261014/release-manifest.json"
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def select_port(catalog: dict, port_id: str) -> dict:
    rows = [row for row in catalog.get("ports") or [] if row.get("portId") == port_id]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select port {port_id}")
    return rows[0]


def build() -> dict:
    catalog = read(PACKAGE / "semantic_port_catalog.json")
    release = read(RELEASE)
    common = {
        "release_manifest": release,
        "module_role": "WasteCup",
        "interface_family": NATIVE_WASTECUP_FAMILY,
        "recipe_id": NATIVE_WASTECUP_RECIPE_ID,
        "interface_variant_key": "project05_p000_a000_slot_distance/v1",
        "internal_flexibility_preserved": False,
    }
    module = build_flexible_calibration_contract(
        port=select_port(catalog, "P000.frame_installation"),
        side="moving_module",
        module_definition_id="project05::P000",
        role_aliases={
            "重合43_target_1": "support_plane",
            "平行14_target_1": "orientation_datum",
            "槽口6_target_1": "slot_locator",
            "P000_LOCATING_DISTANCE_X_target_1": "longitudinal_datum",
        },
        **common,
    )
    slot = build_flexible_calibration_contract(
        port=select_port(catalog, "A000.p000_installation"),
        side="base_slot",
        module_definition_id="project05::A000",
        accepted_module_roles=["WasteCup"],
        longitudinal_offset_meters=0.3451225352603192,
        role_aliases={
            "重合43_context_1": "support_plane",
            "平行14_context_1": "orientation_datum",
            "槽口6_context_1": "slot_locator",
            "P000_LOCATING_DISTANCE_X_context_1": "longitudinal_datum",
        },
        **common,
    )
    pair_release = {
        "moduleDefinitionId": "project05::P000",
        "slotDefinitionId": "project05::A000",
        "releaseId": release["releaseId"],
        "releaseDigest": release["releaseDigest"],
        "nonPrototypeCadValidated": True,
    }
    match = match_interface_contracts(
        module,
        slot,
        pair_release_evidence=pair_release,
    )
    core = {
        "schemaVersion": NATIVE_WASTECUP_CATALOG_SCHEMA,
        "role": "WasteCup",
        "contracts": [module, slot],
        "releasedPairEvidence": [pair_release],
        "compatibilityMatrix": [match],
        "instantiatedTemplates": [instantiate_connection_template(match, module, slot)],
        "summary": {
            "modulePortCount": 1,
            "baseSlotCount": 1,
            "compatiblePairCount": 1,
            "incompatiblePairCount": 0,
            "releasedPairCount": 1,
            "projectIdentityUsedForCompatibility": False,
            "parameterAuthority": "prototype_estimate",
        },
        "claimBoundary": (
            "P000/A000 is a released non-anchor native installation using support, "
            "parallel orientation, free slot and a prototype-estimated 345.122535 mm "
            "distance. It is demo placement evidence, not vendor fastening certification."
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
    (OUTPUT / "README-CN.md").write_text(
        "\n".join(
            [
                "# Project05 P000原生安装契约",
                "",
                "- P000→A000：支承重合＋方向平行＋自由槽口＋345.122535 mm纵向距离。",
                "- 已复用v61非原型初始位姿、保存重开发布证据。",
                "- 距离来自原型估计；实际紧固、碰撞/B-rep及生产认证未验证。",
                "- P000→A600/AA00的支承面＋位置参数属于另一种显式Demo接口。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"success": True, "output": str(path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

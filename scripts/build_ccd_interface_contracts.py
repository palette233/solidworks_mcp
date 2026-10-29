#!/usr/bin/env python3
"""Build exact CCD installation contracts from released non-anchor bundles."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    CCD_CATALOG_SCHEMA,
    CCD_DUAL_SLOT_FAMILY,
    CCD_DUAL_SLOT_RECIPE_ID,
    CCD_DUAL_SLOT_ROLES,
    CCD_PLANE_AXIS_FAMILY,
    CCD_PLANE_AXIS_RECIPE_ID,
    CCD_PLANE_AXIS_ROLES,
    _digest,
    build_exact_three_relation_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


OUTPUT = ROOT / "demo/cross_project_substitution/ccd-interface-contract-v1"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
M000_PACKAGE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v5/M000"
)
A200_PACKAGE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-six-addon-driving-v5/A200"
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def select_port(catalog: dict, port_id: str) -> dict:
    rows = [row for row in catalog.get("ports") or [] if row.get("portId") == port_id]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select port {port_id}")
    return rows[0]


def release(name: str) -> dict:
    return read(RELEASES / name / "release-manifest.json")


def released_template(release_name: str, legacy_template_id: str) -> dict:
    catalog = read(RELEASES / release_name / "global_module_catalog.json")
    rows = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == legacy_template_id
    ]
    if len(rows) != 1:
        raise ValueError(f"cannot uniquely select template {legacy_template_id}")
    return rows[0]


def build() -> dict:
    m_catalog = read(M000_PACKAGE / "semantic_port_catalog.json")
    a_catalog = read(A200_PACKAGE / "semantic_port_catalog.json")
    m_release_name = "relation-v61-project05-complete-seven-addon-driving-20261014"
    a_release_name = "relation-v34-project02-six-addon-portable-driving-20261011"
    m_release = release(m_release_name)
    a_release = release(a_release_name)
    a_template = released_template(a_release_name, "A200_to_A600_nonanchor_driving_v1")
    slot_steps = [row for row in a_template["mateSteps"] if row.get("mateTypeName") == "swMateSLOT"]
    if len(slot_steps) != 2:
        raise ValueError("A200 release must preserve exactly two slot mates")

    m_module = build_exact_three_relation_contract(
        port=select_port(m_catalog, "M000.frame_installation"),
        release_manifest=m_release,
        side="moving_module",
        module_role="CCD",
        module_definition_id="project05::M000",
        interface_family=CCD_PLANE_AXIS_FAMILY,
        recipe_id=CCD_PLANE_AXIS_RECIPE_ID,
        topology_roles=CCD_PLANE_AXIS_ROLES,
        interface_variant_key="project05_m000_a000_plane_axis/v1",
        role_aliases={
            "重合19_target_1": "support_plane",
            "平行5_target_1": "orientation_datum",
            "同心6_target_1": "locating_axis",
        },
    )
    m_slot = build_exact_three_relation_contract(
        port=select_port(m_catalog, "A000.m000_installation"),
        release_manifest=m_release,
        side="base_slot",
        module_role="Base",
        module_definition_id="project05::A000",
        accepted_module_roles=["CCD"],
        interface_family=CCD_PLANE_AXIS_FAMILY,
        recipe_id=CCD_PLANE_AXIS_RECIPE_ID,
        topology_roles=CCD_PLANE_AXIS_ROLES,
        interface_variant_key="project05_m000_a000_plane_axis/v1",
        role_aliases={
            "重合19_context_1": "support_plane",
            "平行5_context_1": "orientation_datum",
            "同心6_context_1": "locating_axis",
        },
    )
    a_module = build_exact_three_relation_contract(
        port=select_port(a_catalog, "A200.frame_installation"),
        release_manifest=a_release,
        side="moving_module",
        module_role="CCD",
        module_definition_id="project02::A200",
        interface_family=CCD_DUAL_SLOT_FAMILY,
        recipe_id=CCD_DUAL_SLOT_RECIPE_ID,
        topology_roles=CCD_DUAL_SLOT_ROLES,
        interface_variant_key="project02_a200_a600_dual_slot/v1",
        role_aliases={
            "mate_1_target_1": "support_plane",
            "mate_2_target_1": "slot_locator_a",
            "mate_3_target_1": "slot_locator_b",
        },
    )
    a_slot = build_exact_three_relation_contract(
        port=select_port(a_catalog, "A600.a200_installation"),
        release_manifest=a_release,
        side="base_slot",
        module_role="Base",
        module_definition_id="project02::A600",
        accepted_module_roles=["CCD"],
        interface_family=CCD_DUAL_SLOT_FAMILY,
        recipe_id=CCD_DUAL_SLOT_RECIPE_ID,
        topology_roles=CCD_DUAL_SLOT_ROLES,
        interface_variant_key="project02_a200_a600_dual_slot/v1",
        role_aliases={
            "mate_1_context_1": "support_plane",
            "mate_2_context_1": "slot_locator_a",
            "mate_3_context_1": "slot_locator_b",
        },
        recipe_parameters={
            "slotAAdvancedOptions": slot_steps[0]["advancedOptions"],
            "slotBAdvancedOptions": slot_steps[1]["advancedOptions"],
        },
    )
    contracts = [m_module, m_slot, a_module, a_slot]
    pair_releases = [
        {
            "moduleDefinitionId": "project05::M000",
            "slotDefinitionId": "project05::A000",
            "releaseId": m_release["releaseId"],
            "releaseDigest": m_release["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
        {
            "moduleDefinitionId": "project02::A200",
            "slotDefinitionId": "project02::A600",
            "releaseId": a_release["releaseId"],
            "releaseDigest": a_release["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
    ]
    evidence = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in pair_releases
    }
    matrix, templates = [], []
    for module in (m_module, a_module):
        for slot in (m_slot, a_slot):
            match = match_interface_contracts(
                module,
                slot,
                pair_release_evidence=evidence.get(
                    (module["moduleDefinitionId"], slot["moduleDefinitionId"])
                ),
            )
            matrix.append(match)
            if match["mateInstantiationAllowed"]:
                templates.append(instantiate_connection_template(match, module, slot))
    core = {
        "schemaVersion": CCD_CATALOG_SCHEMA,
        "role": "CCD",
        "contracts": contracts,
        "releasedPairEvidence": pair_releases,
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "summary": {
            "modulePortCount": 2,
            "baseSlotCount": 2,
            "compatiblePairCount": sum(row["compatible"] for row in matrix),
            "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
            "releasedPairCount": sum(row["existingPairReleaseReusable"] for row in matrix),
            "projectIdentityUsedForCompatibility": False,
        },
        "claimBoundary": (
            "M000/A000 uses support+parallel+axis; A200/A600 uses support+two exact "
            "slot mates. Both native pairs have non-anchor CAD evidence. Their different "
            "mechanical families are not cross-compatible. CCD field of view and motion "
            "coverage are read-only process validations outside this catalog."
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
        "# CCD机械安装接口契约",
        "",
        "| CCD模组 | 基座槽位 | 状态 | 说明 |",
        "|---|---|---|---|",
    ]
    for row in report["compatibilityMatrix"]:
        reason = "；".join(item["code"] for item in row["blockers"]) or "完整契约且已有非原型CAD发布"
        lines.append(
            f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | {row['status']} | {reason} |"
        )
    lines += [
        "",
        "- M000→A000：支承重合＋方向平行＋定位轴同心。",
        "- A200→A600：支承重合＋两条保留源高级参数的槽配合。",
        "- 两者安装拓扑不同，不能因同属CCD而直接跨项目互换。",
        "- 视野、运动覆盖、碰撞/B-rep和生产认证不在本层结论范围。",
    ]
    (OUTPUT / "README-CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

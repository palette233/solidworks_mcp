#!/usr/bin/env python3
"""Register released contextual transport interfaces for D000 and A800."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    CONTEXTUAL_TRANSPORT_CATALOG_SCHEMA,
    _digest,
    build_plane_distance_width_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


OUTPUT = ROOT / "demo/cross_project_substitution/contextual-transport-interface-contract-v1"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
D000_PACKAGE = ROOT / "demo/global_assembly_catalog/coverage-v2/d000-deterministic-candidate-v1"
A800_PACKAGE = (
    ROOT
    / "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-a800-a180-driving-v1/A800"
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


def build() -> dict:
    d_catalog = read(D000_PACKAGE / "semantic_port_catalog.json")
    a_catalog = read(A800_PACKAGE / "semantic_port_catalog.json")
    r60 = release("relation-v60-project05-d000-deterministic-driving-20261014")
    r30 = release("relation-v30-project02-a800-a180-portable-driving-20261011")
    d_module = build_plane_distance_width_contract(
        port=select_port(d_catalog, "D000.frame_installation"),
        release_manifest=r60,
        side="moving_module",
        module_role="Transport",
        module_definition_id="project05::D000",
        interface_variant_key="project05_d000_a000_width_context/v1",
        role_aliases={
            "重合3_target_1": "support_plane",
            "距离1_target_1": "longitudinal_datum",
            "宽度17_target_1": "width_datum_a",
            "宽度17_target_2": "width_datum_b",
        },
    )
    d_slot = build_plane_distance_width_contract(
        port=select_port(d_catalog, "A000.d000_installation"),
        release_manifest=r60,
        side="base_slot",
        module_role="Base",
        module_definition_id="project05::A000",
        accepted_module_roles=["Transport"],
        interface_variant_key="project05_d000_a000_width_context/v1",
        longitudinal_offset_meters=0.312,
        role_aliases={
            "重合3_context_1": "support_plane",
            "距离1_context_1": "longitudinal_datum",
            "宽度17_context_1": "width_datum_a",
            "宽度17_context_2": "width_datum_b",
        },
    )
    a_module = build_plane_distance_width_contract(
        port=select_port(a_catalog, "A800.frame_installation"),
        release_manifest=r30,
        side="moving_module",
        module_role="Transport",
        module_definition_id="project02::A800",
        interface_variant_key="project02_a800_a600_width_context/v1",
        role_aliases={
            "mate_1_target_1": "support_plane",
            "mate_2_target_1": "width_datum_a",
            "mate_2_target_2": "width_datum_b",
            "mate_3_target_1": "longitudinal_datum",
        },
    )
    a_slot = build_plane_distance_width_contract(
        port=select_port(a_catalog, "A600.a800_installation"),
        release_manifest=r30,
        side="base_slot",
        module_role="Base",
        module_definition_id="project02::A600",
        accepted_module_roles=["Transport"],
        interface_variant_key="project02_a800_a600_width_context/v1",
        longitudinal_offset_meters=0.04949999999997534,
        role_aliases={
            "mate_1_context_1": "support_plane",
            "mate_2_context_1": "width_datum_a",
            "mate_2_context_2": "width_datum_b",
            "mate_3_context_1": "longitudinal_datum",
        },
    )
    contracts = [d_module, d_slot, a_module, a_slot]
    pair_release = {
        "moduleDefinitionId": "project05::D000",
        "slotDefinitionId": "project05::A000",
        "releaseId": r60["releaseId"],
        "releaseDigest": r60["releaseDigest"],
        "nonPrototypeCadValidated": True,
    }
    a800_pair_release = {
        "moduleDefinitionId": "project02::A800",
        "slotDefinitionId": "project02::A600",
        "releaseId": r30["releaseId"],
        "releaseDigest": r30["releaseDigest"],
        "nonPrototypeCadValidated": True,
    }
    matrix, templates = [], []
    for module in (d_module, a_module):
        for slot in (d_slot, a_slot):
            evidence = {
                ("project05::D000", "project05::A000"): pair_release,
                ("project02::A800", "project02::A600"): a800_pair_release,
            }.get((module["moduleDefinitionId"], slot["moduleDefinitionId"]))
            match = match_interface_contracts(
                module, slot, pair_release_evidence=evidence
            )
            matrix.append(match)
            if match["mateInstantiationAllowed"]:
                templates.append(instantiate_connection_template(match, module, slot))
    core = {
        "schemaVersion": CONTEXTUAL_TRANSPORT_CATALOG_SCHEMA,
        "role": "Transport",
        "contracts": contracts,
        "releasedPairEvidence": [pair_release, a800_pair_release],
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "summary": {
            "modulePortCount": 2,
            "baseSlotCount": 2,
            "compatiblePairCount": sum(row["compatible"] for row in matrix),
            "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
            "releasedPairCount": sum(row["existingPairReleaseReusable"] for row in matrix),
            "completeModulePortCount": 2,
            "incompleteModulePortCount": 0,
            "incompleteSlotPortCount": 0,
            "projectIdentityUsedForCompatibility": False,
        },
        "claimBoundary": (
            "D000/A000 and A800/A600 are released support-distance-width contextual "
            "installations. A800 uses the later non-anchor release with a prototype-estimated "
            "49.5 mm longitudinal datum; it is demo evidence, not vendor-authoritative geometry. "
            "Their distinct variants are not cross-matched, and no compatibility with 58 mm "
            "two-hole transport interfaces is inferred."
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
        "# 上下文型传输接口契约", "",
        "本目录登记Project05 D000与Project02 A800两套完整、已发布的三配合端口。", "",
        "| 传输模组 | 基座槽位 | 状态 | 主要原因 |",
        "|---|---|---|---|",
    ]
    for row in report["compatibilityMatrix"]:
        reasons = "；".join(item["code"] for item in row["blockers"]) or "完整契约且已有配对发布"
        lines.append(
            f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | {row['status']} | {reasons} |"
        )
    lines += [
        "", "## 结论", "",
        "- D000→A000：支承重合＋312 mm距离＋宽度居中，非原型CAD发布可复用。",
        "- A800→A600：支承重合＋49.5 mm纵向距离＋宽度居中，已通过非原型初始位姿CAD验证。",
        "- A800的49.5 mm来自原型估计而非厂商权威尺寸，因此只作为Demo级定位参数。",
        "- D000/A800均不自动兼容SS00/AE00的58 mm一面两轴接口；接口拓扑不同。",
        "- 碰撞/B-rep和实际紧固仍不在本层验收范围。",
    ]
    (OUTPUT / "README-CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

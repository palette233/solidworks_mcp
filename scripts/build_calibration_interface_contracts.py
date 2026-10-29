#!/usr/bin/env python3
"""Build the reusable Project01/03 calibration interface-contract matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    CALIBRATION_DISTANCE_WIDTH_FAMILY,
    CALIBRATION_DISTANCE_WIDTH_RECIPE_ID,
    FLEX_CALIBRATION_FAMILY,
    FLEX_CALIBRATION_RECIPE_ID,
    CALIBRATION_CATALOG_SCHEMA,
    _digest,
    build_plane_two_hole_contract,
    build_plane_distance_width_contract,
    build_flexible_calibration_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)


BD00 = ROOT / "demo/semantic_ports/project01_BD00_fifth_increment_v1"
AH00 = ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1"
A500 = ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/project02-a800-a180-a500-driving-v2/A500"
G000 = ROOT / "demo/global_assembly_catalog/coverage-v2/g000-four-relation-candidate-v1"
A600_ALTERNATE = ROOT / "demo/semantic_ports/project02_A600_project03_AH00_cross_project_slot_v1"
CROSS = ROOT / "demo/cross_project_substitution/calibration-project01-to-project03-v1/build_summary.json"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"
OUTPUT = ROOT / "demo/cross_project_substitution/calibration-interface-contract-v1"
FAMILY = "calibration_plane_two_hole_mount/v1"
RECIPE = "recipe/calibration-plane-two-hole-rigid-mount/v1"
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


def released_direct_pair(module_id: str, slot_id: str) -> dict | None:
    matches: list[dict] = []
    for path in sorted(RELEASES.glob("*/release-manifest.json")):
        manifest = read(path)
        binding = (manifest.get("releaseMetadata") or {}).get(
            "directInterfacePairBinding"
        ) or {}
        if (
            binding.get("moduleDefinitionId") == module_id
            and binding.get("slotDefinitionId") == slot_id
            and binding.get("nonPrototypeCadValidated") is True
            and binding.get("directMechanicalInterfaceCompatible") is True
        ):
            matches.append(manifest)
    if len(matches) > 1:
        raise ValueError(
            f"multiple immutable direct releases claim {module_id} -> {slot_id}"
        )
    return matches[0] if matches else None


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
    bd_summary = read(BD00 / "work_packet_summary.json")
    bd_catalog = read(BD00 / "semantic_port_catalog.json")
    ah_summary = read(AH00 / "work_packet_summary.json")
    ah_catalog = read(AH00 / "semantic_port_catalog.json")
    a500_catalog = read(A500 / "semantic_port_catalog.json")
    g000_catalog = read(G000 / "semantic_port_catalog.json")
    a600_alternate_catalog = read(A600_ALTERNATE / "semantic_port_catalog.json")
    cross = read(CROSS)
    source_spacing = cross["compatibility"]["locatingFeatureGeometry"]["source"]["pairSpacings"][0]["distanceMeters"]
    target_spacing = cross["compatibility"]["locatingFeatureGeometry"]["target"]["pairSpacings"][0]["distanceMeters"]
    if abs(source_spacing - target_spacing) > 1e-6:
        raise ValueError("published calibration interfaces no longer share one spacing")
    spacing = float(source_spacing)

    r9 = release("relation-v9-project01-driving-independent-20261011")
    r15 = release("relation-v15-project03-five-module-driving-20261011")
    r44 = release("relation-v44-project01-jj00-project03-ah00-calibration-driving-20261012")
    r45 = release("relation-v45-project03-aa00-project01-bd00-calibration-driving-20261012")
    r31 = release("relation-v31-project02-a800-a180-a500-portable-driving-20261011")
    r58 = release("relation-v58-project05-g000-static-four-relation-driving-20261014")
    r41 = release("relation-v41-project02-a600-project03-ah00-driving-20261012")

    def make(*, port: dict, summary: dict, manifest: dict, side: str, definition: str) -> dict:
        contract = build_plane_two_hole_contract(
            port=port,
            summary=summary,
            release_manifest=manifest,
            side=side,
            module_role="Calibration" if side == "moving_module" else "Base",
            module_definition_id=definition,
            accepted_module_roles=["Calibration"] if side == "base_slot" else None,
            interface_family=FAMILY,
            recipe_id=RECIPE,
            locating_axis_spacing_meters=spacing,
            role_aliases=ALIASES,
            axis_parallel_score=1.0,
            axis_relation_to_primary=1.0,
        )
        if manifest["releaseId"] == r9["releaseId"]:
            contract["releaseEvidence"]["geometryProvenanceOnly"] = True
            contract["contractId"] = "interface-contract/" + _digest(
                {key: value for key, value in contract.items() if key != "contractId"}
            )[:16]
        return contract

    contracts = [
        make(port=select_port(bd_catalog, "BD00.frame_installation"), summary=bd_summary,
             manifest=r9, side="moving_module", definition="project01::BD00"),
        make(port=select_port(bd_catalog, "JJ00.calibration_installation"), summary=bd_summary,
             manifest=r9, side="base_slot", definition="project01::JJ00"),
        make(port=select_port(ah_catalog, "AH00.frame_installation"), summary=ah_summary,
             manifest=r15, side="moving_module", definition="project03::AH00"),
        make(port=select_port(ah_catalog, "AA00.ah00_installation"), summary=ah_summary,
             manifest=r15, side="base_slot", definition="project03::AA00"),
        make(
            port=select_port(
                a600_alternate_catalog,
                "A600.calibration_slot_candidate.operation_side",
            ),
            summary={
                "projectId": "project02",
                "expectedResidualDof": 0,
                "drivingMateCount": 3,
                "secondaryAxis": {
                    "primaryIndependenceMeters": spacing,
                    "axisParallelScore": 1.0,
                    "axisRelationToPrimary": 1.0,
                },
            },
            manifest=r41,
            side="base_slot",
            definition="project02::A600",
        ),
        build_plane_distance_width_contract(
            port=select_port(a500_catalog, "A500.frame_installation"),
            release_manifest=r31,
            side="moving_module",
            module_role="Calibration",
            module_definition_id="project02::A500",
            interface_variant_key="project02_a500_a600_width_context/v1",
            role_aliases={
                "mate_1_target_1": "support_plane",
                "mate_2_target_1": "width_datum_a",
                "mate_2_target_2": "width_datum_b",
                "mate_3_target_1": "longitudinal_datum",
            },
            interface_family=CALIBRATION_DISTANCE_WIDTH_FAMILY,
            recipe_id=CALIBRATION_DISTANCE_WIDTH_RECIPE_ID,
        ),
        build_flexible_calibration_contract(
            port=select_port(g000_catalog, "G000.frame_installation"),
            release_manifest=r58,
            side="moving_module",
            module_definition_id="project05::G000",
            interface_variant_key="project05_g000_a000_flexible_slot/v1",
            role_aliases={
                "重合14_target_1": "support_plane",
                "平行4_target_1": "orientation_datum",
                "距离2_target_1": "longitudinal_datum",
                "槽口1_target_1": "slot_locator",
            },
        ),
        build_flexible_calibration_contract(
            port=select_port(g000_catalog, "A000.g000_installation"),
            release_manifest=r58,
            side="base_slot",
            module_definition_id="project05::A000",
            accepted_module_roles=["Calibration"],
            interface_variant_key="project05_g000_a000_flexible_slot/v1",
            role_aliases={
                "重合14_context_1": "support_plane",
                "平行4_context_1": "orientation_datum",
                "距离2_context_1": "longitudinal_datum",
                "槽口1_context_1": "slot_locator",
            },
            longitudinal_offset_meters=0.482,
        ),
        build_plane_distance_width_contract(
            port=select_port(a500_catalog, "A600.a500_installation"),
            release_manifest=r31,
            side="base_slot",
            module_role="Base",
            module_definition_id="project02::A600",
            accepted_module_roles=["Calibration"],
            interface_variant_key="project02_a500_a600_width_context/v1",
            role_aliases={
                "mate_1_context_1": "support_plane",
                "mate_2_context_1": "width_datum_a",
                "mate_2_context_2": "width_datum_b",
                "mate_3_context_1": "longitudinal_datum",
            },
            longitudinal_offset_meters=0.06,
            interface_family=CALIBRATION_DISTANCE_WIDTH_FAMILY,
            recipe_id=CALIBRATION_DISTANCE_WIDTH_RECIPE_ID,
        ),
    ]
    pair_rows = [
        pair_evidence("project01::BD00", "project03::AA00", r45),
        pair_evidence("project03::AH00", "project01::JJ00", r44),
        pair_evidence("project03::AH00", "project03::AA00", r15),
        pair_evidence("project03::AH00", "project02::A600", r41),
        pair_evidence("project02::A500", "project02::A600", r31),
        pair_evidence("project05::G000", "project05::A000", r58),
    ]
    # r9 supplies historical endpoint geometry, but authorizes GN00/SS00 only.
    # Geometry provenance must not authorize a different moving component.
    bd00_jj00_release = released_direct_pair("project01::BD00", "project01::JJ00")
    if bd00_jj00_release is not None:
        pair_rows.append(pair_evidence("project01::BD00", "project01::JJ00", bd00_jj00_release))
    bd00_a600_release = released_direct_pair("project01::BD00", "project02::A600")
    if bd00_a600_release is not None:
        pair_rows.append(
            pair_evidence(
                "project01::BD00", "project02::A600", bd00_a600_release
            )
        )
    pair_index = {(row["moduleDefinitionId"], row["slotDefinitionId"]): row for row in pair_rows}
    modules = [row for row in contracts if row["side"] == "moving_module"]
    slots = [row for row in contracts if row["side"] == "base_slot"]
    matrix, templates = [], []
    for module in modules:
        for slot in slots:
            match = match_interface_contracts(
                module,
                slot,
                pair_release_evidence=pair_index.get((module["moduleDefinitionId"], slot["moduleDefinitionId"])),
            )
            matrix.append(match)
            if match["mateInstantiationAllowed"]:
                templates.append(instantiate_connection_template(match, module, slot))

    core = {
        "schemaVersion": CALIBRATION_CATALOG_SCHEMA,
        "role": "Calibration",
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
            "genericRecipeCount": 3,
            "projectIdentityUsedForCompatibility": False,
            "crossProjectPairReleaseCount": sum(
                row["moduleDefinitionId"].split("::", 1)[0]
                != row["slotDefinitionId"].split("::", 1)[0]
                for row in pair_rows
            ),
            "locatingAxisSpacingMeters": spacing,
        },
        "claimBoundary": (
            "BD00 and AH00 share the geometrically matched 50 mm plane/two-axis calibration interface on "
            "JJ00 and AA00; A600 also exposes the CAD-validated AH00 alternate 50 mm slot, so "
            "BD00/A600 is compatible but still requires its own exact-pair CAD release. "
            "A500 uses a separate support/width/60 mm distance context on A600. "
            "G000 preserves internal flexibility through its released four-relation static bundle. "
            f"{len(pair_rows)} compatible pairs have non-prototype CAD releases; "
            + (
                "BD00/A600 remains an exact-pair CAD candidate. "
                if bd00_a600_release is None
                else "BD00/A600 has an exact-pair direct release. "
            )
            + "Calibration target "
            "accuracy, nozzle reach, collision and vendor fastening remain outside this layer."
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
        "# 校准模组通用接口契约", "",
        "BD00与AH00通过50 mm平面＋双定位轴匹配JJ00、AA00，并可复用A600已验证的50 mm备用槽位；A500通过独立的支承＋宽度＋60 mm距离契约匹配A600。", "",
        "| 校准模组 | 基座槽位 | 接口结果 | 已有非原型CAD发布 |", "|---|---|---|---|",
    ]
    for row in report["compatibilityMatrix"]:
        lines.append(
            f"| {row['moduleDefinitionId']} | {row['slotDefinitionId']} | {row['status']} | "
            f"{(row.get('pairReleaseEvidence') or {}).get('releaseId', '-')} |"
        )
    lines += [
        "", "## 边界", "",
        "- 项目编号不参与兼容判断；两个槽位都兼容时需要当前基座上下文或人工确认。",
        "- 四种组合均复用已有非原型位姿、三配合、完全定位和保存重开证据。",
        "- 本层不验证喷嘴到标定靶的精度、行程覆盖、紧固件和碰撞/B-rep。",
        "", "## API", "",
        "- `GET /api/demo/mechanical-interface-contracts/calibration`",
        "- `GET /api/demo/mechanical-interface-contracts/calibration/plan?moduleDefinitionId=project01::BD00`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(json_path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

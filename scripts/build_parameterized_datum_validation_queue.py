#!/usr/bin/env python3
"""Build the datum-pair validation queue and optionally materialize packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.parameterized_datum_placement import (  # noqa: E402
    compile_parameterized_datum_validation_package,
)
from demo_backend.hybrid_plane_axis_slot_selection import (  # noqa: E402
    compile_f000_hybrid_axis_validation_package,
)
from demo_backend.flexible_calibration_slot_selection import (  # noqa: E402
    compile_g000_flexible_slot_validation_package,
)
from demo_backend.parameterized_datum_validation_queue import (  # noqa: E402
    build_parameterized_datum_validation_queue,
)
from demo_backend.two_axis_slot_selection import (  # noqa: E402
    compile_two_axis_slot_validation_package,
)
from demo_backend.parameterized_datum_geometry_decisions import (  # noqa: E402
    geometry_decision_evidence_maps,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialize_package(output: Path, row: dict) -> None:
    target = output / row["proposedValidationDirectory"]
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite validation package: {target}")
    repeat_effective_graph = None
    if row.get("candidateKind") == "reviewed_hybrid_plane_axis_datum":
        evidence = row.get("axisSelectionEvidence") or {}
        package = compile_f000_hybrid_axis_validation_package(
            ROOT,
            slot_definition_id=row["slotDefinitionId"],
            selected_axis_endpoint_id=str(row["selectedAxisEndpointId"]),
            evidence=evidence,
        )
    elif row.get("candidateKind") == "reviewed_support_plane_two_axis_slot":
        evidence = row.get("axisPairSelectionEvidence") or {}
        package = compile_two_axis_slot_validation_package(
            ROOT,
            module_definition_id=row["moduleDefinitionId"],
            selected_candidate_pair_id=str(row["selectedCandidatePairId"]),
            evidence=evidence,
        )
    elif row.get("candidateKind") == "reviewed_flexible_calibration_slot":
        evidence = row.get("flexibleSlotSelectionEvidence") or {}
        package = compile_g000_flexible_slot_validation_package(
            ROOT,
            slot_definition_id=row["slotDefinitionId"],
            selected_axis_endpoint_id=str(row["selectedAxisEndpointId"]),
            longitudinal_offset_meters=float(row["longitudinalOffsetMeters"]),
            evidence=evidence,
        )
        repeat_package = compile_g000_flexible_slot_validation_package(
            ROOT,
            slot_definition_id=row["slotDefinitionId"],
            selected_axis_endpoint_id=str(row["selectedAxisEndpointId"]),
            longitudinal_offset_meters=float(row["longitudinalOffsetMeters"]),
            evidence=evidence,
            initial_placement_variant=2,
        )
        repeat_effective_graph = repeat_package.get("effectiveGraph")
        if not isinstance(repeat_effective_graph, dict):
            raise ValueError("flexible validation package has no repeat graph")
    else:
        package = compile_parameterized_datum_validation_package(
            ROOT,
            row["moduleDefinitionId"],
            row["slotDefinitionId"],
            position_parameters=row.get("positionParametersOverride"),
        )
        if (package.get("finiteSupportGate") or {}).get("required") is True:
            repeat_package = compile_parameterized_datum_validation_package(
                ROOT,
                row["moduleDefinitionId"],
                row["slotDefinitionId"],
                position_parameters=row.get("positionParametersOverride"),
                initial_placement_variant=2,
            )
            repeat_effective_graph = repeat_package.get("effectiveGraph")
            if not isinstance(repeat_effective_graph, dict):
                raise ValueError("finite-support validation package has no repeat graph")
            package["externalPlacementRepeatabilityRequired"] = True
            package["externalPlacementRepeatabilityKind"] = (
                "rigid_finite_support_pose"
            )
    target.mkdir(parents=True)
    graph = target / "effective-mate-graph.json"
    repeat_graph = target / "effective-mate-graph-repeat.json"
    endpoints = target / "selected-face-endpoint-catalog.json"
    manifest = target / "validation-package.json"
    effective_graph = package.pop(
        "effectiveGraph", package.pop("effectiveMateGraph", None)
    )
    if not isinstance(effective_graph, dict):
        raise ValueError("validation package has no effective graph")
    _write(graph, effective_graph)
    if repeat_effective_graph is not None:
        _write(repeat_graph, repeat_effective_graph)
    selected_endpoints = package.pop("selectedEndpointCatalog", None)
    if isinstance(selected_endpoints, dict):
        _write(endpoints, selected_endpoints)
    package["artifacts"] = {
        "effectiveGraph": {"path": str(graph.resolve()), "sha256": _sha256(graph)},
    }
    if repeat_graph.is_file():
        package["artifacts"]["repeatEffectiveGraph"] = {
            "path": str(repeat_graph.resolve()),
            "sha256": _sha256(repeat_graph),
            "initialPlacementVariant": 2,
        }
    if endpoints.is_file():
        package["artifacts"]["selectedEndpointCatalog"] = {
            "path": str(endpoints.resolve()),
            "sha256": _sha256(endpoints),
        }
    _write(manifest, package)


def _markdown(queue: dict) -> str:
    lines = [
        "# 参数化基准定位配对验证队列",
        "",
        "| 模组 | 基座 | 角色 | 跨项目 | 状态 | 下一步 |",
        "|---|---|---|---|---|---|",
    ]
    for row in queue["pairs"]:
        lines.append(
            "| {moduleDefinitionId} | {slotDefinitionId} | {moduleRole} | {cross} | {state} | {nextAction} |".format(
                **row, cross="是" if row["crossProject"] else "否"
            )
        )
    lines.extend(
        [
            "",
            "## 汇总",
            "",
            f"- 已发布：{queue['summary']['releasedPairCount']}",
            f"- 可进入CAD验证：{queue['summary']['readyForCadValidationCount']}",
            f"- CAD前阻断：{queue['summary']['blockedBeforeCadCount']}",
            f"- 需明确位置参数：{queue['summary']['explicitPositionParametersRequiredCount']}",
            f"- 已确认显式位置参数：{queue['summary']['confirmedExplicitPositionParameterCount']}",
            f"- 需明确孔轴候选：{queue['summary']['explicitAxisSelectionRequiredCount']}",
            f"- 已确认孔轴候选：{queue['summary']['confirmedExplicitAxisSelectionCount']}",
            f"- 需明确双定位轴对：{queue['summary']['explicitAxisPairSelectionRequiredCount']}",
            f"- 已确认双定位轴对：{queue['summary']['confirmedExplicitAxisPairSelectionCount']}",
            f"- 需明确G000槽定位轴与纵向距离：{queue['summary']['explicitFlexibleSlotSelectionRequiredCount']}",
            f"- 已确认G000槽定位轴与纵向距离：{queue['summary']['confirmedExplicitFlexibleSlotSelectionCount']}",
            f"- 尚需捕获端口：{queue['summary']['captureGapCount']}",
            "",
            "## 尚需捕获端口",
            "",
            *[
                f"- {row['moduleDefinitionId']}（{row['role']}）：{row['status']}"
                for row in queue["captureGaps"]
            ],
            "",
            "候选包不等于执行授权；只有非原型初始位姿、真实配合、保存关闭重开均通过并发布后，才能进入正常累计装配。",
            "",
        ]
    )
    return "\n".join(lines)


def write_parameterized_datum_validation_queue(
    output: Path,
    queue: dict,
    *,
    materialize_packages: bool,
) -> None:
    """Write one immutable queue directory and its optional CAD candidates."""

    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite queue directory: {output}")
    output.mkdir(parents=True)
    try:
        if materialize_packages:
            for row in queue["pairs"]:
                if row["state"] == "ready_for_nonprototype_cad_validation":
                    _materialize_package(output, row)
        _write(output / "validation-queue.json", queue)
        (output / "README-CN.md").write_text(_markdown(queue), encoding="utf-8")
    except Exception:
        # The caller owns recovery of a partially written directory.  Never
        # delete it silently because materialization inputs are audit evidence.
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--materialize-packages", action="store_true")
    parser.add_argument(
        "--explicit-position-parameters",
        type=Path,
        help=(
            "JSON file containing engineer-confirmed semantic position "
            "instructions or absolute longitudinal, lateral and supportGap "
            "parameters in metres."
        ),
    )
    parser.add_argument(
        "--explicit-axis-selections",
        type=Path,
        help=(
            "JSON file containing engineer-confirmed F000 base-axis endpoint "
            "selections for exact module/base pairs."
        ),
    )
    parser.add_argument(
        "--explicit-axis-pair-selections",
        type=Path,
        help=(
            "JSON file containing engineer-confirmed A000 support-plane/two-axis "
            "candidate-pair selections."
        ),
    )
    parser.add_argument(
        "--explicit-flexible-slot-selections",
        type=Path,
        help=(
            "JSON file containing engineer-confirmed G000 base-axis and "
            "longitudinal-offset selections."
        ),
    )
    parser.add_argument(
        "--geometry-decision-bundle",
        type=Path,
        help=(
            "Compiled geometry-decision evidence bundle. This replaces the three "
            "individual axis, axis-pair and flexible-slot evidence arguments."
        ),
    )
    args = parser.parse_args()
    if args.geometry_decision_bundle and any(
        (
            args.explicit_axis_selections,
            args.explicit_axis_pair_selections,
            args.explicit_flexible_slot_selections,
        )
    ):
        parser.error(
            "--geometry-decision-bundle cannot be combined with individual geometry evidence files"
        )
    output = args.output_dir.resolve()
    explicit_parameters = None
    if args.explicit_position_parameters:
        payload = json.loads(
            args.explicit_position_parameters.resolve().read_text(
                encoding="utf-8-sig"
            )
        )
        if payload.get("schemaVersion") != "parameterized-datum-position-parameters/v1":
            raise ValueError("Unsupported explicit position parameter file schema.")
        explicit_parameters = {}
        for row in payload.get("pairs") or []:
            pair = (
                str(row.get("moduleDefinitionId") or ""),
                str(row.get("slotDefinitionId") or ""),
            )
            if pair in explicit_parameters:
                raise ValueError(f"Duplicate explicit position parameter pair: {pair}")
            explicit_parameters[pair] = {
                "confirmed": row.get("confirmed"),
                "source": row.get("source"),
                "confirmedBy": row.get("confirmedBy"),
                "confirmedAt": row.get("confirmedAt"),
                "parametersMeters": row.get("parametersMeters"),
                "positionInstruction": row.get("positionInstruction"),
                "currentParametersMeters": row.get("currentParametersMeters"),
                "notes": row.get("notes"),
            }
    explicit_axes = None
    if args.explicit_axis_selections:
        payload = json.loads(
            args.explicit_axis_selections.resolve().read_text(
                encoding="utf-8-sig"
            )
        )
        if payload.get("schemaVersion") != "hybrid-plane-axis-selection-evidence/v1":
            raise ValueError("Unsupported explicit axis selection file schema.")
        explicit_axes = {}
        for row in payload.get("pairs") or []:
            pair = (
                str(row.get("moduleDefinitionId") or ""),
                str(row.get("slotDefinitionId") or ""),
            )
            if pair in explicit_axes:
                raise ValueError(f"Duplicate explicit axis selection pair: {pair}")
            explicit_axes[pair] = {
                "confirmed": row.get("confirmed"),
                "source": row.get("source"),
                "confirmedBy": row.get("confirmedBy"),
                "confirmedAt": row.get("confirmedAt"),
                "selectedAxisEndpointId": row.get("selectedAxisEndpointId"),
                "requestedPositionMeters": row.get("requestedPositionMeters"),
                "notes": row.get("notes"),
            }
    explicit_axis_pairs = None
    if args.explicit_axis_pair_selections:
        payload = json.loads(
            args.explicit_axis_pair_selections.resolve().read_text(
                encoding="utf-8-sig"
            )
        )
        if payload.get("schemaVersion") != "two-axis-slot-selection-evidence/v1":
            raise ValueError("Unsupported explicit axis-pair selection file schema.")
        explicit_axis_pairs = {}
        for row in payload.get("pairs") or []:
            pair = (
                str(row.get("moduleDefinitionId") or ""),
                str(row.get("slotDefinitionId") or ""),
            )
            if pair in explicit_axis_pairs:
                raise ValueError(f"Duplicate explicit axis-pair selection: {pair}")
            explicit_axis_pairs[pair] = {
                "confirmed": row.get("confirmed"),
                "source": row.get("source"),
                "confirmedBy": row.get("confirmedBy"),
                "confirmedAt": row.get("confirmedAt"),
                "selectedCandidatePairId": row.get("selectedCandidatePairId"),
                "notes": row.get("notes"),
            }
    explicit_flexible_slots = None
    if args.explicit_flexible_slot_selections:
        payload = json.loads(
            args.explicit_flexible_slot_selections.resolve().read_text(
                encoding="utf-8-sig"
            )
        )
        if (
            payload.get("schemaVersion")
            != "flexible-calibration-slot-selection-evidence/v1"
        ):
            raise ValueError("Unsupported explicit flexible-slot selection schema.")
        explicit_flexible_slots = {}
        for row in payload.get("pairs") or []:
            pair = (
                str(row.get("moduleDefinitionId") or ""),
                str(row.get("slotDefinitionId") or ""),
            )
            if pair in explicit_flexible_slots:
                raise ValueError(f"Duplicate explicit flexible-slot selection: {pair}")
            explicit_flexible_slots[pair] = {
                "confirmed": row.get("confirmed"),
                "source": row.get("source"),
                "confirmedBy": row.get("confirmedBy"),
                "confirmedAt": row.get("confirmedAt"),
                "selectedAxisEndpointId": row.get("selectedAxisEndpointId"),
                "longitudinalOffsetMeters": row.get("longitudinalOffsetMeters"),
                "notes": row.get("notes"),
            }
    if args.geometry_decision_bundle:
        bundle = json.loads(
            args.geometry_decision_bundle.resolve().read_text(encoding="utf-8-sig")
        )
        maps = geometry_decision_evidence_maps(bundle)
        explicit_axes = maps["axisSelections"]
        explicit_axis_pairs = maps["axisPairSelections"]
        explicit_flexible_slots = maps["flexibleSlotSelections"]
    queue = build_parameterized_datum_validation_queue(
        ROOT,
        explicit_position_parameters=explicit_parameters,
        explicit_axis_selections=explicit_axes,
        explicit_axis_pair_selections=explicit_axis_pairs,
        explicit_flexible_slot_selections=explicit_flexible_slots,
    )
    write_parameterized_datum_validation_queue(
        output,
        queue,
        materialize_packages=args.materialize_packages,
    )
    print(json.dumps(queue["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

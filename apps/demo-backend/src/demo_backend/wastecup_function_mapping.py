"""Select explicit dual-cup function mappings without authorizing CAD.

The target base supplies the native cup station while the moving module
supplies its own measured cup openings.  This module evaluates every explicit
one-to-one mapping for the already validated installation orientation.  It
never copies the source prototype pose and it never publishes a relation.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from .calibration_function_point import EXTENSION_CANDIDATE_REPORT_SCHEMA
from .cup_function_point import (
    build_cup_function_point_report,
    screen_mapped_cup_planar_translation,
)
from .role_station_geometry import _dot, _transform


CONFIG_SCHEMA = "wastecup-function-mapping-batch/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(root: Path, value: str) -> Path:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    path.relative_to(root)
    if not path.is_file():
        raise ValueError(f"wastecup mapping evidence is missing: {path}")
    return path


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    token = token.upper()
    rows = [
        row for row in graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper().endswith(token)
    ]
    if len(rows) != 1:
        raise ValueError(f"wastecup mapping module is missing or ambiguous: {token}")
    return rows[0]


def _points(report: dict[str, Any], role: str) -> list[dict[str, Any]]:
    if role not in {"source", "native"}:
        raise ValueError("cup geometry role must be source or native")
    rows = [point for group in report["geometry"][role] for point in group["points"]]
    if len(rows) != 2 or len({row["pointId"] for row in rows}) != 2:
        raise ValueError("dual-cup mapping requires exactly two distinct measured openings")
    return sorted(rows, key=lambda row: row["leafPath"])


def select_unique_cup_mapping(
    *, source_points: list[dict[str, Any]], native_points: list[dict[str, Any]],
    source_pose: list[float], base_pose: list[float], native_pose: list[float],
    native_base_pose: list[float], support_normal_base_local: list[float],
    radial_margin_meters: float,
) -> dict[str, Any]:
    """Rank both one-to-one mappings for one fixed, already verified orientation."""

    candidates = []
    for permutation in itertools.permutations(native_points):
        mapping = {
            source["pointId"]: native["pointId"]
            for source, native in zip(source_points, permutation, strict=True)
        }
        screening = screen_mapped_cup_planar_translation(
            source_points=source_points,
            native_points=native_points,
            mapping=mapping,
            source_pose=source_pose,
            base_pose=base_pose,
            native_pose=native_pose,
            native_base_pose=native_base_pose,
            support_normal_base_local=support_normal_base_local,
            radial_margin_meters=radial_margin_meters,
        )
        candidates.append({
            "mapping": mapping,
            "mappingByLeaf": {
                source["leafPath"]: native["leafPath"]
                for source, native in zip(source_points, permutation, strict=True)
            },
            "screening": screening,
        })
    candidates.sort(key=lambda row: row["screening"]["maximumPlanarMappingResidualMeters"])
    passed = [row for row in candidates if row["screening"]["passed"] is True]
    selected = passed[0] if len(passed) == 1 else None
    return {
        "status": (
            "mapping_selected_for_published_orientation"
            if selected is not None
            else "multiple_function_mappings_fit_published_orientation"
            if len(passed) > 1
            else "no_function_mapping_fits_published_orientation"
        ),
        "selected": selected,
        "candidateCount": len(candidates),
        "passingCandidateCount": len(passed),
        "candidates": candidates,
    }


def build_wastecup_function_mapping_report(
    workspace: Path, config: dict[str, Any]
) -> dict[str, Any]:
    """Build standardized offline decisions for all configured dual-cup pairs."""

    root = workspace.resolve()
    if config.get("schemaVersion") != CONFIG_SCHEMA:
        raise ValueError("unsupported wastecup function-mapping config schema")
    entries = config.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("wastecup function-mapping config has no entries")
    decisions, evidence, seen = [], {}, set()
    for spec in entries:
        required = (
            "sourceModuleDefinitionId", "targetBaseDefinitionId",
            "sourceGeometryRequestPath", "sourceGeometryRole",
            "targetGeometryRequestPath", "targetGeometryRole",
            "pairCadResultPath", "pairGraphPath", "nativeGraphPath",
            "sourceToken", "baseToken", "nativeModuleToken", "nativeBaseToken",
        )
        if any(not isinstance(spec.get(key), str) or not spec[key] for key in required):
            raise ValueError("wastecup function-mapping entry is incomplete")
        key = (spec["sourceModuleDefinitionId"], spec["targetBaseDefinitionId"])
        if key in seen:
            raise ValueError(f"duplicate wastecup function-mapping pair: {key}")
        seen.add(key)
        paths = {
            name: _file(root, spec[name])
            for name in (
                "sourceGeometryRequestPath", "targetGeometryRequestPath",
                "pairCadResultPath", "pairGraphPath", "nativeGraphPath",
            )
        }
        for path in paths.values():
            evidence[str(path)] = {"path": str(path), "sha256": _sha(path)}
        source_report = build_cup_function_point_report(paths["sourceGeometryRequestPath"])
        target_report = build_cup_function_point_report(paths["targetGeometryRequestPath"])
        source_points = _points(source_report, spec["sourceGeometryRole"])
        native_points = _points(target_report, spec["targetGeometryRole"])
        if any(row["moduleDefinitionId"] != spec["sourceModuleDefinitionId"] for row in source_points):
            raise ValueError("source cup geometry does not match configured module")
        cad, graph, native_graph = (
            _read(paths["pairCadResultPath"]), _read(paths["pairGraphPath"]),
            _read(paths["nativeGraphPath"]),
        )
        tool = cad.get("toolResult") or {}
        output = Path(str(cad.get("outputAssemblyPath") or ""))
        if (
            cad.get("success") is not True
            or cad.get("sourceAssemblyUnchanged") is not True
            or tool.get("Success") is not True
            or tool.get("Reopened") is not True
            or tool.get("TargetFullyConstrained") is not True
            or tool.get("MateSolveClean") is not True
            or int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) != 0
            or not output.is_file()
            or _sha(output) != cad.get("outputAssemblySha256")
            or _sha(paths["pairGraphPath"])
            != (cad.get("executionEffectiveGraphSha256") or cad.get("effectiveGraphSha256"))
        ):
            raise ValueError("wastecup mapping pair CAD evidence is not reusable")
        source_module = _module(graph, spec["sourceToken"])
        base_module = _module(graph, spec["baseToken"])
        native_module = _module(native_graph, spec["nativeModuleToken"])
        native_base = _module(native_graph, spec["nativeBaseToken"])
        if not str(tool.get("TargetModuleToken") or "").upper().endswith(
            spec["sourceToken"].upper()
        ):
            raise ValueError("wastecup mapping CAD target identity differs")
        support = [row for row in graph["Mates"] if row.get("MateType") == 0]
        if len(support) != 1:
            raise ValueError("wastecup mapping requires one support mate")
        base_endpoints = [
            row for row in support[0]["Endpoints"]
            if str(row.get("ModuleToken") or "").upper().endswith(spec["baseToken"].upper())
        ]
        if len(base_endpoints) != 1:
            raise ValueError("wastecup support endpoint does not bind the target base")
        base_pose = _transform(base_module["SourceTransform"])
        world_normal = base_endpoints[0]["FaceNormalWorld"]
        support_normal = [
            _dot(world_normal, base_pose[index:index + 3]) for index in (0, 3, 6)
        ]
        selected = select_unique_cup_mapping(
            source_points=source_points,
            native_points=native_points,
            source_pose=tool["ReopenedTargetRootTransform"],
            base_pose=base_pose,
            native_pose=native_module["SourceTransform"],
            native_base_pose=native_base["SourceTransform"],
            support_normal_base_local=support_normal,
            radial_margin_meters=float(spec.get("radialMarginMeters", 0.005)),
        )
        mapping_selected = selected["selected"] is not None
        decisions.append({
            "sourceModuleDefinitionId": spec["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": spec["targetBaseDefinitionId"],
            "role": "WasteCup",
            "interfaceTopology": "support_plane_two_offset_position_with_dual_cup_mapping",
            "status": (
                "wastecup_mapping_selected_requires_saved_base_pose_and_station_candidate"
                if mapping_selected else selected["status"]
            ),
            "readyForCadValidation": False,
            "cadLaunchAllowed": False,
            "mappingDecision": selected,
            "nextAction": (
                "capture_or_reuse_authenticated_saved_base_pose_then_derive_new_"
                "position_parameters_and_run_nonprototype_cad"
                if mapping_selected else
                "obtain_engineering_mapping_or_select_a_different_target_station"
            ),
            "claimBoundary": (
                "The selected one-to-one cup mapping only proves that target native points "
                "fit inside the measured source openings after one planar translation for "
                "the already validated installation orientation. It is not a new station "
                "placement, CAD validation, dispensing, fastening or collision approval."
            ),
        })
    report = {
        "schemaVersion": EXTENSION_CANDIDATE_REPORT_SCHEMA,
        "candidates": decisions,
        "summary": {
            "candidateCount": len(decisions),
            "mappingSelectedCount": sum(
                row["status"].startswith("wastecup_mapping_selected_")
                for row in decisions
            ),
        },
        "evidence": sorted(evidence.values(), key=lambda row: row["path"]),
        "cadExecuted": False,
        "boundary": "Offline function mapping only; no CAD or relation authority.",
    }
    report["reportDigest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return report

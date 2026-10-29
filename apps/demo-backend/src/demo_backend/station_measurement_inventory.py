"""Merge reviewed native role stations into the reusable measurement inventory.

The result remains measurement evidence.  It never creates a station rule,
authorizes CAD, or copies a prototype world transform into execution.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "station-measurement-reuse-index/v1"
NATIVE_SCHEMA = "native-role-station-review-evidence/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_binding(role: str) -> list[str]:
    return {
        "Transport": [
            "bind_source_track_and_work_area_to_target_native_transport_station",
            "recompute_scanner_target_association_for_selected_transport_instance",
        ],
        "Calibration": [
            "bind_source_calibration_function_point_to_target_native_station",
        ],
        "CleaningWeighing": [
            "bind_source_service_subtrees_to_target_service_station",
            "verify_target_capability_coverage",
        ],
        "WasteCup": [
            "bind_source_cup_function_points_to_target_native_station",
        ],
        "Scanner": [
            "bind_source_optical_frame_to_selected_transport_target",
        ],
    }.get(role, ["bind_source_function_to_target_native_station"])


def merge_native_role_station_measurements(
    workspace: Path,
    base_index_path: Path,
    native_evidence_path: Path,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    base_path = Path(base_index_path)
    base_path = base_path if base_path.is_absolute() else root / base_path
    native_path = Path(native_evidence_path)
    native_path = native_path if native_path.is_absolute() else root / native_path
    base, native = _read(base_path), _read(native_path)
    if base.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported measurement inventory schema")
    if native.get("schemaVersion") != NATIVE_SCHEMA:
        raise ValueError("unsupported native role station evidence schema")
    if native.get("status") != "review_only_native_role_station_evidence":
        raise ValueError("native role station evidence is not ready")
    entries = json.loads(json.dumps(base.get("entries") or []))
    existing = {
        (
            row.get("targetBaseDefinitionId"),
            row.get("role"),
            row.get("nativeRoleModuleDefinitionId"),
        )
        for row in entries
    }
    added = 0
    for station in native.get("stations") or []:
        key = (
            station.get("baseDefinitionId"),
            station.get("moduleRole"),
            station.get("moduleDefinitionId"),
        )
        if not all(key) or key in existing:
            continue
        parameters = station.get("parametersMeters") or {}
        if set(parameters) != {"longitudinal", "lateral", "supportGap"}:
            raise ValueError(f"native station parameters incomplete: {key}")
        if station.get("reviewOnly") is not True or station.get(
            "prototypePoseAllowedAsCadExecutionAuthority"
        ) is not False:
            raise ValueError(f"native station execution boundary changed: {key}")
        release = station.get("nativeRelationRelease") or {}
        release_path = str(release.get("manifestPath") or "").replace("\\", "/")
        paths = [
            str(native_path.relative_to(root)).replace("\\", "/"),
            str(station.get("moduleEndpointCatalogPath") or ""),
            str(station.get("baseEndpointCatalogPath") or ""),
            release_path,
        ]
        if any(not value or not (root / value).is_file() for value in paths):
            raise ValueError(f"native station evidence path missing: {key}")
        entries.append({
            "targetBaseDefinitionId": key[0],
            "role": key[1],
            "nativeRoleModuleDefinitionId": key[2],
            "paths": paths,
            "available": [
                "reviewed_native_role_station_signed_parameters",
                "complete_three_plane_datum_contracts",
                "immutable_native_relation_release",
                "shared_source_assembly_measurement_frame",
            ],
            "stillRequired": _required_binding(str(key[1])),
            "nativeStationParametersMeters": parameters,
            "nativeStationEvidenceDigest": station.get("evidenceDigest"),
            "acquisitionStatus": "reviewed_prototype_native_station_measurement",
            "boundary": (
                "Review-only native station measurement. It may seed an exact "
                "cross-project candidate after semantic binding, but it is not "
                "a prototype-pose execution authority or CAD validation."
            ),
        })
        existing.add(key)
        added += 1
    return {
        "schemaVersion": SCHEMA,
        "entries": entries,
        "generation": {
            "baseIndexPath": str(base_path.relative_to(root)).replace("\\", "/"),
            "baseIndexSha256": _sha(base_path),
            "nativeEvidencePath": str(native_path.relative_to(root)).replace("\\", "/"),
            "nativeEvidenceSha256": _sha(native_path),
            "addedNativeStationCount": added,
            "cadExecuted": False,
        },
    }

"""Derive review-only WasteCup station parameters from authenticated saved CAD.

The dual-cup mapping layer selects a functional correspondence but intentionally
does not create a placement.  This bridge consumes that immutable mapping plus a
fresh read-only inspection of the already saved pair assembly and translates the
selected in-plane shift into the two distance parameters of the existing
support-plane/two-offset interface.

The result is never CAD or release authority.  It is a deterministic candidate
that must be executed again from a non-prototype initial pose and pass the normal
save/reopen and target-station postcheck gates.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .role_station_geometry import _direction, _dot, _transform, _vector
from .saved_output_station_inspection import (
    authenticate_saved_output_station_inspection_binding,
)
from .wastecup_function_mapping import (
    CONFIG_SCHEMA as MAPPING_CONFIG_SCHEMA,
    build_wastecup_function_mapping_report,
)


SCHEMA = "wastecup-station-candidate/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    path.relative_to(root)
    if not path.is_file():
        raise ValueError(f"wastecup station-candidate evidence is missing: {path}")
    return path


def _canonical_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("candidateDigest", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _one(rows: list[dict[str, Any]], predicate, message: str) -> dict[str, Any]:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise ValueError(message)
    return matches[0]


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    token = token.upper()
    return _one(
        graph.get("Modules") or [],
        lambda row: str(row.get("ModuleToken") or "").upper().endswith(token),
        f"expected one graph module for {token}",
    )


def _component(state: dict[str, Any], token: str) -> dict[str, Any]:
    marker = f"{token.upper()}.001"

    def matches(row: dict[str, Any]) -> bool:
        name = str(row.get("name") or "").upper()
        source = Path(str(row.get("sourcePath") or "")).stem.upper()
        return marker in name or source.endswith(marker)

    return _one(
        (state.get("observed") or {}).get("components") or [],
        matches,
        f"expected one saved component for {token}",
    )


def _same_path(first: str | Path, second: str | Path) -> bool:
    return Path(first).resolve() == Path(second).resolve()


def _same_transform(first: Any, second: Any, tolerance: float = 1e-8) -> bool:
    return max(abs(a - b) for a, b in zip(
        _transform(first), _transform(second), strict=True
    )) <= tolerance


def _selected_mapping_candidate(
    report: dict[str, Any], source_id: str, target_id: str
) -> dict[str, Any]:
    candidate = _one(
        report.get("candidates") or [],
        lambda row: row.get("sourceModuleDefinitionId") == source_id
        and row.get("targetBaseDefinitionId") == target_id,
        "wastecup mapping candidate is absent or ambiguous",
    )
    decision = candidate.get("mappingDecision") or {}
    selected = decision.get("selected")
    if (
        candidate.get("status")
        != "wastecup_mapping_selected_requires_saved_base_pose_and_station_candidate"
        or decision.get("status") != "mapping_selected_for_published_orientation"
        or not isinstance(selected, dict)
        or (selected.get("screening") or {}).get("passed") is not True
    ):
        raise ValueError("wastecup mapping is not uniquely selected and passing")
    return candidate


def _mapping_entry(
    config: dict[str, Any], source_id: str, target_id: str
) -> dict[str, Any]:
    if config.get("schemaVersion") != MAPPING_CONFIG_SCHEMA:
        raise ValueError("unsupported wastecup mapping config")
    return _one(
        config.get("entries") or [],
        lambda row: row.get("sourceModuleDefinitionId") == source_id
        and row.get("targetBaseDefinitionId") == target_id,
        "wastecup mapping config pair is absent or ambiguous",
    )


def _authenticate_saved_state(
    *, root: Path, binding: dict[str, Any], state_path: Path,
    graph: dict[str, Any], cad: dict[str, Any], base_token: str,
    target_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if state_path != Path(binding["outputStatePath"]).resolve():
        raise ValueError("saved state does not belong to the inspection request")
    state = _read(state_path)
    checks = state.get("checks") or {}
    observed = state.get("observed") or {}
    if (
        state.get("schemaVersion") != "p000-support-position-readonly-state/v1"
        or
        state.get("success") is not True
        or observed.get("readOnly") is not True
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise ValueError("saved state is not a successful read-only inspection")
    assembly = Path(str(state.get("assemblyPath") or "")).resolve()
    if (
        assembly != Path(binding["outputAssemblyPath"]).resolve()
        or not assembly.is_file()
        or _sha(assembly) != state.get("assemblySha256")
        or state.get("assemblySha256") != binding["outputAssemblySha256"]
    ):
        raise ValueError("saved state assembly identity changed")
    components = observed.get("components") or []
    if len(components) != binding["expectedTopLevelComponentCount"]:
        raise ValueError("saved state component count differs from the request")
    base = _component(state, base_token)
    target = _component(state, target_token)
    fixed = [row for row in components if row.get("isFixed") is True]
    if len(fixed) != 1 or fixed[0] is not base or target.get("isFixed") is not False:
        raise ValueError("only the target base may be fixed")
    if target.get("constrainedStatus") != 3:
        raise ValueError("saved target is not fully constrained")
    tool = cad.get("toolResult") or {}
    if (
        Path(str(target.get("sourcePath") or "")).resolve()
        != Path(str(tool.get("TargetModuleSourcePath") or "")).resolve()
        or str(target.get("name") or "") != str(tool.get("InsertedComponentName") or "")
    ):
        raise ValueError("saved target component identity differs from the bound CAD")
    if not _same_transform(target.get("transform"), tool.get("ReopenedTargetRootTransform")):
        raise ValueError("saved target transform differs from the bound CAD reopen")
    graph_base = _module(graph, base_token)
    if not _same_transform(base.get("transform"), graph_base.get("SourceTransform")):
        raise ValueError("saved base transform differs from the executed graph")
    return base, target


def _derive_distance_parameters(
    *, graph: dict[str, Any], base_token: str, target_token: str,
    planar_shift_base_local: list[float],
) -> tuple[dict[str, float], dict[str, bool], list[dict[str, Any]], list[float]]:
    base_pose = _transform(_module(graph, base_token)["SourceTransform"])
    mates = graph.get("Mates") or []
    if len(mates) != 3 or any(row.get("IsSuppressed") is True for row in mates):
        raise ValueError("wastecup station candidate requires three active mates")
    parameters: dict[str, float] = {"supportGap": 0.0}
    flips: dict[str, bool] = {"supportGap": False}
    derivation: list[dict[str, Any]] = []
    support_normal: list[float] | None = None
    roles: set[str] = set()
    for mate in mates:
        endpoints = mate.get("Endpoints") or []
        base_endpoint = _one(
            endpoints,
            lambda row: str(row.get("ModuleToken") or "").upper().endswith(
                base_token.upper()
            ),
            "mate does not contain one target-base endpoint",
        )
        _one(
            endpoints,
            lambda row: str(row.get("ModuleToken") or "").upper().endswith(
                target_token.upper()
            ),
            "mate does not contain one moving-module endpoint",
        )
        normal_world = _vector(base_endpoint.get("FaceNormalWorld"), 3)
        normal_base = _direction(normal_world, base_pose, inverse=True)
        length = math.sqrt(_dot(normal_base, normal_base))
        if abs(length - 1.0) > 1e-6:
            raise ValueError("target-base datum normal is not unit length")
        shift_projection = _dot(planar_shift_base_local, normal_base)
        if mate.get("MateType") == 0:
            if support_normal is not None or abs(shift_projection) > 1e-7:
                raise ValueError("selected cup translation leaves the support plane")
            support_normal = normal_base
            derivation.append({
                "mateName": mate.get("MateName"),
                "parameterRole": "supportGap",
                "baseNormalLocal": normal_base,
                "shiftProjectionMeters": shift_projection,
                "derivedMagnitudeMeters": 0.0,
                "derivedFlipDimension": False,
            })
            continue
        if mate.get("MateType") != 5:
            raise ValueError("wastecup station candidate expects two distance mates")
        name = str(mate.get("MateName") or "").upper()
        role = "longitudinal" if "LONGITUDINAL" in name else (
            "lateral" if "LATERAL" in name else ""
        )
        if not role or role in roles:
            raise ValueError("distance-mate roles are missing or duplicated")
        roles.add(role)
        distance = mate.get("Distance")
        if (
            isinstance(distance, bool)
            or not isinstance(distance, (int, float))
            or not math.isfinite(distance)
            or distance < 0
        ):
            raise ValueError("distance mate has an invalid magnitude")
        flip = (mate.get("AdvancedOptions") or {}).get(
            "DistanceFlipDimension", False
        )
        if not isinstance(flip, bool):
            raise ValueError("distance-mate direction is invalid")
        current_signed = -float(distance) if flip else float(distance)
        derived_signed = current_signed + shift_projection
        parameters[role] = abs(derived_signed)
        flips[role] = derived_signed < 0
        derivation.append({
            "mateName": mate.get("MateName"),
            "parameterRole": role,
            "baseNormalLocal": normal_base,
            "currentSignedDistanceMeters": current_signed,
            "shiftProjectionMeters": shift_projection,
            "derivedSignedDistanceMeters": derived_signed,
            "derivedMagnitudeMeters": abs(derived_signed),
            "derivedFlipDimension": derived_signed < 0,
        })
    if roles != {"longitudinal", "lateral"} or support_normal is None:
        raise ValueError("wastecup station candidate lacks a complete datum bundle")
    return parameters, flips, derivation, support_normal


def build_wastecup_station_candidate(
    workspace: Path,
    *,
    mapping_config_path: Path,
    mapping_report_path: Path,
    inspection_request_path: Path,
    saved_state_path: Path,
    source_module_definition_id: str,
    target_base_definition_id: str,
) -> dict[str, Any]:
    """Create one review candidate; never launch CAD or publish a relation."""

    started_at = datetime.now(timezone.utc).isoformat()
    clock = perf_counter()
    root = workspace.resolve()
    mapping_config_path = _resolve(root, mapping_config_path)
    mapping_report_path = _resolve(root, mapping_report_path)
    inspection_request_path = _resolve(root, inspection_request_path)
    saved_state_path = _resolve(root, saved_state_path)
    config = _read(mapping_config_path)
    report = _read(mapping_report_path)
    rebuilt = build_wastecup_function_mapping_report(root, config)
    if report != rebuilt:
        raise ValueError("wastecup mapping report is stale or changed")
    candidate = _selected_mapping_candidate(
        report, source_module_definition_id, target_base_definition_id
    )
    spec = _mapping_entry(
        config, source_module_definition_id, target_base_definition_id
    )
    binding = authenticate_saved_output_station_inspection_binding(
        root, inspection_request_path
    )
    cad_path = _resolve(root, spec["pairCadResultPath"])
    graph_path = _resolve(root, spec["pairGraphPath"])
    if (
        not _same_path(cad_path, binding["cadResultPath"])
        or not _same_path(graph_path, binding["effectiveGraphPath"])
    ):
        raise ValueError("mapping and read-only inspection bind different CAD evidence")
    cad, graph = _read(cad_path), _read(graph_path)
    if _sha(graph_path) != binding["effectiveGraphSha256"]:
        raise ValueError("executed graph changed after inspection planning")
    base, target = _authenticate_saved_state(
        root=root,
        binding=binding,
        state_path=saved_state_path,
        graph=graph,
        cad=cad,
        base_token=spec["baseToken"],
        target_token=spec["sourceToken"],
    )
    selected = candidate["mappingDecision"]["selected"]
    screening = selected["screening"]
    shift = _vector(screening["commonPlanarTranslationBaseLocalMeters"], 3)
    parameters, flips, derivation, support_normal = _derive_distance_parameters(
        graph=graph,
        base_token=spec["baseToken"],
        target_token=spec["sourceToken"],
        planar_shift_base_local=shift,
    )
    observations = screening.get("observations") or []
    point_checks = screening.get("pointChecks") or []
    if len(observations) != 2 or len(point_checks) != 2:
        raise ValueError("selected cup mapping does not contain two point checks")
    recomputed_residuals = []
    for observation, point_check in zip(observations, point_checks, strict=True):
        source = _vector(observation["sourceCenterBaseLocalMeters"], 3)
        native = _vector(observation["nativeTargetCenterBaseLocalMeters"], 3)
        delta = [source[i] + shift[i] - native[i] for i in range(3)]
        normal_component = _dot(delta, support_normal)
        planar = [
            delta[i] - normal_component * support_normal[i] for i in range(3)
        ]
        residual = math.sqrt(_dot(planar, planar))
        if (
            abs(residual - float(point_check["centerResidualAfterCommonTranslationMeters"]))
            > 1e-8
        ):
            raise ValueError("selected cup mapping residual changed")
        recomputed_residuals.append(residual)
    base_transform = _transform(base["transform"])
    target_transform = _transform(target["transform"])
    world_shift = _direction(shift, base_transform)
    candidate_transform = list(target_transform)
    for index in range(3):
        candidate_transform[9 + index] += world_shift[index]
    evidence_paths = [
        mapping_config_path,
        mapping_report_path,
        inspection_request_path,
        saved_state_path,
        cad_path,
        graph_path,
        Path(binding["outputAssemblyPath"]).resolve(),
    ]
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA,
        "sourceModuleDefinitionId": source_module_definition_id,
        "targetBaseDefinitionId": target_base_definition_id,
        "role": "WasteCup",
        "status": "review_candidate_requires_fresh_nonprototype_cad",
        "selectedFunctionMapping": selected["mapping"],
        "selectedFunctionMappingByLeaf": selected["mappingByLeaf"],
        "planarTranslationBaseLocalMeters": shift,
        "positionParametersMeters": parameters,
        "distanceFlipDimensions": flips,
        "parameterDerivation": derivation,
        "functionalMappingCheck": {
            "pointCount": 2,
            "recomputedPlanarResidualMeters": recomputed_residuals,
            "maximumPlanarResidualMeters": max(recomputed_residuals),
            "allTargetPointsInsideMeasuredOpenings": all(
                row.get("nativePointInsideSourceOpeningAfterTranslation") is True
                for row in point_checks
            ),
        },
        "currentSavedTargetTransform": target_transform,
        "candidateTargetTransformForReviewOnly": candidate_transform,
        "candidateWorldTranslationMeters": world_shift,
        "sourceWorldPoseCopied": False,
        "prototypeExecutionPoseUsed": False,
        "cadLaunchAllowed": False,
        "freshNonPrototypeCadRequired": True,
        "saveReopenRequired": True,
        "targetStationPostcheckRequired": True,
        "collisionOrBrep": "not_evaluated",
        "actualFastening": "not_verified",
        "timing": {
            "startedAtUtc": started_at,
            "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
            "planningSeconds": perf_counter() - clock,
            "cadExecutionSeconds": 0.0,
            "saveReopenSeconds": 0.0,
            "stationPostcheckSeconds": 0.0,
        },
        "evidence": [
            {"path": str(path), "sha256": _sha(path)} for path in evidence_paths
        ],
        "claimBoundary": (
            "Authenticated saved CAD and the selected dual-cup mapping were used "
            "to derive a new two-distance candidate. This is not a CAD result, "
            "relation release, dispensing validation, fastening approval or "
            "collision/B-rep result."
        ),
    }
    result["candidateDigest"] = _canonical_digest(result)
    return result


def build_wastecup_station_candidate_batch(
    workspace: Path,
    *,
    mapping_config_path: Path,
    mapping_report_path: Path,
    inspection_batch_path: Path,
) -> dict[str, Any]:
    """Plan all mapped WasteCup pairs and materialize no CAD side effects."""

    started_at = datetime.now(timezone.utc).isoformat()
    clock = perf_counter()
    root = workspace.resolve()
    mapping_config_path = _resolve(root, mapping_config_path)
    mapping_report_path = _resolve(root, mapping_report_path)
    inspection_batch_path = _resolve(root, inspection_batch_path)
    batch = _read(inspection_batch_path)
    if (
        batch.get("schemaVersion") != "saved-output-inspection-batch/v1"
        or batch.get("role") != "WasteCup"
        or batch.get("requestCount") != len(batch.get("requests") or [])
    ):
        raise ValueError("unsupported WasteCup saved-output inspection batch")
    rows = []
    for item in batch["requests"]:
        request_path = _resolve(root, item.get("requestPath") or "")
        binding = authenticate_saved_output_station_inspection_binding(
            root, request_path
        )
        if binding["requestDigest"] != item.get("requestDigest"):
            raise ValueError("inspection batch request digest changed")
        state_path = Path(binding["outputStatePath"]).resolve()
        row: dict[str, Any] = {
            "sourceModuleDefinitionId": item.get("sourceModuleDefinitionId"),
            "targetBaseDefinitionId": item.get("targetBaseDefinitionId"),
            "inspectionRequestPath": str(request_path),
            "inspectionRequestDigest": binding["requestDigest"],
            "savedStatePath": str(state_path),
        }
        if not state_path.is_file():
            row.update({
                "status": "pending_saved_output_inspection",
                "candidateReady": False,
                "readOnlyInspectionCommand": binding["command"],
                "candidatePayload": None,
            })
        else:
            payload = build_wastecup_station_candidate(
                root,
                mapping_config_path=mapping_config_path,
                mapping_report_path=mapping_report_path,
                inspection_request_path=request_path,
                saved_state_path=state_path,
                source_module_definition_id=item["sourceModuleDefinitionId"],
                target_base_definition_id=item["targetBaseDefinitionId"],
            )
            row.update({
                "status": "review_candidate_ready_requires_fresh_nonprototype_cad",
                "candidateReady": True,
                "readOnlyInspectionCommand": None,
                "candidatePayload": payload,
            })
        rows.append(row)
    result: dict[str, Any] = {
        "schemaVersion": "wastecup-station-candidate-batch/v1",
        "rows": rows,
        "summary": {
            "pairCount": len(rows),
            "pendingSavedOutputInspectionCount": sum(
                row["status"] == "pending_saved_output_inspection" for row in rows
            ),
            "candidateReadyCount": sum(row["candidateReady"] for row in rows),
        },
        "cadStarted": False,
        "relationPublished": False,
        "timing": {
            "startedAtUtc": started_at,
            "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
            "planningSeconds": perf_counter() - clock,
            "cadExecutionSeconds": 0.0,
            "saveReopenSeconds": 0.0,
            "stationPostcheckSeconds": 0.0,
        },
        "evidence": [
            {"path": str(path), "sha256": _sha(path)}
            for path in (
                mapping_config_path,
                mapping_report_path,
                inspection_batch_path,
            )
        ],
        "claimBoundary": (
            "Batch preparation or candidate derivation only. No CAD operation, "
            "station validation, relation publication, fastening, dispensing or "
            "collision/B-rep claim is made."
        ),
    }
    result["candidateDigest"] = _canonical_digest(result)
    return result

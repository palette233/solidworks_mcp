"""Bind scanner and barcode module-local points to one saved CAD context.

This is a thin adapter for scanner evidence that is recorded as two module-local
points instead of the older transport-lane process report.  It never places a
component, opens CAD, or upgrades a geometric proxy to measured scan success.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any


RULE_SCHEMA = "scanner-local-point-pair-rule/v1"
REPORT_SCHEMA = "scanner-current-context-point-pair-evaluation/v1"
CANDIDATE_SCHEMA = "scanner-cross-track-translation-candidate/v1"
PROFILE_SCHEMA = "scanner-local-point-pair-profile/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(value: Any) -> str:
    return str(value or "").replace("\\", "/").casefold()


def _vector(value: Any) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(item)
            for item in value
        )
    ):
        raise ValueError("Expected a finite three-number vector")
    return [float(item) for item in value]


def _transform(value: Any) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != 16
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(item)
            for item in value
        )
    ):
        raise ValueError("Expected a finite 16-number transform")
    result = [float(item) for item in value]
    axes = [result[index : index + 3] for index in (0, 3, 6)]
    for first_index, first in enumerate(axes):
        for second_index, second in enumerate(axes):
            expected = 1.0 if first_index == second_index else 0.0
            if abs(sum(a * b for a, b in zip(first, second, strict=True)) - expected) > 1e-6:
                raise ValueError("Transform rotation must be orthonormal")
    first, second, third = axes
    determinant = (
        first[0] * (second[1] * third[2] - second[2] * third[1])
        - first[1] * (second[0] * third[2] - second[2] * third[0])
        + first[2] * (second[0] * third[1] - second[1] * third[0])
    )
    if abs(determinant - 1.0) > 1e-6 or any(
        abs(a - b) > 1e-6
        for a, b in zip(result[12:16], [1.0, 0.0, 0.0, 0.0], strict=True)
    ):
        raise ValueError("Transform must be a proper rigid unit-scale transform")
    return result


def _point_to_world(point: list[float], transform: list[float]) -> list[float]:
    return [
        sum(point[index] * transform[3 * index + axis] for index in range(3))
        + transform[9 + axis]
        for axis in range(3)
    ]


def _reproject_direction(
    direction: list[float], reference: list[float], current: list[float]
) -> list[float]:
    local = [
        sum(direction[axis] * reference[3 * index + axis] for axis in range(3))
        for index in range(3)
    ]
    result = [
        sum(local[index] * current[3 * index + axis] for index in range(3))
        for axis in range(3)
    ]
    length = math.sqrt(sum(value * value for value in result))
    if length <= 1e-12:
        raise ValueError("Optical direction collapsed during reprojection")
    return [value / length for value in result]


def _component(
    components: list[dict[str, Any]], *, source_path: str, selector: str | None
) -> dict[str, Any]:
    matches = [
        row
        for row in components
        if isinstance(row, dict) and _path(row.get("sourcePath")) == _path(source_path)
    ]
    if selector is not None:
        matches = [row for row in matches if row.get("name") == selector]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one saved component for {source_path}; observed {len(matches)}"
        )
    if not matches[0].get("name"):
        raise ValueError("Saved component has no stable instance name")
    return deepcopy(matches[0])


def _measurement_geometry(
    measurement: dict[str, Any], definitions: dict[str, str]
) -> dict[str, Any]:
    """Normalize legacy Project02 capture or a reusable cross-project profile."""

    if measurement.get("schemaVersion") == PROFILE_SCHEMA:
        source = measurement.get("sourceScanner") or {}
        target = measurement.get("targetTransport") or {}
        if source.get("moduleDefinitionId") != definitions["scanner"]:
            raise ValueError("Scanner profile identity does not match the rule")
        if target.get("moduleDefinitionId") != definitions["transport"]:
            raise ValueError("Transport profile identity does not match the rule")
        if source.get("coarseLayoutUsable") is not True:
            raise ValueError("Scanner optical profile is not approved for coarse geometry")
        target_kind = str(target.get("targetKind") or "")
        if target_kind not in {"direct_cad_face", "barcode_lane_proxy_at_scan_station"}:
            raise ValueError("Unsupported transport barcode target evidence")
        return {
            "scannerReference": _transform(source.get("referenceTransform")),
            "transportReference": _transform(target.get("referenceTransform")),
            "scannerLocal": _vector(source.get("localOpticalOriginMeters")),
            "barcodeLocal": _vector(target.get("localBarcodeTargetMeters")),
            "scannerDirectionWorld": _vector(source.get("opticalDirectionWorld")),
            "targetEvidenceKind": target_kind,
            "targetEngineeringConfirmed": target.get("engineeringConfirmed") is True,
        }
    if measurement.get("schemaVersion") != "project02-scanner-barcode-points/v1":
        raise ValueError("Unsupported scanner point-pair measurement")
    scanner_entry = (measurement.get("entries") or {}).get("scanner") or {}
    barcode_entry = (measurement.get("entries") or {}).get("barcode") or {}
    if scanner_entry.get("moduleCode") != definitions["scanner"].split("::", 1)[1]:
        raise ValueError("Scanner measurement identity does not match the rule")
    if barcode_entry.get("moduleCode") != definitions["transport"].split("::", 1)[1]:
        raise ValueError("Barcode measurement identity does not match the transport rule")
    scanner_audit = scanner_entry.get("transformAudit") or {}
    barcode_audit = barcode_entry.get("transformAudit") or {}
    if scanner_entry.get("readyForCoarseLayout") is not True:
        raise ValueError("Scanner optical proxy is not approved for coarse geometry")
    if barcode_entry.get("measurementStatus") != "direct-face-measured":
        raise ValueError("Barcode target must be a directly measured CAD face")
    if not barcode_entry.get("persistentReferenceBase64"):
        raise ValueError("Barcode target has no persistent face reference")
    return {
        "scannerReference": _transform(scanner_audit.get("prototypeModuleTransform")),
        "transportReference": _transform(barcode_audit.get("prototypeModuleTransform")),
        "scannerLocal": _vector(scanner_audit.get("componentLocalOpticalOriginMeters")),
        "barcodeLocal": _vector(barcode_audit.get("componentLocalBarcodeCenterMeters")),
        "scannerDirectionWorld": _vector(scanner_entry.get("worldNormal")),
        "targetEvidenceKind": "direct_cad_face",
        "targetEngineeringConfirmed": True,
    }


def evaluate_scanner_point_pair_in_saved_context(
    *,
    rule: dict[str, Any],
    measurement: dict[str, Any],
    saved_state: dict[str, Any],
    state_path: str,
    state_sha256: str,
    assembly_sha256: str,
    instance_selectors: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Reproject one authenticated point pair into a saved cumulative state."""

    if rule.get("schemaVersion") != RULE_SCHEMA or not rule.get("ruleId"):
        raise ValueError("Unsupported or unnamed scanner point-pair rule")
    definitions = {
        "scanner": rule.get("sourceModuleDefinitionId"),
        "transport": rule.get("transportModuleDefinitionId"),
        "targetBase": rule.get("targetBaseDefinitionId"),
    }
    if any(
        not isinstance(value, str) or "::" not in value
        for value in definitions.values()
    ) or len(set(definitions.values())) != 3:
        raise ValueError("Scanner, transport and base definition identities are required")
    observed = saved_state.get("observed") or {}
    if saved_state.get("success") is not True or observed.get("readOnly") is not True:
        raise ValueError("A successful read-only saved CAD state is required")
    if not state_path or not state_sha256 or not assembly_sha256:
        raise ValueError("Saved-state and assembly evidence identities are required")
    if saved_state.get("assemblySha256") != assembly_sha256:
        raise ValueError("Saved-state assembly digest does not match current assembly")

    components = observed.get("components") or []
    paths = rule.get("componentSourcePaths") or {}
    if any(not str(paths.get(role) or "").strip() for role in definitions):
        raise ValueError("Exact scanner, transport and base source paths are required")
    if len({_path(paths[role]) for role in definitions}) != 3:
        raise ValueError("Scanner, transport and base source paths must be distinct")
    selectors = dict(rule.get("instanceSelectors") or {})
    if instance_selectors is not None:
        unknown = set(instance_selectors) - {"scanner", "transport", "targetBase"}
        if unknown:
            raise ValueError("Unsupported scanner point-pair instance selector")
        selectors.update(instance_selectors)
    scanner = _component(
        components,
        source_path=str(paths.get("scanner") or ""),
        selector=selectors.get("scanner"),
    )
    transport = _component(
        components,
        source_path=str(paths.get("transport") or ""),
        selector=selectors.get("transport"),
    )
    base = _component(
        components,
        source_path=str(paths.get("targetBase") or ""),
        selector=selectors.get("targetBase"),
    )
    if len({scanner["name"], transport["name"], base["name"]}) != 3:
        raise ValueError("Scanner, transport and base instances must be distinct")

    measurement_geometry = _measurement_geometry(measurement, definitions)
    scanner_reference = measurement_geometry["scannerReference"]
    transport_reference = measurement_geometry["transportReference"]
    scanner_current = _transform(scanner.get("transform"))
    transport_current = _transform(transport.get("transform"))
    base_current = _transform(base.get("transform"))
    scanner_local = measurement_geometry["scannerLocal"]
    barcode_local = measurement_geometry["barcodeLocal"]
    origin = _point_to_world(scanner_local, scanner_current)
    target = _point_to_world(barcode_local, transport_current)
    direction = _reproject_direction(
        measurement_geometry["scannerDirectionWorld"], scanner_reference, scanner_current
    )
    delta = [target[index] - origin[index] for index in range(3)]
    if sum(delta[index] * direction[index] for index in range(3)) < 0:
        direction = [-value for value in direction]
    distance = sum(delta[index] * direction[index] for index in range(3))
    cross_track = math.sqrt(
        sum(
            (delta[index] - distance * direction[index]) ** 2
            for index in range(3)
        )
    )
    range_evidence = deepcopy(rule.get("workingDistanceRangeEvidence") or {})
    minimum = range_evidence.get("minimumMeters")
    maximum = range_evidence.get("maximumMeters")
    if (
        not isinstance(minimum, (int, float))
        or isinstance(minimum, bool)
        or not isinstance(maximum, (int, float))
        or isinstance(maximum, bool)
        or not math.isfinite(minimum)
        or not math.isfinite(maximum)
        or not 0 <= minimum < maximum
        or not range_evidence.get("authority")
        or not range_evidence.get("sourceUrl")
    ):
        raise ValueError("Working-distance range evidence is incomplete")
    tolerance = rule.get("crossTrackToleranceMeters")
    if (
        not isinstance(tolerance, (int, float))
        or isinstance(tolerance, bool)
        or not math.isfinite(tolerance)
        or tolerance <= 0
    ):
        raise ValueError("Cross-track tolerance must be finite and positive")
    distance_passed = minimum <= distance <= maximum
    cross_track_passed = cross_track <= tolerance
    proxy_passed = distance_passed and cross_track_passed
    core = {
        "schemaVersion": REPORT_SCHEMA,
        "ruleId": rule["ruleId"],
        "ruleDigest": _digest(rule),
        "status": (
            "current_context_point_pair_proxy_passed"
            if proxy_passed
            else "current_context_point_pair_geometry_mismatch"
        ),
        "definitions": definitions,
        "instances": {
            "scanner": scanner["name"],
            "transport": transport["name"],
            "targetBase": base["name"],
        },
        "currentTransforms": {
            "scanner": scanner_current,
            "transport": transport_current,
            "targetBase": base_current,
        },
        "geometry": {
            "opticalOriginWorldMeters": origin,
            "barcodeTargetWorldMeters": target,
            "opticalDirectionWorld": direction,
            "axisSignResolvedTowardCurrentTargetProxy": True,
            "axisSignEngineeringConfirmed": False,
            "requiredWorkingDistanceMeters": distance,
            "crossTrackErrorMeters": cross_track,
            "crossTrackToleranceMeters": float(tolerance),
            "workingDistanceRangeEvidence": range_evidence,
            "workingDistancePassed": distance_passed,
            "crossTrackPassed": cross_track_passed,
        },
        "targetAssociationBound": True,
        "targetEvidenceKind": measurement_geometry["targetEvidenceKind"],
        "targetEngineeringConfirmed": measurement_geometry[
            "targetEngineeringConfirmed"
        ],
        "processProxyValidationPassed": proxy_passed,
        "mechanicalPlacementChanged": False,
        "cadExecuted": False,
        "measuredScanSuccess": False,
        "evidence": {
            "statePath": state_path,
            "stateSha256": state_sha256,
            "assemblyPath": saved_state.get("assemblyPath"),
            "assemblySha256": assembly_sha256,
            "measurementDigest": _digest(measurement),
        },
        "blockingReasonCodes": [
            *([] if distance_passed else ["WORKING_DISTANCE_OUTSIDE_RECORDED_RANGE"]),
            *([] if cross_track_passed else ["OPTICAL_AXIS_MISSES_CURRENT_BARCODE_TARGET_PROXY"]),
        ],
        "boundary": (
            "The saved scanner, selected transport and base instances are bound and the "
            "recorded module-local points are recomputed in their current poses. This is "
            "a coarse geometric proxy only; no CAD mutation, field-of-view, obstruction, "
            "trigger, code-size or measured scan validation is claimed."
        ),
    }
    return {**core, "evaluationDigest": _digest(core)}


def build_scanner_point_pair_report(
    *, rule_path: Path, measurement_path: Path, state_path: Path
) -> dict[str, Any]:
    rule_path = rule_path.resolve()
    measurement_path = measurement_path.resolve()
    state_path = state_path.resolve()
    rule = json.loads(rule_path.read_text(encoding="utf-8-sig"))
    measurement = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    saved_state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    expected = rule.get("inputSha256") or {}
    measurement_sha = _file_hash(measurement_path)
    if expected.get("measurementPath") != measurement_sha:
        raise ValueError("Scanner point-pair measurement hash changed")
    assembly_path = Path(saved_state.get("assemblyPath") or "").resolve()
    if not assembly_path.is_file():
        raise ValueError("Saved-state assembly is missing")
    assembly_sha = _file_hash(assembly_path)
    return evaluate_scanner_point_pair_in_saved_context(
        rule=rule,
        measurement=measurement,
        saved_state=saved_state,
        state_path=str(state_path),
        state_sha256=_file_hash(state_path),
        assembly_sha256=assembly_sha,
    )


def derive_scanner_cross_track_translation_candidate(
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Derive the smallest translation that removes current cross-track error.

    The result is only a functional placement candidate.  It deliberately does
    not claim that an existing mechanical interface can realize the movement.
    """

    if evaluation.get("schemaVersion") != REPORT_SCHEMA:
        raise ValueError("Unsupported scanner current-context evaluation")
    core = {
        key: value for key, value in evaluation.items() if key != "evaluationDigest"
    }
    if _digest(core) != evaluation.get("evaluationDigest"):
        raise ValueError("Scanner current-context evaluation digest mismatch")
    if evaluation.get("targetAssociationBound") is not True:
        raise ValueError("Scanner target association is not bound")
    geometry = evaluation.get("geometry") or {}
    origin = _vector(geometry.get("opticalOriginWorldMeters"))
    target = _vector(geometry.get("barcodeTargetWorldMeters"))
    direction = _vector(geometry.get("opticalDirectionWorld"))
    base = _transform(
        (evaluation.get("currentTransforms") or {}).get("targetBase")
    )
    delta = [target[index] - origin[index] for index in range(3)]
    distance = sum(delta[index] * direction[index] for index in range(3))
    correction_world = [
        delta[index] - distance * direction[index] for index in range(3)
    ]
    magnitude = math.sqrt(sum(value * value for value in correction_world))
    if magnitude <= 1e-12:
        raise ValueError("Scanner point pair has no cross-track translation gap")
    correction_base = [
        sum(correction_world[axis] * base[3 * row + axis] for axis in range(3))
        for row in range(3)
    ]
    shifted_origin = [
        origin[index] + correction_world[index] for index in range(3)
    ]
    shifted_delta = [
        target[index] - shifted_origin[index] for index in range(3)
    ]
    shifted_distance = sum(
        shifted_delta[index] * direction[index] for index in range(3)
    )
    predicted_cross_track = math.sqrt(
        sum(
            (
                shifted_delta[index]
                - shifted_distance * direction[index]
            )
            ** 2
            for index in range(3)
        )
    )
    candidate_core = {
        "schemaVersion": CANDIDATE_SCHEMA,
        "status": "candidate_requires_mechanical_interface_review",
        "definitions": deepcopy(evaluation.get("definitions") or {}),
        "instances": deepcopy(evaluation.get("instances") or {}),
        "sourceEvaluationDigest": evaluation["evaluationDigest"],
        "recommendedScannerTranslationDeltaWorldMeters": correction_world,
        "recommendedScannerTranslationDeltaInTargetBaseMeters": correction_base,
        "translationMagnitudeMeters": magnitude,
        "preservedRequiredWorkingDistanceMeters": distance,
        "predictedCrossTrackErrorMeters": predicted_cross_track,
        "candidateRequiresNewMechanicalInterfaceOrParameterizedDatum": True,
        "cadLaunchAllowed": False,
        "prototypePoseAllowedAsExecutionAuthority": False,
        "nextAction": (
            "find_an_authorized_alternate_slot_or_parameterized_datum_that_realizes_"
            "the_translation_then_run_fresh_nonprototype_CAD_save_reopen_and_station_postcheck"
        ),
        "boundary": (
            "Smallest point-pair cross-track correction only. It does not prove that "
            "the current mount can translate, that a backup slot exists, or that CAD, "
            "field scan, collision, fastening or production requirements pass."
        ),
    }
    return {**candidate_core, "candidateDigest": _digest(candidate_core)}

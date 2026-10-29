"""Read-only scanner/transport target bindings and cumulative-chain preflight.

Prototype measurements may justify an explicitly authorized geometric proxy,
never a measured barcode surface, a CAD closure, or a functional scan success.
No function in this module creates mates, chooses positions, or launches CAD.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any


SCHEMA = "scanner-target-association/v1"
PREFLIGHT_SCHEMA = "scanner-target-association-chain-preflight/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _valid_digest(value: dict, field: str) -> bool:
    try:
        return value.get(field) == _digest({k: v for k, v in value.items() if k != field})
    except (TypeError, ValueError):
        return False


def _numbers(value: Any, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        for v in value
    )


def _near(first: Any, second: Any, length: int, tolerance: float = 1e-9) -> bool:
    return _numbers(first, length) and _numbers(second, length) and all(
        abs(a - b) <= tolerance for a, b in zip(first, second, strict=True)
    )


def _path(value: Any) -> str:
    return str(value or "").replace("\\", "/").casefold()


def _module(graph: dict, token: str) -> dict:
    # Full CAD part-number tokens are allowed, but a substring such as AI001
    # must not select AI00; multiple instances require an explicit new binding.
    rows = [r for r in graph.get("Modules") or []
            if str(r.get("ModuleToken") or "").upper().endswith(token.upper())]
    return rows[0] if len(rows) == 1 else {}


def build_scanner_target_association(
    *, prior_process_evidence: dict, scanner_graph: dict,
    target_transport_graph: dict, target_face_catalog: dict,
    scanner_module_token: str = "AI00", transport_module_token: str = "SS00",
    target_base_module_token: str = "JJ00",
    prototype_estimate_authorized: bool = False,
    scanner_optical_evidence: dict | None = None,
) -> dict:
    """Bind legacy measurements to exact instances without upgrading their grade.

The legacy lane is in the installed transport frame. Reusing it in another
world frame is accepted only when source/installed transport transforms and
the target face-catalog source assembly agree. Otherwise an explicit measured
frame bridge is still missing; this builder does not invent one.
"""
    scanner = prior_process_evidence.get("sourceScanner") or {}
    transport = prior_process_evidence.get("targetTransport") or {}
    lane = transport.get("barcodeLaneReference") or {}
    distance = (prior_process_evidence.get("readOnlyChecks") or {}).get(
        "workingDistanceRangeEvidence") or {}
    source_instance = _module(scanner_graph, scanner_module_token)
    transport_instance = _module(target_transport_graph, transport_module_token)
    base_instance = _module(target_transport_graph, target_base_module_token)
    optical = scanner_optical_evidence if scanner_optical_evidence is not None else (
        (scanner_graph.get("SemanticAssemblyPlanAudit") or {}).get("opticalValidation") or {})
    blockers: list[str] = []
    if prototype_estimate_authorized is not True:
        blockers.append("PROTOTYPE_ESTIMATE_NOT_AUTHORIZED")
    if not source_instance.get("HierarchyPath") or scanner.get("moduleToken") != scanner_module_token:
        blockers.append("SCANNER_INSTANCE_NOT_UNIQUE")
    if not transport_instance.get("HierarchyPath") or transport.get("moduleToken") != transport_module_token:
        blockers.append("TRANSPORT_INSTANCE_NOT_UNIQUE")
    if not base_instance.get("HierarchyPath"):
        blockers.append("TARGET_BASE_INSTANCE_NOT_UNIQUE")
    if not scanner.get("projectId") or not transport.get("projectId"):
        blockers.append("MODULE_DEFINITION_IDENTITY_MISSING")
    source_frame = scanner_graph.get("SourceAssemblyPath")
    target_frame = target_transport_graph.get("SourceAssemblyPath")
    target_frame_agrees = bool(target_frame) and _path(target_frame) == _path(
        target_face_catalog.get("SourceAssemblyPath"))
    transform_agrees = _near(transport_instance.get("SourceTransform"),
                            transport.get("installedTransform"), 16) and _near(
        transport.get("sourceTransform"), transport.get("installedTransform"), 16)
    if not source_frame or not target_frame_agrees or not transform_agrees:
        blockers.append("TARGET_COORDINATE_FRAME_BRIDGE_UNPROVEN")

    frame = transport.get("installationFrameWorld") or {}
    axes = [frame.get(k) for k in ("flowAxis", "transverseAxis", "upAxis")]
    frame_valid = _numbers(frame.get("origin"), 3) and all(_numbers(a, 3) for a in axes)
    if frame_valid:
        frame_valid = all(abs(sum(v*v for v in a) - 1) <= 1e-6 for a in axes) and all(
            abs(sum(a*b for a, b in zip(axes[i], axes[j], strict=True))) <= 1e-6
            for i, j in ((0, 1), (0, 2), (1, 2)))
    if not frame_valid:
        blockers.append("TRANSPORT_INSTALLATION_FRAME_INVALID")

    origin, direction, endpoint = (scanner.get(k) for k in (
        "opticalOriginWorldMeters", "opticalDirectionWorld", "cadBeamEndpointProxyWorldMeters"))
    nominal = optical.get("modeledWorkingDistanceMeters")
    sign_known = _numbers(origin, 3) and _numbers(direction, 3) and _numbers(endpoint, 3)
    sign_known = sign_known and isinstance(nominal, (int, float)) and not isinstance(nominal, bool) and math.isfinite(nominal) and nominal > 0
    if sign_known:
        sign_known = _near(direction, optical.get("opticalDirectionWorld"), 3) and _near(
            endpoint, optical.get("targetProxyWorldMeters"), 3) and _near(
            [a + nominal*b for a, b in zip(origin, direction, strict=True)], endpoint, 3)
        sign_known = sign_known and abs(sum(v*v for v in direction) - 1) <= 1e-6
    if not sign_known:
        blockers.append("OPTICAL_AXIS_SIGN_EVIDENCE_MISSING_OR_INCONSISTENT")
    lane_valid = all(isinstance(lane.get(k), (int, float)) and not isinstance(lane.get(k), bool)
                     and math.isfinite(lane[k]) for k in (
                         "transverseCoordinateMeters", "normalCoordinateMeters"))
    if not lane_valid or not lane.get("source"):
        blockers.append("WORKPIECE_BARCODE_TARGET_PROXY_MISSING")
    interval = transport.get("conservativeFlowEnvelopeMeters")
    if not _numbers(interval, 2) or interval[0] >= interval[1]:
        blockers.append("TRANSPORT_FLOW_ENVELOPE_INVALID")
    bounds = [distance.get("minimumMeters"), distance.get("maximumMeters")]
    if not _numbers(bounds, 2) or not 0 <= bounds[0] < bounds[1] or not distance.get("authority") or not distance.get("sourceUrl"):
        blockers.append("WORKING_DISTANCE_RANGE_EVIDENCE_MISSING")

    # Even a legacy true flag cannot manufacture a physical face identifier.
    core = {
        "schemaVersion": SCHEMA,
        "status": "prototype_proxy_associated" if not blockers else "blocked_missing_target_association_evidence",
        "scanner": {"moduleDefinitionId": f"{scanner.get('projectId')}::{scanner_module_token}",
                    "instanceId": source_instance.get("HierarchyPath"),
                    "sourceWorldFrameId": source_frame},
        "transport": {"moduleDefinitionId": f"{transport.get('projectId')}::{transport_module_token}",
                      "instanceId": transport_instance.get("HierarchyPath"),
                      "installedTransform": deepcopy(transport.get("installedTransform"))},
        "targetBase": {"moduleDefinitionId": f"{transport.get('projectId')}::{target_base_module_token}",
                       "instanceId": base_instance.get("HierarchyPath"),
                       "installedTransform": deepcopy(base_instance.get("SourceTransform"))},
        "coordinateFrame": {"worldFrameId": target_frame,
                            "frameId": "transport_installation_frame",
                            "installationFrameWorld": deepcopy(frame),
                            "bridgeVerifiedBySourceIdentityAndTransform": target_frame_agrees and transform_agrees},
        "opticalRay": {"originWorldMeters": deepcopy(origin), "directionWorld": deepcopy(direction),
                       "axisSignKnown": bool(sign_known), "axisSignEngineeringConfirmed": False,
                       "axisSignAuthority": "prototype_cad_origin_to_beam_endpoint" if sign_known else None},
        "workpieceTarget": {"targetId": f"{transport.get('projectId')}::{transport_module_token}::barcode-lane-proxy",
                            "ownerTransportInstanceId": transport_instance.get("HierarchyPath"),
                            "coordinateFrameId": "transport_installation_frame",
                            "geometryKind": "moving_barcode_lane_proxy", "workpieceInstanceId": None,
                            "physicalBarcodeFaceId": None, "reference": deepcopy(lane),
                            "flowEnvelopeMeters": deepcopy(interval),
                            "engineeringConfirmedBarcodeSurface": False},
        "workingDistanceRangeEvidence": deepcopy(distance),
        "evidenceGrade": "prototype_measured_proxy",
        "prototypeEstimateAuthorized": prototype_estimate_authorized is True,
        "sourceProcessEvidenceDigest": _digest(prior_process_evidence),
        "sourceInputDigests": {"scannerGraph": _digest(scanner_graph),
                              "targetTransportGraph": _digest(target_transport_graph),
                              "targetFaceCatalog": _digest(target_face_catalog),
                              **({"scannerOpticalEvidence": _digest(optical)} if scanner_optical_evidence is not None else {})},
        "coarseGeometryEvaluationReady": not blockers,
        "blockingReasonCodes": blockers,
        "engineeringEvidenceMissing": ["real_workpiece_barcode_surface", "field_optical_axis_sign_confirmation",
                                       "code_size_and_field_of_view", "line_of_sight", "carrier_stop_or_trigger_evidence"],
        "cadEvidence": {"performed": False, "nonPrototypeMateClosurePassed": None,
                        "savedReopened": None},
        "engineeringProcessValidationPassed": False, "measuredScanSuccess": False,
        "cadLaunchAllowed": False, "drivesMechanicalPlacement": False,
    }
    return {**core, "associationDigest": _digest(core)}


def validate_scanner_target_association(association: dict | None, *, prior_process_evidence: dict | None = None) -> list[str]:
    """Return stable blockers, including stale geometry and altered associations."""
    if not association:
        return ["SCANNER_TARGET_ASSOCIATION_REQUIRED"]
    blockers = list(association.get("blockingReasonCodes") or [])
    if association.get("schemaVersion") != SCHEMA or not _valid_digest(association, "associationDigest"):
        blockers.append("SCANNER_TARGET_ASSOCIATION_DIGEST_INVALID")
    if prior_process_evidence is not None and association.get("sourceProcessEvidenceDigest") != _digest(prior_process_evidence):
        blockers.append("SCANNER_TARGET_PROCESS_EVIDENCE_STALE")
    if association.get("coarseGeometryEvaluationReady") is not True:
        blockers.append("SCANNER_TARGET_ASSOCIATION_NOT_READY")
    if any(not (association.get(role) or {}).get("instanceId") or not (
        association.get(role) or {}).get("moduleDefinitionId")
           for role in ("scanner", "transport", "targetBase")):
        blockers.append("SCANNER_TARGET_INSTANCE_IDENTITY_MISSING")
    frame = association.get("coordinateFrame") or {}
    target = association.get("workpieceTarget") or {}
    if not frame.get("worldFrameId") or not (frame.get("bridgeVerifiedBySourceIdentityAndTransform") is True or frame.get("bridgeVerifiedByRigidModuleReprojection") is True):
        blockers.append("TARGET_COORDINATE_FRAME_BRIDGE_UNPROVEN")
    if (association.get("opticalRay") or {}).get("axisSignKnown") is not True:
        blockers.append("OPTICAL_AXIS_SIGN_EVIDENCE_MISSING_OR_INCONSISTENT")
    if not target.get("targetId") or target.get("ownerTransportInstanceId") != (
        association.get("transport") or {}).get("instanceId") or target.get("coordinateFrameId") != frame.get("frameId"):
        blockers.append("WORKPIECE_TARGET_OWNER_OR_FRAME_MISMATCH")
    if association.get("evidenceGrade") != "prototype_measured_proxy" or association.get("prototypeEstimateAuthorized") is not True:
        blockers.append("PROTOTYPE_PROXY_EVIDENCE_GRADE_OR_AUTHORIZATION_INVALID")
    return sorted(set(blockers))


def preflight_scanner_target_for_cumulative_chain(
    *, evaluation: dict, association: dict | None, planned_components: list[dict],
    world_frame_id: str, allow_prototype_proxy: bool = False,
) -> dict:
    """Independent, offline entry point before compiling a cumulative chain.

planned_components carry exact instanceId, moduleDefinitionId and transform.
Passing only authorizes a process-candidate compile; mechanical release/CAD
authorization remains a separate gate. No historical CAD success is inferred.
"""
    blockers = validate_scanner_target_association(association)
    association = association or {}
    if not _valid_digest(evaluation, "evaluationDigest"):
        blockers.append("SCANNER_EVALUATION_DIGEST_INVALID")
    if evaluation.get("targetAssociationDigest") != association.get("associationDigest"):
        blockers.append("SCANNER_EVALUATION_ASSOCIATION_MISMATCH")
    if evaluation.get("candidatePoseTransformSolved") is not True and not (
        evaluation.get("schemaVersion") == "scanner-current-context-process-evaluation/v1"
        and evaluation.get("currentContextPoseBound") is True
    ):
        blockers.append("SCANNER_MECHANICAL_CANDIDATE_NOT_SOLVED")
    if (evaluation.get("targetAssociationCheck") or {}).get("passed") is not True:
        blockers.append("SCANNER_EVALUATION_TARGET_ASSOCIATION_NOT_VALIDATED")
    if evaluation.get("processProxyValidationPassed") is not True:
        blockers.append("SCANNER_TARGET_GEOMETRY_FAILED")
    if _path(world_frame_id) != _path((association.get("coordinateFrame") or {}).get("worldFrameId")) or not world_frame_id:
        blockers.append("SCANNER_TARGET_WORLD_FRAME_MISMATCH")
    for role in ("scanner", "transport", "targetBase"):
        binding = association.get(role) or {}
        rows = [r for r in planned_components if r.get("instanceId") == binding.get("instanceId")]
        if len(rows) != 1 or rows[0].get("moduleDefinitionId") != binding.get("moduleDefinitionId"):
            blockers.append(f"SCANNER_{role.upper()}_INSTANCE_BINDING_MISMATCH")
            continue
        expected = binding.get("installedTransform") if role != "scanner" else (
            evaluation.get("selectedCandidate") or {}).get("candidateTransform")
        if not _near(rows[0].get("transform"), expected, 16):
            blockers.append(f"SCANNER_{role.upper()}_POSE_CHANGED_REEVALUATION_REQUIRED")
        if binding.get("sourcePath") and _path(rows[0].get("sourcePath")) != _path(binding["sourcePath"]):
            blockers.append(f"SCANNER_{role.upper()}_SOURCE_CHANGED_REEVALUATION_REQUIRED")
        if "configuration" in binding and rows[0].get("configuration") != binding["configuration"]:
            blockers.append(f"SCANNER_{role.upper()}_CONFIGURATION_CHANGED_REEVALUATION_REQUIRED")
    if association.get("evidenceGrade") == "prototype_measured_proxy" and allow_prototype_proxy is not True:
        blockers.append("SCANNER_PROXY_REQUIRES_EXPLICIT_DEMO_MODE")
    blockers = sorted(set(blockers))
    core = {"schemaVersion": PREFLIGHT_SCHEMA,
            "status": "proxy_process_candidate_compile_allowed" if not blockers else "blocked_before_chain_compile",
            "processCandidateCompileAllowed": not blockers,
            "blockingReasonCodes": blockers,
            "associationDigest": association.get("associationDigest"),
            "evaluationDigest": evaluation.get("evaluationDigest"),
            "plannedComponentsDigest": _digest(planned_components),
            "evidenceGrade": association.get("evidenceGrade"),
            "engineeringProcessValidationPassed": False, "measuredScanSuccess": False,
            "cadLaunchAllowed": False, "mechanicalReleaseCheckRequired": True}
    return {**core, "preflightDigest": _digest(core)}


def _proper_transform(value: Any) -> list[float]:
    if not _numbers(value, 16):
        raise ValueError("Expected a finite 16-number module transform")
    axes = [value[i:i+3] for i in (0, 3, 6)]
    if any(abs(sum(x*y for x, y in zip(a, b, strict=True)) - (i == j)) > 1e-6
           for i, a in enumerate(axes) for j, b in enumerate(axes)):
        raise ValueError("Module transform must be orthonormal")
    a, b, c = axes
    determinant = a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    if abs(determinant-1) > 1e-6 or not _near(value[12:16], [1, 0, 0, 0], 4, 1e-6):
        raise ValueError("Module transform must be proper rigid unit-scale")
    return [float(v) for v in value]


def _reproject(vector: list, reference: list, current: list, *, direction: bool = False) -> list:
    if not _numbers(vector, 3):
        raise ValueError("Expected a finite point or direction")
    relative = vector if direction else [vector[i]-reference[9+i] for i in range(3)]
    local = [sum(relative[j]*reference[3*i+j] for j in range(3)) for i in range(3)]
    return [sum(local[i]*current[3*i+j] for i in range(3)) + (0 if direction else current[9+j])
            for j in range(3)]


def bind_scanner_target_to_current_context(
    *, reference_association: dict, scanner_reference_graph: dict,
    current_components: list[dict], selection: dict[str, str],
    world_frame_id: str, context_evidence: dict,
) -> dict:
    """Reproject scanner ray and transport lane independently into current poses.

The caller supplies an exact role-to-instance selection and current poses.
Source optical geometry remains a tagged prototype proxy. This is a geometry
measurement, not an instruction to place a component at a reference pose.
"""
    blockers = validate_scanner_target_association(reference_association)
    if blockers:
        raise ValueError(f"Reference association is not usable: {blockers}")
    if reference_association["sourceInputDigests"]["scannerGraph"] != _digest(scanner_reference_graph):
        raise ValueError("Scanner reference graph changed")
    if not world_frame_id or not context_evidence.get("sourcePath") or not context_evidence.get("sourceSha256"):
        raise ValueError("Current pose context requires explicit frame and evidence identity")
    if context_evidence.get("kind") not in {"read_only_saved_cad_state", "explicit_planned_context"}:
        raise ValueError("Unknown current pose evidence grade")
    roles = {}
    for role in ("scanner", "transport", "targetBase"):
        instance = selection.get(role)
        rows = [r for r in current_components if r.get("instanceId") == instance]
        if not instance or len(rows) != 1 or not rows[0].get("moduleDefinitionId"):
            raise ValueError(f"Expected unique current {role} instance")
        roles[role] = deepcopy(rows[0])
        roles[role]["transform"] = _proper_transform(rows[0].get("transform"))
        if role != "targetBase" and roles[role]["moduleDefinitionId"] != reference_association[role]["moduleDefinitionId"]:
            raise ValueError(f"Different {role} module needs its own process geometry")
    if len(set(selection.values())) != 3:
        raise ValueError("Scanner, transport and base must be distinct instances")
    scanner_reference = [r for r in scanner_reference_graph.get("Modules") or []
                         if r.get("HierarchyPath") == reference_association["scanner"]["instanceId"]]
    if len(scanner_reference) != 1:
        raise ValueError("Reference scanner instance does not resolve uniquely")
    scanner_t = _proper_transform(scanner_reference[0].get("SourceTransform"))
    transport_t = _proper_transform(reference_association["transport"].get("installedTransform"))
    current = deepcopy(reference_association)
    current.pop("associationDigest", None)
    current["status"] = "prototype_proxy_associated_to_current_context"
    current["referenceAssociationDigest"] = reference_association["associationDigest"]
    current["currentContextEvidence"] = deepcopy(context_evidence)
    current["currentComponentsDigest"] = _digest(current_components)
    for role, component in roles.items():
        current[role] = {"moduleDefinitionId": component["moduleDefinitionId"],
                         "instanceId": component["instanceId"],
                         "installedTransform": component["transform"], "worldFrameId": world_frame_id,
                         **({"sourcePath": component["sourcePath"]} if component.get("sourcePath") else {}),
                         **({"configuration": component["configuration"]} if "configuration" in component else {})}
    reference_frame = reference_association["coordinateFrame"]["installationFrameWorld"]
    frame = {"origin": _reproject(reference_frame["origin"], transport_t, roles["transport"]["transform"])}
    for key in ("flowAxis", "transverseAxis", "upAxis"):
        frame[key] = _reproject(reference_frame[key], transport_t, roles["transport"]["transform"], direction=True)
    current["coordinateFrame"] = {
        "worldFrameId": world_frame_id, "frameId": "transport_installation_frame",
        "installationFrameWorld": frame, "bridgeKind": "independent_module_local_reprojection",
        "bridgeVerifiedBySourceIdentityAndTransform": False,
        "bridgeVerifiedByRigidModuleReprojection": True,
        "referenceTransportTransform": transport_t,
        "referenceScannerTransform": scanner_t,
    }
    ray = reference_association["opticalRay"]
    current["opticalRay"] = {**deepcopy(ray),
        "originWorldMeters": _reproject(ray["originWorldMeters"], scanner_t, roles["scanner"]["transform"]),
        "directionWorld": _reproject(ray["directionWorld"], scanner_t, roles["scanner"]["transform"], direction=True),
        "worldFrameId": world_frame_id,
    }
    current["workpieceTarget"]["ownerTransportInstanceId"] = roles["transport"]["instanceId"]
    current["cadEvidence"] = {"performed": False, "nonPrototypeMateClosurePassed": None,
                              "savedReopened": None,
                              "historicalObservedPoseUsed": context_evidence["kind"] == "read_only_saved_cad_state"}
    return {**current, "associationDigest": _digest(current)}


def evaluate_scanner_target_in_current_context(*, association: dict) -> dict:
    """Evaluate the current ray/lane geometry, never the historical pass flag."""
    # Reuse the bounded ray/line computation without invoking candidate search.
    from .cross_project_scanner_alternate_route import _closest_ray_to_line

    blockers = validate_scanner_target_association(association)
    if blockers or not association.get("currentContextEvidence"):
        raise ValueError(f"Current target association is incomplete: {blockers}")
    frame = association["coordinateFrame"]["installationFrameWorld"]
    target = association["workpieceTarget"]
    lane = target["reference"]
    lane_origin = [frame["origin"][i] + frame["transverseAxis"][i]*lane["transverseCoordinateMeters"]
                   + frame["upAxis"][i]*lane["normalCoordinateMeters"] for i in range(3)]
    ray = association["opticalRay"]
    distance, flow, error = _closest_ray_to_line(
        ray["originWorldMeters"], ray["directionWorld"], lane_origin, frame["flowAxis"])
    distance_range = association["workingDistanceRangeEvidence"]
    finite = all(math.isfinite(v) for v in (distance, flow, error))
    interval = target["flowEnvelopeMeters"]
    checks = {"requiredWorkingDistanceMeters": distance if finite else None,
              "transportFlowCoordinateMeters": flow if finite else None,
              "crossTrackErrorMeters": error if finite else None,
              "crossTrackToleranceMeters": 0.005,
              "workingDistanceRangeMeters": [distance_range["minimumMeters"], distance_range["maximumMeters"]],
              "axisPointsTowardBarcodeLane": finite and distance > 0,
              "stationInsideTransportEnvelope": finite and interval[0] <= flow <= interval[1],
              "workingDistancePassed": finite and distance_range["minimumMeters"] <= distance <= distance_range["maximumMeters"],
              "crossTrackPassed": finite and error <= 0.005}
    passed = all(checks[k] is True for k in ("axisPointsTowardBarcodeLane", "stationInsideTransportEnvelope",
                                           "workingDistancePassed", "crossTrackPassed"))
    checks["passed"] = passed
    core = {
        "schemaVersion": "scanner-current-context-process-evaluation/v1",
        "status": "current_context_proxy_geometry_passed" if passed else "blocked_current_context_proxy_geometry",
        "targetAssociationDigest": association["associationDigest"],
        "targetAssociationCheck": {"passed": True, "blockingReasonCodes": []},
        "currentContextPoseBound": True, "candidatePoseTransformSolved": False,
        "poseAuthority": association["currentContextEvidence"]["kind"],
        "selectedCandidate": {"candidateTransform": association["scanner"]["installedTransform"],
                              "processProxyChecks": checks},
        "processProxyValidationPassed": passed,
        "calculationEvidence": {"performed": True, "kind": "reprojected_current_pose_barcode_lane_proxy",
                                "historicalProcessPassFlagReused": False},
        "cadEvidence": {"performed": False, "nonPrototypeMateClosurePassed": None, "savedReopened": None},
        "engineeringProcessValidationPassed": False, "measuredScanSuccess": False,
        "cadLaunchAllowed": False, "mechanicalReleaseCheckRequired": True,
    }
    return {**core, "evaluationDigest": _digest(core)}

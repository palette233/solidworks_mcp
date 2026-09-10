from __future__ import annotations

import math
from copy import deepcopy
from typing import Any


GANTRY = "FL9A24D062A100.001-1"
TRANSPORT = "FL9A24D062A800.001-1"


class EngineeringInputError(ValueError):
    pass


def apply_confirmed_project02_engineering_inputs(
    request: dict[str, Any], inputs: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply only complete, explicitly confirmed engineering inputs.

    Unconfirmed sections remain inert.  This prevents a partially edited JSON
    template from silently replacing the current coarse assumptions.
    """

    updated = deepcopy(request)
    applied: list[str] = []
    skipped: list[str] = []
    semantics = updated.get("moduleSemantics") or {}

    transport_installation = inputs.get("transportInstallation") or {}
    transport_source_type = str(
        transport_installation.get("sourceType") or ""
    ).strip()
    transport_vendor_confirmed = bool(
        transport_installation.get("vendorConfirmed") is True
        or (
            transport_installation.get("confirmed") is True
            and transport_source_type != "prototypeBaseline"
        )
    )
    transport_prototype_baseline_accepted = bool(
        transport_source_type == "prototypeBaseline"
        and transport_installation.get("acceptedForCoarseLayout") is True
        and transport_installation.get("vendorConfirmed") is not True
        and str(transport_installation.get("scope") or "") == "project02-only"
    )
    if transport_vendor_confirmed and transport_source_type == "prototypeBaseline":
        raise EngineeringInputError(
            "transportInstallation prototypeBaseline cannot be marked vendorConfirmed"
        )
    if transport_vendor_confirmed or transport_prototype_baseline_accepted:
        frame_name = str(
            transport_installation.get("frameName") or "A600_INSTALLATION_FRAME"
        ).strip()
        if not frame_name:
            raise EngineeringInputError("transportInstallation.frameName is required")
        anchor_point = _vector3(
            transport_installation.get("a800AnchorPointFrameMeters"),
            "transportInstallation.a800AnchorPointFrameMeters",
        )
        source = str(
            transport_installation.get("source")
            or (
                "engineer-confirmed vendor datum"
                if transport_vendor_confirmed
                else "Project02 prototype baseline"
            )
        )
        anchor_scope = (
            "project02-vendor-interface"
            if transport_vendor_confirmed
            else "project02-only"
        )
        policy = updated.setdefault("sourceIndependentPolicy", {})
        policy.update(
            {
                "caseSpecificPrototypeAnchor": False,
                "caseAnchorEnabled": True,
                "caseAnchorComponentName": TRANSPORT,
                "caseAnchorTargetKind": "installationFramePoint",
                "caseAnchorTargetFrameName": frame_name,
                "caseAnchorTargetFrameMeters": anchor_point,
                "caseAnchorTargetSource": source,
                "caseAnchorTargetPrototypeDerived": not transport_vendor_confirmed,
                "caseAnchorScope": anchor_scope,
            }
        )
        sequence = updated.setdefault("assemblySequencePolicy", {})
        vendor = sequence.setdefault("vendorTransportInterface", {})
        vendor.update(
            {
                "confirmed": transport_vendor_confirmed,
                "xyzMeters": anchor_point if transport_vendor_confirmed else None,
                "project02PrototypePoseReuseConfirmed": False,
                "installationFrameAnchorAcceptedForCoarseLayout": True,
                "installationFrameAnchorPointMeters": anchor_point,
                "installationFrameAnchorPrototypeDerived": not transport_vendor_confirmed,
                "installationFrameAnchorSourceType": (
                    transport_source_type
                    or ("vendorDatum" if transport_vendor_confirmed else "prototypeBaseline")
                ),
                "installationFrameAnchorScope": anchor_scope,
                "evidence": source,
            }
        )
        applied.append("transportInstallation")
    else:
        skipped.append("transportInstallation")

    scan = inputs.get("dynamicScan") or {}
    scan_source_type = str(scan.get("sourceType") or "").strip()
    scan_vendor_confirmed = bool(
        scan.get("vendorConfirmed") is True
        or (
            scan.get("confirmed") is True
            and scan_source_type != "prototypeBaseline"
        )
    )
    scan_prototype_baseline_accepted = bool(
        scan_source_type == "prototypeBaseline"
        and scan.get("acceptedForCoarseLayout") is True
        and scan.get("vendorConfirmed") is not True
        and str(scan.get("scope") or "") == "project02-only"
    )
    if scan_vendor_confirmed and scan_source_type == "prototypeBaseline":
        raise EngineeringInputError(
            "dynamicScan prototypeBaseline cannot be marked vendorConfirmed"
        )
    if scan_vendor_confirmed or scan_prototype_baseline_accepted:
        tolerance = _positive(scan.get("stopToleranceMeters"), "dynamicScan.stopToleranceMeters")
        transport = semantics[TRANSPORT]
        barcode = transport["points"]["barcode"]
        low_name, high_name = transport["parameters"]["dynamicScanWindowPointNames"]
        transport["points"][low_name] = {"u": float(barcode["u"]) - tolerance, "v": float(barcode["v"])}
        transport["points"][high_name] = {"u": float(barcode["u"]) + tolerance, "v": float(barcode["v"])}
        transport["parameters"].update(
            {
                "dynamicScanStopToleranceMeters": tolerance,
                "dynamicScanStopToleranceConfirmed": scan_vendor_confirmed,
                "dynamicScanWindowAcceptedForCoarseLayout": True,
                "dynamicScanStopToleranceSource": str(
                    scan.get("source")
                    or (
                        "engineer-confirmed PLC/fixture input"
                        if scan_vendor_confirmed
                        else "Project02 prototype/geometry baseline"
                    )
                ),
                "dynamicScanStopToleranceSourceType": (
                    scan_source_type
                    or ("vendorDatum" if scan_vendor_confirmed else "prototypeBaseline")
                ),
                "dynamicScanStopToleranceAuthority": (
                    "vendorConfirmed"
                    if scan_vendor_confirmed
                    else "prototypeBaselineAcceptedForCoarseLayout"
                ),
                "dynamicScanStopTolerancePrototypeDerived": not scan_vendor_confirmed,
                "dynamicScanStopToleranceScope": (
                    "project02-vendor-interface"
                    if scan_vendor_confirmed
                    else "project02-only"
                ),
            }
        )
        sequence_scan = updated.setdefault("assemblySequencePolicy", {}).setdefault(
            "dynamicScan", {}
        )
        sequence_scan.update(
            {
                "confirmed": scan_vendor_confirmed,
                "estimateAcceptedForCoarseLayout": scan_prototype_baseline_accepted,
                "inputSourceType": (
                    scan_source_type
                    or ("vendorDatum" if scan_vendor_confirmed else "prototypeBaseline")
                ),
                "inputScope": (
                    "project02-vendor-interface"
                    if scan_vendor_confirmed
                    else "project02-only"
                ),
                "prototypeDerived": not scan_vendor_confirmed,
                "stopToleranceMeters": tolerance,
                "source": str(scan.get("source") or ""),
            }
        )
        applied.append("dynamicScan")
    else:
        skipped.append("dynamicScan")

    reach = inputs.get("dualValveReach") or {}
    reach_source_type = str(reach.get("sourceType") or "").strip()
    reach_vendor_confirmed = bool(
        reach.get("vendorConfirmed") is True
        or (
            reach.get("confirmed") is True
            and reach_source_type != "prototypeBaseline"
        )
    )
    reach_prototype_baseline_accepted = bool(
        reach_source_type == "prototypeBaseline"
        and reach.get("acceptedForCoarseLayout") is True
        and reach.get("vendorConfirmed") is not True
        and str(reach.get("scope") or "") == "project02-only"
    )
    if reach_vendor_confirmed and reach_source_type == "prototypeBaseline":
        raise EngineeringInputError(
            "dualValveReach prototypeBaseline cannot be marked vendorConfirmed"
        )
    if reach_vendor_confirmed or reach_prototype_baseline_accepted:
        left = _region(reach.get("leftValveReachLocalMeters"), "dualValveReach.leftValveReachLocalMeters")
        right = _region(reach.get("rightValveReachLocalMeters"), "dualValveReach.rightValveReachLocalMeters")
        common = _intersection(left, right)
        spacing = _positive(reach.get("valveHeadSpacingMeters"), "dualValveReach.valveHeadSpacingMeters")
        gantry = semantics[GANTRY]
        gantry["regions"].update(
            {"leftValveReach": left, "rightValveReach": right, "dualValveReach": common}
        )
        gantry["parameters"].update(
            {
                "estimatedValveHeadSpacingMeters": spacing,
                "valveHeadSpacingMeters": spacing,
                "valveHeadSpacingConfirmed": reach_vendor_confirmed,
                "reachModel": (
                    "engineer-confirmed-equivalent-left-right-common-envelope-v1"
                    if reach_vendor_confirmed
                    else "project02-prototype-baseline-left-right-common-envelope-v1"
                ),
                "reachEvidenceAuthority": (
                    "vendorConfirmed"
                    if reach_vendor_confirmed
                    else "prototypeBaselineAcceptedForCoarseLayout"
                ),
                "reachEvidenceSource": str(
                    reach.get("source")
                    or (
                        "engineer-confirmed valve reach"
                        if reach_vendor_confirmed
                        else "Project02 prototype/geometry baseline"
                    )
                ),
                "provisional": not reach_vendor_confirmed,
                "provisionalReach": not reach_vendor_confirmed,
            }
        )
        sequence_reach = updated.setdefault("assemblySequencePolicy", {}).setdefault(
            "dualValveReach", {}
        )
        sequence_reach.update(
            {
                "confirmed": reach_vendor_confirmed,
                "estimateAcceptedForCoarseLayout": reach_prototype_baseline_accepted,
                "inputSourceType": (
                    reach_source_type
                    or ("vendorDatum" if reach_vendor_confirmed else "prototypeBaseline")
                ),
                "inputScope": (
                    "project02-vendor-interface"
                    if reach_vendor_confirmed
                    else "project02-only"
                ),
                "prototypeDerived": not reach_vendor_confirmed,
                "source": str(reach.get("source") or ""),
            }
        )
        applied.append("dualValveReach")
    else:
        skipped.append("dualValveReach")

    maintenance = inputs.get("serviceAccess") or {}
    maintenance_source_type = str(maintenance.get("sourceType") or "").strip()
    maintenance_vendor_confirmed = bool(
        maintenance.get("vendorConfirmed") is True
        or (
            maintenance.get("confirmed") is True
            and maintenance_source_type != "prototypeBaseline"
        )
    )
    maintenance_prototype_baseline_accepted = bool(
        maintenance_source_type == "prototypeBaseline"
        and maintenance.get("acceptedForCoarseLayout") is True
        and maintenance.get("vendorConfirmed") is not True
        and str(maintenance.get("scope") or "") == "project02-only"
    )
    if maintenance_vendor_confirmed and maintenance_source_type == "prototypeBaseline":
        raise EngineeringInputError(
            "serviceAccess prototypeBaseline cannot be marked vendorConfirmed"
        )
    if maintenance_vendor_confirmed or maintenance_prototype_baseline_accepted:
        modules = maintenance.get("modules")
        if not isinstance(modules, dict) or not modules:
            raise EngineeringInputError("serviceAccess.modules must be a non-empty object")
        for component, spaces in modules.items():
            if component not in semantics:
                raise EngineeringInputError(f"Unknown service component: {component}")
            if not isinstance(spaces, list) or not spaces:
                raise EngineeringInputError(f"serviceAccess.modules.{component} must be a non-empty list")
            normalized = []
            for index, space in enumerate(spaces):
                bounds = space.get("bounds") if isinstance(space, dict) else None
                height = space.get("heightRangeMeters") if isinstance(space, dict) else None
                if not isinstance(bounds, list) or len(bounds) != 4 or not (float(bounds[0]) < float(bounds[2]) and float(bounds[1]) < float(bounds[3])):
                    raise EngineeringInputError(f"Invalid service space bounds for {component}[{index}]")
                if not isinstance(height, list) or len(height) != 2 or not float(height[0]) < float(height[1]):
                    raise EngineeringInputError(f"Invalid service height range for {component}[{index}]")
                normalized.append(deepcopy(space))
            parameters = semantics[component].setdefault("parameters", {})
            parameters["protectedSpaceBoxesLocal"] = normalized
            parameters["serviceAccessLaneRequired"] = True
            parameters["serviceAccessLaneEvidenceStatus"] = str(
                maintenance.get("source")
                or (
                    "engineer-confirmed maintenance envelope"
                    if maintenance_vendor_confirmed
                    else "Project02 prototype/coarse maintenance baseline"
                )
            )
            parameters["serviceAccessLaneConfirmed"] = maintenance_vendor_confirmed
            parameters["serviceAccessLaneAuthority"] = (
                "vendorConfirmed"
                if maintenance_vendor_confirmed
                else "prototypeBaselineAcceptedForCoarseLayout"
            )
            parameters["serviceAccessLanePrototypeDerived"] = (
                not maintenance_vendor_confirmed
            )
            parameters["serviceAccessLaneScope"] = (
                "project02-vendor-interface"
                if maintenance_vendor_confirmed
                else "project02-only"
            )
        functional_points = maintenance.get("functionalPoints") or {}
        if not isinstance(functional_points, dict):
            raise EngineeringInputError("serviceAccess.functionalPoints must be an object")
        for component, function_configurations in functional_points.items():
            if component not in semantics:
                raise EngineeringInputError(
                    f"Unknown functional service component: {component}"
                )
            if not isinstance(function_configurations, dict) or not function_configurations:
                raise EngineeringInputError(
                    f"serviceAccess.functionalPoints.{component} must be a non-empty object"
                )
            semantic = semantics[component]
            points = semantic.setdefault("points", {})
            parameters = semantic.setdefault("parameters", {})
            point_names: dict[str, str] = {}
            default_function = str(
                parameters.get("defaultServiceFunction") or ""
            ).strip()
            for function_name, configuration in function_configurations.items():
                if not isinstance(configuration, dict):
                    raise EngineeringInputError(
                        f"serviceAccess.functionalPoints.{component}.{function_name} must be an object"
                    )
                point_name = str(configuration.get("pointName") or "").strip()
                if not point_name:
                    raise EngineeringInputError(
                        f"serviceAccess.functionalPoints.{component}.{function_name}.pointName is required"
                    )
                point = _point2(
                    configuration.get("pointLocalMeters"),
                    f"serviceAccess.functionalPoints.{component}.{function_name}.pointLocalMeters",
                )
                points[point_name] = point
                point_names[str(function_name)] = point_name
                if configuration.get("defaultServiceFunction") is True:
                    default_function = str(function_name)
                for constraint_id in configuration.get("processConstraintIds") or []:
                    found = False
                    for constraint in updated.get("processConstraints") or []:
                        if constraint.get("id") == constraint_id:
                            if constraint.get("pointComponent") != component:
                                raise EngineeringInputError(
                                    f"Process constraint '{constraint_id}' does not target {component}"
                                )
                            constraint["point"] = point_name
                            found = True
                    if not found:
                        raise EngineeringInputError(
                            f"Unknown process constraint for functional point: {constraint_id}"
                        )
            if default_function:
                if default_function not in point_names:
                    raise EngineeringInputError(
                        f"Default service function '{default_function}' is not configured for {component}"
                    )
                points["servicePoint"] = deepcopy(points[point_names[default_function]])
            parameters["functionalServicePointNames"] = point_names
            parameters["defaultServiceFunction"] = default_function or None
            parameters["functionalServicePointsPrototypeDerived"] = (
                not maintenance_vendor_confirmed
            )
            parameters["functionalServicePointsAuthority"] = (
                "vendorConfirmed"
                if maintenance_vendor_confirmed
                else "prototypeBaselineAcceptedForCoarseLayout"
            )
        sequence_service = updated.setdefault("assemblySequencePolicy", {}).setdefault(
            "serviceAccess", {}
        )
        sequence_service.update(
            {
                "confirmed": maintenance_vendor_confirmed,
                "estimateAcceptedForCoarseLayout": maintenance_prototype_baseline_accepted,
                "inputSourceType": (
                    maintenance_source_type
                    or (
                        "vendorDatum"
                        if maintenance_vendor_confirmed
                        else "prototypeBaseline"
                    )
                ),
                "inputScope": (
                    "project02-vendor-interface"
                    if maintenance_vendor_confirmed
                    else "project02-only"
                ),
                "prototypeDerived": not maintenance_vendor_confirmed,
                "source": str(maintenance.get("source") or ""),
                "functionalSplitEvidencePath": maintenance.get(
                    "functionalSplitEvidencePath"
                ),
            }
        )
        applied.append("serviceAccess")
    else:
        skipped.append("serviceAccess")

    return updated, {
        "schemaVersion": "project02-engineering-input-application/v1",
        "success": True,
        "appliedSections": applied,
        "skippedUnconfirmedSections": skipped,
        "layoutResolveRequired": bool(applied),
        "replayDecisionDeferredUntilPoseComparison": bool(applied),
        "transportInstallationAuthority": (
            "vendorConfirmed"
            if transport_vendor_confirmed
            else "prototypeBaselineAcceptedForCoarseLayout"
            if transport_prototype_baseline_accepted
            else "notApplied"
        ),
        "dualValveReachAuthority": (
            "vendorConfirmed"
            if reach_vendor_confirmed
            else "prototypeBaselineAcceptedForCoarseLayout"
            if reach_prototype_baseline_accepted
            else "notApplied"
        ),
        "dynamicScanAuthority": (
            "vendorConfirmed"
            if scan_vendor_confirmed
            else "prototypeBaselineAcceptedForCoarseLayout"
            if scan_prototype_baseline_accepted
            else "notApplied"
        ),
        "serviceAccessAuthority": (
            "vendorConfirmed"
            if maintenance_vendor_confirmed
            else "prototypeBaselineAcceptedForCoarseLayout"
            if maintenance_prototype_baseline_accepted
            else "notApplied"
        ),
    }


def _positive(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EngineeringInputError(f"{label} must be a positive number") from exc
    if number <= 0:
        raise EngineeringInputError(f"{label} must be a positive number")
    return number


def _vector3(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise EngineeringInputError(f"{label} must contain three numbers")
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EngineeringInputError(f"{label} must contain three finite numbers") from exc
    if not all(math.isfinite(item) for item in result):
        raise EngineeringInputError(f"{label} must contain three finite numbers")
    return result


def _point2(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise EngineeringInputError(f"{label} must be an object")
    try:
        result = {"u": float(value["u"]), "v": float(value["v"])}
    except (KeyError, TypeError, ValueError) as exc:
        raise EngineeringInputError(f"{label} must contain finite u/v numbers") from exc
    if not all(math.isfinite(item) for item in result.values()):
        raise EngineeringInputError(f"{label} must contain finite u/v numbers")
    return result


def _region(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise EngineeringInputError(f"{label} must be an object")
    result = {key: float(value[key]) for key in ("minU", "minV", "maxU", "maxV")}
    if not (result["minU"] < result["maxU"] and result["minV"] < result["maxV"]):
        raise EngineeringInputError(f"{label} has an empty extent")
    return result


def _intersection(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    result = {
        "minU": max(left["minU"], right["minU"]),
        "minV": max(left["minV"], right["minV"]),
        "maxU": min(left["maxU"], right["maxU"]),
        "maxV": min(left["maxV"], right["maxV"]),
    }
    if not (result["minU"] < result["maxU"] and result["minV"] < result["maxV"]):
        raise EngineeringInputError("Confirmed left/right valve reaches have no common intersection")
    return result

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class AssemblySequenceConfigurationError(ValueError):
    pass


def build_assembly_sequence_plan(
    workspace: Path,
    request: dict[str, Any],
    generated: dict[str, Any],
) -> dict[str, Any] | None:
    """Compile the mechanical engineer's assembly order into an auditable gate.

    The current layout solver still operates on the eight process modules.  This
    plan deliberately separates evidence that is already available from facts
    that must be captured or confirmed before A600-anchored sequential solving
    can be claimed.
    """

    policy = request.get("assemblySequencePolicy")
    if not isinstance(policy, dict) or not policy.get("enabled", False):
        return None

    graph_path = _resolve_path(
        workspace,
        request.get("moduleMateGraphPath") or policy.get("moduleMateGraphPath"),
        "moduleMateGraphPath",
    )
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    modules = graph.get("Modules")
    bundles = graph.get("MateBundles")
    if not isinstance(modules, list) or not isinstance(bundles, list):
        raise AssemblySequenceConfigurationError(
            f"Module mate graph has no Modules/MateBundles arrays: {graph_path}"
        )

    base_code = str(policy.get("baseModuleCode") or "A600").upper()
    transport_code = str(policy.get("transportModuleCode") or "A800").upper()
    scanner_code = str(policy.get("scannerModuleCode") or "A180").upper()
    gantry_code = str(policy.get("gantryModuleCode") or "A100").upper()
    service_codes = [
        str(value).upper()
        for value in policy.get("serviceModuleCodes", ["A700", "A500", "A300"])
    ]

    graph_modules = {
        str(item.get("ModuleToken") or "").upper(): item
        for item in modules
        if item.get("ModuleToken")
    }
    bundle_index: dict[frozenset[str], dict[str, Any]] = {}
    for item in bundles:
        first = str(item.get("FirstModuleToken") or "").upper()
        second = str(item.get("SecondModuleToken") or "").upper()
        if first and second:
            bundle_index[frozenset((first, second))] = item

    generated_components = generated.get("components") or []
    solver_codes = {
        _component_code(str(item.get("componentName") or ""))
        for item in generated_components
    }
    semantic_by_code = _semantics_by_code(generated)

    operation_face = policy.get("operationFace") or {}
    operation_side = str(operation_face.get("side") or "unknown").lower()
    operation_face_confirmed = bool(operation_face.get("confirmed"))
    installation_frame = policy.get("installationFrame") or {}
    installation_frame_path: Path | None = None
    installation_frame_data: dict[str, Any] = {}
    if installation_frame.get("evidencePath"):
        installation_frame_path = _resolve_path(
            workspace,
            installation_frame.get("evidencePath"),
            "assemblySequencePolicy.installationFrame.evidencePath",
        )
        installation_frame_data = json.loads(
            installation_frame_path.read_text(encoding="utf-8")
        )
    installation_frame_resolved = bool(
        installation_frame.get("confirmed")
        and installation_frame_data.get("success") is True
        and str(installation_frame_data.get("moduleCode") or "").upper() == base_code
    )
    operation_side_resolved = operation_side in {"low", "high"} or (
        operation_side in {"front", "back"} and installation_frame_resolved
    )
    installation_geometry = policy.get("installationGeometry") or {}
    installation_geometry_path: Path | None = None
    installation_geometry_data: dict[str, Any] = {}
    if installation_geometry.get("evidencePath"):
        installation_geometry_path = _resolve_path(
            workspace,
            installation_geometry.get("evidencePath"),
            "assemblySequencePolicy.installationGeometry.evidencePath",
        )
        installation_geometry_data = json.loads(
            installation_geometry_path.read_text(encoding="utf-8")
        )
    installation_geometry_resolved = bool(
        installation_geometry.get("confirmed")
        and installation_geometry_data.get("success") is True
        and installation_geometry_data.get("usableForCoarseLayout") is True
        and str(installation_geometry_data.get("moduleCode") or "").upper() == base_code
    )
    base_in_graph = base_code in graph_modules
    base_in_solver = base_code in solver_codes or installation_geometry_resolved

    transport_bundle = bundle_index.get(frozenset((base_code, transport_code)))
    vendor_interface = policy.get("vendorTransportInterface") or {}
    vendor_xyz = vendor_interface.get("xyzMeters")
    vendor_xyz_confirmed = bool(
        vendor_interface.get("confirmed") and _is_xyz(vendor_xyz)
    )
    project02_prototype_reuse_confirmed = bool(
        vendor_interface.get("project02PrototypePoseReuseConfirmed")
        and vendor_interface.get("prototypeReuseScope") == "project02-only"
        and vendor_interface.get("prototypeReuseMode")
        == "source-capture-top-level-pose"
    )
    anchor_policy = request.get("sourceIndependentPolicy") or {}
    installation_frame_anchor_point = anchor_policy.get(
        "caseAnchorTargetFrameMeters"
    )
    installation_frame_anchor_resolved = bool(
        anchor_policy.get("caseAnchorEnabled")
        and str(anchor_policy.get("caseAnchorTargetKind") or "")
        == "installationFramePoint"
        and _component_code(str(anchor_policy.get("caseAnchorComponentName") or ""))
        == transport_code
        and _is_xyz(installation_frame_anchor_point)
        and str(anchor_policy.get("caseAnchorTargetFrameName") or "")
        == str(installation_frame_data.get("frameName") or "")
        and installation_frame_resolved
    )
    prototype_interface_path: Path | None = None
    prototype_interface_data: dict[str, Any] = {}
    if vendor_interface.get("prototypeEvidencePath"):
        prototype_interface_path = _resolve_path(
            workspace,
            vendor_interface.get("prototypeEvidencePath"),
            "assemblySequencePolicy.vendorTransportInterface.prototypeEvidencePath",
        )
        prototype_interface_data = json.loads(
            prototype_interface_path.read_text(encoding="utf-8")
        )
    prototype_interface_resolved = bool(
        vendor_interface.get("prototypeSeedAcceptedForCoarseLayout")
        and prototype_interface_data.get("success") is True
        and prototype_interface_data.get("usableAsPrototypeSeed") is True
        and str(prototype_interface_data.get("baseModuleCode") or "").upper() == base_code
        and str(prototype_interface_data.get("transportModuleCode") or "").upper()
        == transport_code
    )
    mate_interface_path: Path | None = None
    mate_interface_data: dict[str, Any] = {}
    if vendor_interface.get("mateDerivedEvidencePath"):
        mate_interface_path = _resolve_path(
            workspace,
            vendor_interface.get("mateDerivedEvidencePath"),
            "assemblySequencePolicy.vendorTransportInterface.mateDerivedEvidencePath",
        )
        mate_interface_data = json.loads(
            mate_interface_path.read_text(encoding="utf-8")
        )
    mate_interface_resolved = bool(
        vendor_interface.get("mateDerivedSeedAcceptedForCoarseLayout")
        and mate_interface_data.get("success") is True
        and mate_interface_data.get("usableAsMateDerivedCoarseInterface") is True
        and str(mate_interface_data.get("baseModuleCode") or "").upper() == base_code
        and str(mate_interface_data.get("transportModuleCode") or "").upper()
        == transport_code
    )

    scanner_semantic = semantic_by_code.get(scanner_code) or {}
    transport_semantic = semantic_by_code.get(transport_code) or {}
    scanner_process_evidence = {
        "scanOriginDefined": _has_point(scanner_semantic, "scanOrigin"),
        "barcodeDefined": _has_point(transport_semantic, "barcode"),
        "workingDistanceDefined": _positive_number(
            (scanner_semantic.get("parameters") or {}).get(
                "maxWorkingDistanceMeters"
            )
        ),
        "barcodeSideDefined": str(
            (scanner_semantic.get("parameters") or {}).get("barcodeSide") or ""
        ).lower()
        in {"low", "high"},
        "lineOfSightConstraintDefined": _has_constraint_fragment(
            generated, "auto-scanner-los-"
        ),
    }
    scanner_parameters = scanner_semantic.get("parameters") or {}
    transport_parameters = transport_semantic.get("parameters") or {}
    scan_station_path: Path | None = None
    scan_station_data: dict[str, Any] = {}
    if transport_parameters.get("scanCarrierInferenceEvidencePath"):
        scan_station_path = _resolve_path(
            workspace,
            transport_parameters.get("scanCarrierInferenceEvidencePath"),
            "moduleSemantics.transport.parameters.scanCarrierInferenceEvidencePath",
        )
        scan_station_data = json.loads(
            scan_station_path.read_text(encoding="utf-8-sig")
        )
    scan_station_inference_resolved = bool(
        transport_parameters.get("scanCarrierPositionCadInferred")
        and transport_parameters.get("scanCarrierPositionInferenceAudited")
        and scan_station_data.get("success") is True
        and scan_station_data.get("usableForCoarseLayout") is True
        and scan_station_data.get("selectedIsUniqueNearest") is True
        and scan_station_data.get("selectedCarrierInstance")
        == transport_parameters.get("scanCarrierInstance")
    )
    dynamic_scan_window_path: Path | None = None
    dynamic_scan_window_data: dict[str, Any] = {}
    if transport_parameters.get("dynamicScanWindowEvidencePath"):
        dynamic_scan_window_path = _resolve_path(
            workspace,
            transport_parameters.get("dynamicScanWindowEvidencePath"),
            "moduleSemantics.transport.parameters.dynamicScanWindowEvidencePath",
        )
        dynamic_scan_window_data = json.loads(
            dynamic_scan_window_path.read_text(encoding="utf-8-sig")
        )
    dynamic_scan_window_resolved = bool(
        scan_station_inference_resolved
        and transport_parameters.get("dynamicScanWindowAcceptedForCoarseLayout")
        and dynamic_scan_window_data.get("success") is True
        and dynamic_scan_window_data.get("usableForCoarseLayout") is True
        and dynamic_scan_window_data.get("carrierInstance")
        == transport_parameters.get("scanCarrierInstance")
        and len(transport_parameters.get("dynamicScanWindowPointNames") or []) == 2
    )
    dynamic_scan_policy = policy.get("dynamicScan") or {}
    legacy_geometry_confirmed = not _is_provisional(
        scanner_semantic
    ) and not _is_provisional(transport_semantic)
    scanner_capture_evidence = {
        "scanOriginMeasured": bool(
            scanner_parameters.get("scanOriginMeasured", legacy_geometry_confirmed)
        ),
        "scanOriginCadInferred": bool(
            scanner_parameters.get("scanOriginCadInferred", False)
        ),
        "barcodeMeasured": bool(
            transport_parameters.get("barcodeMeasured", legacy_geometry_confirmed)
        ),
        "workingDistanceConfirmed": bool(
            scanner_parameters.get("workingDistanceConfirmed", legacy_geometry_confirmed)
        ),
        "vendorWorkingDistanceConfirmed": bool(
            scanner_parameters.get("vendorWorkingDistanceConfirmed", False)
        ),
        "opticalAxisConfirmed": bool(
            scanner_parameters.get("opticalAxisConfirmed", legacy_geometry_confirmed)
        ),
        "opticalAxisCadInferred": bool(
            scanner_parameters.get("opticalAxisCadInferred", False)
        ),
        "scanCarrierPositionCadInferred": bool(
            transport_parameters.get("scanCarrierPositionCadInferred", False)
        ),
        "scanCarrierPositionInferenceAudited": scan_station_inference_resolved,
        "dynamicScanStopConfirmed": bool(
            transport_parameters.get("dynamicScanStopConfirmed", False)
        ),
        "dynamicScanWindowCoarseAudited": dynamic_scan_window_resolved,
        "dynamicScanStopToleranceConfirmed": bool(
            transport_parameters.get("dynamicScanStopToleranceConfirmed", False)
        ),
    }
    scanner_geometry_confirmed = all(
        scanner_capture_evidence[name]
        for name in (
            "scanOriginMeasured",
            "barcodeMeasured",
            "workingDistanceConfirmed",
            "opticalAxisConfirmed",
        )
    )

    service_bundles = {
        code: bundle_index.get(frozenset((base_code, code)))
        for code in service_codes
    }
    side_capacity = policy.get("operationSideCapacity") or {}
    side_capacity_path: Path | None = None
    side_capacity_data: dict[str, Any] = {}
    if side_capacity.get("evidencePath"):
        side_capacity_path = _resolve_path(
            workspace,
            side_capacity.get("evidencePath"),
            "assemblySequencePolicy.operationSideCapacity.evidencePath",
        )
        side_capacity_data = json.loads(
            side_capacity_path.read_text(encoding="utf-8")
        )
    service_placement_rule = policy.get("servicePlacementRule") or {}
    service_placement_rule_confirmed = bool(
        service_placement_rule.get("confirmed")
        and service_placement_rule.get("preferredLocation") == "nearOperationFace"
        and service_placement_rule.get("fallbackLocation") == "oppositeFace"
    )
    side_capacity_confirmed = bool(
        side_capacity.get("confirmed")
        and _non_negative_number(side_capacity.get("availableWidthMeters"))
        and _non_negative_number(side_capacity.get("requiredWidthMeters"))
    )
    side_capacity_estimated = bool(
        side_capacity.get("estimateAcceptedForCoarseLayout")
        and side_capacity_data.get("success") is True
        and side_capacity_data.get("usableForCoarseLayout") is True
        and str(
            (side_capacity_data.get("capacityDecision") or {}).get(
                "estimatedSelectedSide"
            )
            or side_capacity.get("estimatedSelectedSide")
            or ""
        ).lower()
        in {"front", "back"}
    )
    selected_service_side = (
        operation_side
        if side_capacity_confirmed
        and float(side_capacity["availableWidthMeters"])
        >= float(side_capacity["requiredWidthMeters"])
        else (
            _opposite_side(operation_side)
            if side_capacity_confirmed and operation_side in {"low", "high", "front", "back"}
            else "unknown"
        )
    )
    if not side_capacity_confirmed and side_capacity_estimated:
        selected_service_side = str(
            (side_capacity_data.get("capacityDecision") or {}).get(
                "estimatedSelectedSide"
            )
            or side_capacity.get("estimatedSelectedSide")
        ).lower()

    service_access = policy.get("serviceAccess") or {}
    service_access_path: Path | None = None
    service_access_data: dict[str, Any] = {}
    if service_access.get("evidencePath"):
        service_access_path = _resolve_path(
            workspace,
            service_access.get("evidencePath"),
            "assemblySequencePolicy.serviceAccess.evidencePath",
        )
        service_access_data = json.loads(
            service_access_path.read_text(encoding="utf-8-sig")
        )
    service_access_estimated = bool(
        service_access.get("estimateAcceptedForCoarseLayout")
        and service_access_data.get("success") is True
        and service_access_data.get("usableForCoarseLayout") is True
    )
    service_functional_split_path: Path | None = None
    service_functional_split_data: dict[str, Any] = {}
    if service_access.get("functionalSplitEvidencePath"):
        service_functional_split_path = _resolve_path(
            workspace,
            service_access.get("functionalSplitEvidencePath"),
            "assemblySequencePolicy.serviceAccess.functionalSplitEvidencePath",
        )
        service_functional_split_data = json.loads(
            service_functional_split_path.read_text(encoding="utf-8-sig")
        )
    service_functional_split_resolved = bool(
        service_access_estimated
        and service_functional_split_data.get("success") is True
        and service_functional_split_data.get("status")
        == "A700_CLEANING_WEIGHING_FUNCTIONS_SPLIT_FOR_COARSE_LAYOUT"
    )

    valve_reach_policy = policy.get("dualValveReach") or {}
    valve_reach_path: Path | None = None
    valve_reach_data: dict[str, Any] = {}
    if valve_reach_policy.get("evidencePath"):
        valve_reach_path = _resolve_path(
            workspace,
            valve_reach_policy.get("evidencePath"),
            "assemblySequencePolicy.dualValveReach.evidencePath",
        )
        valve_reach_data = json.loads(
            valve_reach_path.read_text(encoding="utf-8-sig")
        )
    valve_reach_estimated = bool(
        valve_reach_policy.get("estimateAcceptedForCoarseLayout")
        and valve_reach_data.get("success") is True
        and valve_reach_data.get("usableForCoarseLayout") is True
    )
    valve_axis_evidence_path: Path | None = None
    valve_axis_evidence_data: dict[str, Any] = {}
    if valve_reach_policy.get("axisEvidencePath"):
        valve_axis_evidence_path = _resolve_path(
            workspace,
            valve_reach_policy.get("axisEvidencePath"),
            "assemblySequencePolicy.dualValveReach.axisEvidencePath",
        )
        valve_axis_evidence_data = json.loads(
            valve_axis_evidence_path.read_text(encoding="utf-8-sig")
        )
    valve_constraint_ablation_path: Path | None = None
    valve_constraint_ablation_data: dict[str, Any] = {}
    if valve_reach_policy.get("constraintAblationPath"):
        valve_constraint_ablation_path = _resolve_path(
            workspace,
            valve_reach_policy.get("constraintAblationPath"),
            "assemblySequencePolicy.dualValveReach.constraintAblationPath",
        )
        valve_constraint_ablation_data = json.loads(
            valve_constraint_ablation_path.read_text(encoding="utf-8-sig")
        )

    robustness_policy = policy.get("parameterRobustness") or {}
    robustness_path: Path | None = None
    robustness_data: dict[str, Any] = {}
    if robustness_policy.get("evidencePath"):
        robustness_path = _resolve_path(
            workspace,
            robustness_policy.get("evidencePath"),
            "assemblySequencePolicy.parameterRobustness.evidencePath",
        )
        robustness_data = json.loads(
            robustness_path.read_text(encoding="utf-8-sig")
        )
    robustness_audited = bool(
        robustness_policy.get("acceptedForCoarsePlanning")
        and robustness_data.get("success") is True
        and robustness_data.get("status") == "COARSE_PARAMETER_SENSITIVITY_AUDITED"
    )

    gantry_semantic = semantic_by_code.get(gantry_code) or {}
    reach_regions = (gantry_semantic.get("regions") or {})
    reach_region_defined = bool(reach_regions)
    required_point_codes = [transport_code, *service_codes]
    reach_target_evidence = {
        code: _has_reach_target(semantic_by_code.get(code) or {})
        for code in required_point_codes
    }
    gantry_coverage_confirmed = bool(
        reach_region_defined
        and not _is_provisional(gantry_semantic)
        and all(reach_target_evidence.values())
        and all(
            not _is_provisional(semantic_by_code.get(code) or {})
            for code in required_point_codes
        )
    )

    stages = [
        _stage(
            "01-enclosure-frame",
            "建立A600箱体坐标系与操作面",
            [base_code],
            ready=(
                base_in_graph
                and base_in_solver
                and operation_face_confirmed
                and operation_side_resolved
            ),
            provisional=base_in_graph,
            evidence=[
                _evidence("A600存在于模组配合图", base_in_graph, "mateGraph"),
                _evidence("A600已进入求解几何", base_in_solver, "geometryCapture"),
                _evidence("操作面工程语义已人工确认", operation_face_confirmed, "engineerInput"),
                _evidence("A600三基准面安装坐标系已建立", installation_frame_resolved, "cadFrame"),
                _evidence(
                    "A600上部安装区与结构禁入区已建立",
                    installation_geometry_resolved,
                    "cadOccupancy",
                    details={
                        "hardKeepoutRegionCount": len(
                            installation_geometry_data.get("hardKeepoutRegions") or []
                        ),
                        "conditionalStructuralBodyCount": len(
                            installation_geometry_data.get("conditionalStructuralBodies") or []
                        ),
                        "coverageRatio": (
                            installation_geometry_data.get("captureCoverage") or {}
                        ).get("coverageRatio"),
                    },
                ),
            ],
            blocked_by=[
                item
                for item, condition in (
                    ("A600整体几何接入求解器", not base_in_solver),
                    ("A600操作面方向", not operation_face_confirmed),
                    ("A600安装坐标系", not operation_side_resolved),
                )
                if condition
            ],
        ),
        _stage(
            "02-transport-interface",
            "按A600工程安装基准固定A800",
            [base_code, transport_code],
            ready=bool(transport_bundle)
            and (
                vendor_xyz_confirmed
                or installation_frame_anchor_resolved
                or (
                    project02_prototype_reuse_confirmed
                    and prototype_interface_resolved
                    and mate_interface_resolved
                )
            ),
            provisional=bool(transport_bundle) and mate_interface_resolved,
            evidence=[
                _bundle_evidence(base_code, transport_code, transport_bundle),
                _evidence(
                    "A600–A800配合面已恢复Y/Z基准和姿态",
                    mate_interface_resolved,
                    "mateFaceMeasurement",
                    details={
                        "fixedTranslationAxes": (
                            (mate_interface_data.get("constraintInterpretation") or {}).get(
                                "fixedTranslationAxes"
                            )
                            if mate_interface_resolved
                            else None
                        ),
                        "freeTranslationAxes": (
                            (mate_interface_data.get("constraintInterpretation") or {}).get(
                                "freeTranslationAxes"
                            )
                            if mate_interface_resolved
                            else None
                        ),
                    },
                ),
                _evidence(
                    "A800原型位姿已转换到A600工程坐标系",
                    prototype_interface_resolved,
                    "prototypeMeasurement",
                ),
                _evidence(
                    "项目02已批准复用A800原型顶层位姿作为案例锚点",
                    project02_prototype_reuse_confirmed,
                    "engineerDecision",
                    details={
                        "scope": vendor_interface.get("prototypeReuseScope"),
                        "mode": vendor_interface.get("prototypeReuseMode"),
                        "promotedToGenericConstraint": False,
                    },
                ),
                _evidence(
                    "A800已由A600工程安装坐标中的显式锚点定位",
                    installation_frame_anchor_resolved,
                    "installationFrameAnchor",
                    details={
                        "anchorPointFrameMeters": installation_frame_anchor_point,
                        "sourceCapturePoseRead": False,
                        "prototypeDerivedParameter": bool(
                            anchor_policy.get("caseAnchorTargetPrototypeDerived")
                        ),
                        "targetSource": anchor_policy.get("caseAnchorTargetSource"),
                    },
                ),
                _evidence("厂商XYZ距离已确认", vendor_xyz_confirmed, "vendorInput"),
            ],
            blocked_by=(
                []
                if vendor_xyz_confirmed
                or installation_frame_anchor_resolved
                or (
                    project02_prototype_reuse_confirmed
                    and prototype_interface_resolved
                    and mate_interface_resolved
                )
                else [
                    "A800沿传输长轴X的厂商定位尺寸或端面/销孔基准确认"
                    if mate_interface_resolved
                    else "A800相对A600的厂商XYZ距离"
                ]
            ),
            measured={
                "prototypeWorldTranslationDeltaMeters": _prototype_world_translation_delta(
                    graph_modules.get(base_code), graph_modules.get(transport_code)
                ),
                "prototypeTranslationFrameMeters": (
                    prototype_interface_data.get("prototypeTranslationFrameMeters")
                    if prototype_interface_resolved
                    else None
                ),
                "prototypeBoundingBoxCenterFrameMeters": (
                    prototype_interface_data.get("prototypeBoundingBoxCenterFrameMeters")
                    if prototype_interface_resolved
                    else None
                ),
                "prototypeTransportCenterPlaneOffsetMeters": (
                    prototype_interface_data.get("transportCenterPlaneOffsetMeters")
                    if prototype_interface_resolved
                    else None
                ),
                "mateDerivedInstallationDatumFrameMeters": (
                    mate_interface_data.get("mateDerivedInstallationDatumFrameMeters")
                    if mate_interface_resolved
                    else None
                ),
                "mateConstraintInterpretation": (
                    mate_interface_data.get("constraintInterpretation")
                    if mate_interface_resolved
                    else None
                ),
                "mateAxisConfidence": (
                    mate_interface_data.get("axisConfidence")
                    if mate_interface_resolved
                    else None
                ),
                "vendorXyzMeters": vendor_xyz if _is_xyz(vendor_xyz) else None,
                "positioningAuthority": (
                    "vendorXYZ"
                    if vendor_xyz_confirmed
                    else "a600InstallationFramePoint"
                    if installation_frame_anchor_resolved
                    else "project02PrototypeCaseAnchor"
                    if project02_prototype_reuse_confirmed
                    else "unresolved"
                ),
                "mateBundleAssessment": (
                    transport_bundle.get("InstallationRelationAssessment")
                    if transport_bundle
                    else None
                ),
            },
        ),
        _stage(
            "03-scanner-visibility",
            "依据条码侧、工作距离和视线定位A180",
            [scanner_code, transport_code],
            ready=all(scanner_process_evidence.values()) and scanner_geometry_confirmed,
            provisional=all(scanner_process_evidence.values()),
            evidence=[
                _bundle_evidence(base_code, scanner_code, bundle_index.get(frozenset((base_code, scanner_code)))),
                *[
                    _evidence(label, success, "processSemantic")
                    for label, success in (
                        ("扫描原点已定义", scanner_process_evidence["scanOriginDefined"]),
                        ("条码点已定义", scanner_process_evidence["barcodeDefined"]),
                        ("扫描工作距离已定义", scanner_process_evidence["workingDistanceDefined"]),
                        ("条码侧已定义", scanner_process_evidence["barcodeSideDefined"]),
                        ("视线无遮挡约束已生成", scanner_process_evidence["lineOfSightConstraintDefined"]),
                    )
                ],
                _evidence(
                    "A180 SR-X100扫描出光面已由CAD面记录",
                    scanner_capture_evidence["scanOriginMeasured"],
                    "cadCapture",
                ),
                _evidence(
                    "A180扫描光轴原点已由CAD对称特征推断",
                    scanner_capture_evidence["scanOriginCadInferred"],
                    "cadInference",
                ),
                _evidence(
                    "A800条码面已由CAD面记录",
                    scanner_capture_evidence["barcodeMeasured"],
                    "cadCapture",
                ),
                _evidence(
                    "扫描工作距离已由设备规格或工艺确认",
                    scanner_capture_evidence["workingDistanceConfirmed"],
                    "engineeringInput",
                ),
                _evidence(
                    "SR-X100厂商读取范围已记录",
                    scanner_capture_evidence["vendorWorkingDistanceConfirmed"],
                    "vendorSpecification",
                    details={
                        "minimumMeters": scanner_parameters.get(
                            "vendorMinWorkingDistanceMeters"
                        ),
                        "maximumMeters": scanner_parameters.get(
                            "vendorMaxWorkingDistanceMeters"
                        ),
                        "projectPreferredMeters": scanner_parameters.get(
                            "preferredWorkingDistanceMeters"
                        ),
                    },
                ),
                _evidence(
                    "扫描出光面法向已确认代表实际光轴方向",
                    scanner_capture_evidence["opticalAxisConfirmed"],
                    "engineeringInput",
                ),
                _evidence(
                    "有向光轴已由扫描原点指向原型条码点推断并进入约束",
                    scanner_capture_evidence["opticalAxisCadInferred"]
                    and _has_constraint_fragment(
                        generated, "auto-scanner-directed-axis-"
                    ),
                    "cadInference",
                ),
                _evidence(
                    "缓存扫码载具8已由五个条码载具的CAD距离排序与PPT流程审计",
                    scanner_capture_evidence[
                        "scanCarrierPositionInferenceAudited"
                    ],
                    "cadPptInference",
                    details={
                        "evidencePath": str(scan_station_path)
                        if scan_station_path
                        else None,
                        "candidateCount": scan_station_data.get("candidateCount"),
                        "selectedCarrier": scan_station_data.get(
                            "selectedCarrierInstance"
                        ),
                        "nearestDistanceMarginMeters": scan_station_data.get(
                            "nearestDistanceMarginMeters"
                        ),
                        "dynamicScanStopConfirmed": scan_station_data.get(
                            "dynamicScanStopConfirmed"
                        ),
                    },
                ),
                _evidence(
                    "载具8动态停靠窗口两端已进入距离、视线和有向光轴粗约束",
                    scanner_capture_evidence["dynamicScanWindowCoarseAudited"]
                    and all(
                        _has_constraint_fragment(generated, fragment)
                        for fragment in (
                            "auto-scanner-dynamic-distance-",
                            "auto-scanner-dynamic-los-",
                            "auto-scanner-dynamic-directed-axis-",
                        )
                    ),
                    "cadGeometryEstimate",
                    details={
                        "evidencePath": str(dynamic_scan_window_path)
                        if dynamic_scan_window_path
                        else None,
                        "estimatedStopToleranceMeters": dynamic_scan_window_data.get(
                            "estimatedStopToleranceMeters"
                        ),
                        "axis": dynamic_scan_window_data.get("windowAxis"),
                        "engineeringConfirmed": dynamic_scan_window_data.get(
                            "engineeringConfirmed"
                        ),
                    },
                ),
            ],
            blocked_by=[
                item
                for item, missing in (
                    (
                        (
                            "工程确认CAD对称特征推断的A180扫描光轴原点，"
                            "或直接记录可用的SR-X100扫描出光面"
                            if scanner_capture_evidence["scanOriginCadInferred"]
                            else "选择并记录A180 SR-X100扫描出光面（扫描原点）"
                        ),
                        not scanner_capture_evidence["scanOriginMeasured"],
                    ),
                    (
                        "选择并记录A800条码面（条码点）",
                        not scanner_capture_evidence["barcodeMeasured"],
                    ),
                    (
                        "确认SR-X100扫描工作距离或允许范围",
                        not scanner_capture_evidence["workingDistanceConfirmed"],
                    ),
                    (
                        "确认扫描出光面法向代表实际光轴方向",
                        not scanner_capture_evidence["opticalAxisConfirmed"],
                    ),
                    (
                        "确认PLC触发时载具8动态停靠位置及允许公差",
                        dynamic_scan_window_resolved
                        and not scanner_capture_evidence[
                            "dynamicScanStopToleranceConfirmed"
                        ],
                    ),
                )
                if missing
            ],
            measured={
                "directScannerTransportMateExists": frozenset((scanner_code, transport_code))
                in bundle_index,
                "interpretation": "扫描可见性是工艺约束，不要求A180与A800存在直接配合。",
                "captureReadiness": scanner_capture_evidence,
                "configuredWorkingDistanceMeters": {
                    "minimum": scanner_parameters.get("minWorkingDistanceMeters"),
                    "preferred": scanner_parameters.get(
                        "preferredWorkingDistanceMeters"
                    ),
                    "maximum": scanner_parameters.get("maxWorkingDistanceMeters"),
                },
                "opticalAxisDirectionLocal": scanner_parameters.get(
                    "opticalAxisDirectionLocal"
                ),
                "maximumOpticalAxisDeviationDegrees": scanner_parameters.get(
                    "maxOpticalAxisDeviationDegrees"
                ),
                "scanStationInference": {
                    "resolvedForCoarseLayout": scan_station_inference_resolved,
                    "evidencePath": str(scan_station_path)
                    if scan_station_path
                    else None,
                    "selectedCarrierInstance": scan_station_data.get(
                        "selectedCarrierInstance"
                    ),
                    "candidateCount": scan_station_data.get("candidateCount"),
                    "candidateRanking": scan_station_data.get(
                        "candidateRanking"
                    ),
                    "nearestDistanceMarginMeters": scan_station_data.get(
                        "nearestDistanceMarginMeters"
                    ),
                    "dynamicScanStopConfirmed": scanner_capture_evidence[
                        "dynamicScanStopConfirmed"
                    ],
                },
                "dynamicScanWindow": {
                    "resolvedForCoarseLayout": dynamic_scan_window_resolved,
                    "evidencePath": str(dynamic_scan_window_path)
                    if dynamic_scan_window_path
                    else None,
                    "estimatedStopToleranceMeters": dynamic_scan_window_data.get(
                        "estimatedStopToleranceMeters"
                    ),
                    "windowAxis": dynamic_scan_window_data.get("windowAxis"),
                    "engineeringConfirmed": dynamic_scan_window_data.get(
                        "engineeringConfirmed"
                    ),
                    "plcTriggerConfirmed": dynamic_scan_window_data.get(
                        "plcTriggerConfirmed"
                    ),
                },
            },
        ),
        _stage(
            "04-service-side-selection",
            "按操作面剩余空间选择A500/A700/A300所在侧",
            [base_code, *service_codes],
            ready=(
                operation_face_confirmed
                and operation_side_resolved
                and service_placement_rule_confirmed
                and side_capacity_confirmed
            ),
            provisional=(
                operation_face_confirmed
                or service_placement_rule_confirmed
                or any(service_bundles.values())
            ),
            evidence=[
                _evidence("操作面工程语义已确认", operation_face_confirmed, "engineerInput"),
                _evidence(
                    "功能模组优先靠近操作面、空间不足转对侧",
                    service_placement_rule_confirmed,
                    "engineerInput",
                ),
                _evidence(
                    "操作面已映射到A600工程坐标系front/back侧",
                    operation_side_resolved,
                    "cadFrame",
                ),
                _evidence("操作面可用/需求宽度已确认", side_capacity_confirmed, "engineerInput"),
                _evidence(
                    "操作侧非凸空间已由原型和A600几何估计",
                    side_capacity_estimated,
                    "cadPrototypeEstimate",
                    details={
                        "evidencePath": str(side_capacity_path)
                        if side_capacity_path
                        else None,
                        "decision": side_capacity_data.get("capacityDecision"),
                    },
                ),
                _evidence(
                    "A500/A700/A300维护通道与垂直工艺通道通过粗几何约束",
                    service_access_estimated,
                    "coarseServiceAccessAudit",
                    details={
                        "evidencePath": str(service_access_path)
                        if service_access_path
                        else None,
                        "status": service_access_data.get("status"),
                        "constraintCount": service_access_data.get(
                            "protectedSpaceConstraintCount"
                        ),
                        "engineeringConfirmed": service_access_data.get(
                            "engineeringConfirmed"
                        ),
                    },
                ),
                *[
                    _bundle_evidence(base_code, code, service_bundles[code])
                    for code in service_codes
                ],
            ],
            blocked_by=[
                item
                for item, condition in (
                    ("A600操作面方向", not operation_face_confirmed),
                    ("操作面在A600工程坐标系中的侧别", not operation_side_resolved),
                    (
                        "确认操作侧非凸可用空间及真实维护包络",
                        not side_capacity_confirmed,
                    ),
                )
                if condition
            ],
            measured={
                "selectedServiceSide": selected_service_side,
                "selectionAuthority": (
                    "engineerConfirmedScalarCapacity"
                    if side_capacity_confirmed
                    else "prototypeObservedNonConvexEstimate"
                    if side_capacity_estimated
                    else "unresolved"
                ),
                "capacityEstimate": side_capacity_data.get("capacityDecision")
                if side_capacity_estimated
                else None,
                "maintenanceEstimate": side_capacity_data.get(
                    "maintenanceEstimate"
                )
                if side_capacity_estimated
                else None,
            },
        ),
        _stage(
            "05-gantry-final-coverage",
            "最后定位A100并覆盖工作区和全部服务点",
            [gantry_code, transport_code, *service_codes],
            ready=gantry_coverage_confirmed,
            provisional=reach_region_defined and all(reach_target_evidence.values()),
            evidence=[
                _bundle_evidence(base_code, gantry_code, bundle_index.get(frozenset((base_code, gantry_code)))),
                _evidence("双阀公共行程区域已定义", reach_region_defined, "processSemantic"),
                _evidence(
                    "左右阀等效行程、公共交集及全部目标点已通过粗模型审计",
                    valve_reach_estimated,
                    "coarseValveReachAudit",
                    details={
                        "evidencePath": str(valve_reach_path)
                        if valve_reach_path
                        else None,
                        "status": valve_reach_data.get("status"),
                        "commonIntersectionMatches": valve_reach_data.get(
                            "commonIntersectionMatches"
                        ),
                        "engineeringConfirmed": valve_reach_data.get(
                            "engineeringConfirmed"
                        ),
                    },
                ),
                *[
                    _evidence(f"{code}工作/服务点已定义", success, "processSemantic")
                    for code, success in reach_target_evidence.items()
                ],
                _evidence("行程与工艺点均已实测", gantry_coverage_confirmed, "cadCapture"),
            ],
            blocked_by=([] if gantry_coverage_confirmed else ["双阀真实行程及工作/服务点实测"]),
        ),
    ]

    sequential_ready = all(stage["status"] == "ready" for stage in stages)
    next_inputs: list[str] = []
    for stage in stages:
        for item in stage["blockedBy"]:
            if item not in next_inputs:
                next_inputs.append(item)

    return {
        "schemaVersion": "project02-assembly-sequence/v1",
        "enabled": True,
        "mode": "a600-anchored-sequential-readiness",
        "currentLayoutSolverMode": "legacy-joint-eight-module",
        "sequentialSolverReady": sequential_ready,
        "baseModuleCode": base_code,
        "operationFaceConfirmed": operation_face_confirmed,
        "operationSide": operation_side,
        "installationFrameResolved": installation_frame_resolved,
        "installationFramePath": str(installation_frame_path) if installation_frame_path else None,
        "installationFrame": (
            {
                "status": installation_frame_data.get("status"),
                "frameName": installation_frame_data.get("frameName"),
                "originWorldMeters": installation_frame_data.get("originWorldMeters"),
                "axesWorld": installation_frame_data.get("axesWorld"),
            }
            if installation_frame_resolved
            else None
        ),
        "installationGeometryResolved": installation_geometry_resolved,
        "installationGeometryPath": (
            str(installation_geometry_path) if installation_geometry_path else None
        ),
        "installationGeometry": (
            {
                "status": installation_geometry_data.get("status"),
                "installationPlatform": installation_geometry_data.get("installationPlatform"),
                "transportSupportRegion": installation_geometry_data.get("transportSupportRegion"),
                "hardKeepoutRegionCount": len(
                    installation_geometry_data.get("hardKeepoutRegions") or []
                ),
                "hardKeepoutRegions": installation_geometry_data.get("hardKeepoutRegions") or [],
                "conditionalStructuralBodyCount": len(
                    installation_geometry_data.get("conditionalStructuralBodies") or []
                ),
                "captureCoverage": installation_geometry_data.get("captureCoverage"),
                "authoritativeForFinalCollision": installation_geometry_data.get(
                    "authoritativeForFinalCollision"
                ),
            }
            if installation_geometry_resolved
            else None
        ),
        "prototypeTransportInterfaceResolved": prototype_interface_resolved,
        "project02PrototypeTransportReuseConfirmed": project02_prototype_reuse_confirmed,
        "installationFrameTransportAnchorResolved": installation_frame_anchor_resolved,
        "installationFrameTransportAnchorPointMeters": (
            installation_frame_anchor_point
            if installation_frame_anchor_resolved
            else None
        ),
        "prototypeTransportInterfacePath": (
            str(prototype_interface_path) if prototype_interface_path else None
        ),
        "mateDerivedTransportInterfaceResolved": mate_interface_resolved,
        "mateDerivedTransportInterfacePath": (
            str(mate_interface_path) if mate_interface_path else None
        ),
        "mateDerivedTransportInterface": (
            {
                "status": mate_interface_data.get("status"),
                "datumFrameMeters": mate_interface_data.get(
                    "mateDerivedInstallationDatumFrameMeters"
                ),
                "constraintInterpretation": mate_interface_data.get(
                    "constraintInterpretation"
                ),
                "axisConfidence": mate_interface_data.get("axisConfidence"),
                "confirmedAsVendorInterface": mate_interface_data.get(
                    "confirmedAsVendorInterface"
                ),
                "remainingRequiredConfirmation": mate_interface_data.get(
                    "remainingRequiredConfirmation"
                ),
            }
            if mate_interface_resolved
            else None
        ),
        "scanStationInferenceResolved": scan_station_inference_resolved,
        "scanStationInferencePath": (
            str(scan_station_path) if scan_station_path else None
        ),
        "scanStationInference": (
            {
                "status": scan_station_data.get("status"),
                "selectedCarrierInstance": scan_station_data.get(
                    "selectedCarrierInstance"
                ),
                "candidateCount": scan_station_data.get("candidateCount"),
                "nearestDistanceMarginMeters": scan_station_data.get(
                    "nearestDistanceMarginMeters"
                ),
                "selectedDistanceMeters": (
                    (scan_station_data.get("candidateRanking") or [{}])[0].get(
                        "scannerToQrDistanceMeters"
                    )
                ),
                "dynamicScanStopConfirmed": scan_station_data.get(
                    "dynamicScanStopConfirmed"
                ),
                "usableForCoarseLayout": scan_station_data.get(
                    "usableForCoarseLayout"
                ),
            }
            if scan_station_data
            else None
        ),
        "dynamicScanWindowResolved": dynamic_scan_window_resolved,
        "dynamicScanInputAuthority": (
            "vendorConfirmed"
            if dynamic_scan_policy.get("confirmed")
            else "prototypeBaselineAcceptedForCoarseLayout"
            if dynamic_scan_policy.get("inputSourceType") == "prototypeBaseline"
            and dynamic_scan_policy.get("estimateAcceptedForCoarseLayout")
            else "provisionalEstimate"
        ),
        "dynamicScanPrototypeDerived": bool(
            dynamic_scan_policy.get("prototypeDerived")
        ),
        "dynamicScanWindowPath": (
            str(dynamic_scan_window_path) if dynamic_scan_window_path else None
        ),
        "dynamicScanWindow": (
            {
                "status": dynamic_scan_window_data.get("status"),
                "estimatedStopToleranceMeters": dynamic_scan_window_data.get(
                    "estimatedStopToleranceMeters"
                ),
                "windowAxis": dynamic_scan_window_data.get("windowAxis"),
                "engineeringConfirmed": dynamic_scan_window_data.get(
                    "engineeringConfirmed"
                ),
                "plcTriggerConfirmed": dynamic_scan_window_data.get(
                    "plcTriggerConfirmed"
                ),
                "usableForCoarseLayout": dynamic_scan_window_data.get(
                    "usableForCoarseLayout"
                ),
            }
            if dynamic_scan_window_data
            else None
        ),
        "selectedServiceSide": selected_service_side,
        "operationSideCapacityEstimated": side_capacity_estimated,
        "operationSideCapacityEvidencePath": (
            str(side_capacity_path) if side_capacity_path else None
        ),
        "operationSideCapacity": (
            {
                "status": side_capacity_data.get("status"),
                "operationSideGrossBand": side_capacity_data.get(
                    "operationSideGrossBand"
                ),
                "prototypeServiceCluster": side_capacity_data.get(
                    "prototypeServiceCluster"
                ),
                "capacityDecision": side_capacity_data.get("capacityDecision"),
                "maintenanceEstimate": side_capacity_data.get(
                    "maintenanceEstimate"
                ),
                "authoritativeForFinalMaintenance": side_capacity_data.get(
                    "authoritativeForFinalMaintenance"
                ),
            }
            if side_capacity_estimated
            else None
        ),
        "serviceAccessEstimated": service_access_estimated,
        "serviceAccessInputAuthority": (
            "vendorConfirmed"
            if service_access.get("confirmed")
            else "prototypeBaselineAcceptedForCoarseLayout"
            if service_access.get("inputSourceType") == "prototypeBaseline"
            and service_access.get("estimateAcceptedForCoarseLayout")
            else "provisionalEstimate"
        ),
        "serviceAccessPrototypeDerived": bool(
            service_access.get("prototypeDerived")
        ),
        "serviceAccessEvidencePath": (
            str(service_access_path) if service_access_path else None
        ),
        "serviceAccess": service_access_data or None,
        "serviceFunctionalSplitResolved": service_functional_split_resolved,
        "serviceFunctionalSplitEvidencePath": (
            str(service_functional_split_path)
            if service_functional_split_path
            else None
        ),
        "serviceFunctionalSplit": service_functional_split_data or None,
        "dualValveReachEstimated": valve_reach_estimated,
        "dualValveReachInputAuthority": (
            "vendorConfirmed"
            if valve_reach_policy.get("confirmed")
            else "prototypeBaselineAcceptedForCoarseLayout"
            if valve_reach_policy.get("inputSourceType") == "prototypeBaseline"
            and valve_reach_policy.get("estimateAcceptedForCoarseLayout")
            else "provisionalEstimate"
        ),
        "dualValveReachPrototypeDerived": bool(
            valve_reach_policy.get("prototypeDerived")
        ),
        "dualValveReachEvidencePath": (
            str(valve_reach_path) if valve_reach_path else None
        ),
        "dualValveReach": valve_reach_data or None,
        "dualValveAxisEvidencePath": (
            str(valve_axis_evidence_path) if valve_axis_evidence_path else None
        ),
        "dualValveAxisEvidence": valve_axis_evidence_data or None,
        "dualValveConstraintAblationPath": (
            str(valve_constraint_ablation_path)
            if valve_constraint_ablation_path
            else None
        ),
        "dualValveConstraintAblation": valve_constraint_ablation_data or None,
        "parameterRobustnessAudited": robustness_audited,
        "parameterRobustnessEvidencePath": (
            str(robustness_path) if robustness_path else None
        ),
        "parameterRobustness": robustness_data or None,
        "moduleMateGraphPath": str(graph_path),
        "sourceAssemblyPath": graph.get("SourceAssemblyPath"),
        "stages": stages,
        "summary": {
            "stageCount": len(stages),
            "readyCount": sum(stage["status"] == "ready" for stage in stages),
            "provisionalCount": sum(stage["status"] == "provisional" for stage in stages),
            "blockedCount": sum(stage["status"] == "blocked" for stage in stages),
            "mateEvidenceBundleCount": sum(
                1 for stage in stages for item in stage["evidence"] if item["source"] == "mateGraph" and item["available"]
            ),
        },
        "nextRequiredInputs": next_inputs,
        "message": (
            "A600锚定的顺序求解门禁已通过。"
            if sequential_ready
            else "现有八模组布局仍可用于粗排和碰撞筛选，但尚不能标记为A600锚定的完整顺序求解。"
        ),
    }


def _stage(
    stage_id: str,
    title: str,
    module_codes: list[str],
    *,
    ready: bool,
    provisional: bool,
    evidence: list[dict[str, Any]],
    blocked_by: list[str],
    measured: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # A stage with a named missing input is blocked for formal sequential
    # solving even when useful prototype/mate evidence already exists.  The
    # evidence remains visible so it can still seed coarse reconstruction.
    status = "ready" if ready else "blocked" if blocked_by else "provisional" if provisional else "blocked"
    return {
        "id": stage_id,
        "title": title,
        "moduleCodes": module_codes,
        "status": status,
        "evidence": evidence,
        "blockedBy": blocked_by,
        "measured": measured or {},
    }


def _evidence(
    label: str,
    available: bool,
    source: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "available": bool(available),
        "source": source,
    }
    if details is not None:
        result["details"] = details
    return result


def _bundle_evidence(
    first: str,
    second: str,
    bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    assessment = bundle.get("InstallationRelationAssessment") if bundle else None
    return {
        "label": f"{first}与{second}存在模组级配合束",
        "available": bundle is not None,
        "source": "mateGraph",
        "details": {
            "mateCount": int(bundle.get("MateCount", 0)) if bundle else 0,
            "mateNames": list(bundle.get("MateNames") or []) if bundle else [],
            "assessment": assessment,
        },
    }


def _resolve_path(workspace: Path, value: Any, label: str) -> Path:
    if not value:
        raise AssemblySequenceConfigurationError(f"{label} is required.")
    path = Path(str(value))
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    if not path.is_file():
        raise AssemblySequenceConfigurationError(f"{label} does not exist: {path}")
    return path


def _semantics_by_code(generated: dict[str, Any]) -> dict[str, dict[str, Any]]:
    semantics = (generated.get("constraintPlan") or {}).get("moduleSemantics") or {}
    return {_component_code(str(name)): value for name, value in semantics.items()}


def _component_code(name: str) -> str:
    upper = name.upper()
    for code in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"):
        if code in upper:
            return code
    return upper


def _has_point(semantic: dict[str, Any], name: str) -> bool:
    return name in (semantic.get("points") or {})


def _has_reach_target(semantic: dict[str, Any]) -> bool:
    points = semantic.get("points") or {}
    return any(
        str(name).lower().startswith(("workposition", "servicepoint", "leftdrain", "rightdrain"))
        for name in points
    )


def _is_provisional(semantic: dict[str, Any]) -> bool:
    return bool((semantic.get("parameters") or {}).get("provisional", False))


def _has_constraint_fragment(generated: dict[str, Any], fragment: str) -> bool:
    constraints = (generated.get("constraintPlan") or {}).get("processConstraints") or []
    return any(fragment in str(item.get("id") or "") for item in constraints)


def _positive_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _non_negative_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def _is_xyz(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(_non_negative_or_signed_number(item) for item in value)
    )


def _non_negative_or_signed_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _opposite_side(side: str) -> str:
    return {
        "low": "high",
        "high": "low",
        "front": "back",
        "back": "front",
    }.get(side, "unknown")


def _prototype_world_translation_delta(
    base: dict[str, Any] | None,
    target: dict[str, Any] | None,
) -> list[float] | None:
    """Return only the source assembly's world-translation delta.

    This is useful audit evidence but is intentionally not called A600-local
    XYZ: deriving the vendor interface requires applying the A600 local frame
    and confirming which physical faces define the contractual dimensions.
    """
    if not base or not target:
        return None
    base_transform = base.get("SourceTransform")
    target_transform = target.get("SourceTransform")
    if not isinstance(base_transform, list) or not isinstance(target_transform, list):
        return None
    if len(base_transform) < 12 or len(target_transform) < 12:
        return None
    try:
        return [
            float(target_transform[index]) - float(base_transform[index])
            for index in range(9, 12)
        ]
    except (TypeError, ValueError):
        return None

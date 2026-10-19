"""Build fail-closed geometry acquisition requests for unregistered target slots.

This module does not search SolidWorks or invent an installation interface.  It
turns a known cross-project interface mismatch into a small, reviewable request
that a later targeted CAD capture (or a user face selection) can satisfy.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from copy import deepcopy
from typing import Any

from .global_module_catalog import validate_global_module_catalog


SCHEMA = "cross-project-slot-acquisition-request/v1"
SCREENING_SCHEMA = "cross-project-slot-capture-screening/v1"
SELECTION_SCHEMA = "cross-project-slot-candidate-selection/v1"
PORT_CANDIDATE_SCHEMA = "cross-project-slot-port-candidate/v1"


class CrossProjectSlotAcquisitionError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _module(
    catalog: dict[str, Any], *, project_id: str, module_token: str
) -> dict[str, Any]:
    matches = [
        row
        for row in catalog.get("moduleDefinitions") or []
        if any(
            alias.get("projectId") == project_id
            and alias.get("moduleToken") == module_token
            for alias in row.get("projectAliases") or []
        )
    ]
    if len(matches) != 1:
        raise CrossProjectSlotAcquisitionError(
            f"无法唯一定位模组：{project_id}/{module_token}。"
        )
    return matches[0]


def _ports_for(catalog: dict[str, Any], definition_id: str) -> list[dict[str, Any]]:
    return [
        row
        for row in catalog.get("semanticPorts") or []
        if row.get("moduleDefinitionId") == definition_id
    ]


def _port_with_roles(
    catalog: dict[str, Any], definition_id: str, required_roles: set[str]
) -> dict[str, Any]:
    matches = []
    for port in _ports_for(catalog, definition_id):
        roles = {
            str(item.get("role") or "")
            for item in port.get("endpointEvidence") or []
        }
        if required_roles.issubset(roles):
            matches.append(port)
    if len(matches) != 1:
        raise CrossProjectSlotAcquisitionError(
            "无法从端口证据中唯一恢复所需接口。"
        )
    return matches[0]


def _port_by_alias(
    catalog: dict[str, Any], definition_id: str, alias: str
) -> dict[str, Any]:
    matches = [
        port
        for port in _ports_for(catalog, definition_id)
        if alias in (port.get("aliases") or [])
    ]
    if len(matches) != 1:
        raise CrossProjectSlotAcquisitionError(f"无法唯一定位端口别名：{alias}。")
    return matches[0]


def _endpoint(port: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [
        row for row in port.get("endpointEvidence") or [] if row.get("role") == role
    ]
    if len(matches) != 1:
        raise CrossProjectSlotAcquisitionError(f"端口缺少唯一端点：{role}。")
    return matches[0]


def _distance(a: list[float], b: list[float]) -> float:
    if len(a) != 3 or len(b) != 3:
        raise CrossProjectSlotAcquisitionError("定位特征中心必须是三维坐标。")
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _unit(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(float(value) ** 2 for value in vector))
    if length <= 1e-12:
        raise CrossProjectSlotAcquisitionError("几何方向向量长度为零。")
    return [float(value) / length for value in vector]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(_unit(a), _unit(b)))


def _parallel_axis_spacing(
    origin_a: list[float], origin_b: list[float], axis: list[float]
) -> float:
    direction = _unit(axis)
    delta = [float(b) - float(a) for a, b in zip(origin_a, origin_b)]
    along = sum(value * direction[index] for index, value in enumerate(delta))
    normal = [
        value - along * direction[index] for index, value in enumerate(delta)
    ]
    return math.sqrt(sum(value * value for value in normal))


def _dominant_axis(vector: list[float]) -> int:
    values = [abs(value) for value in _unit(vector)]
    return max(range(3), key=values.__getitem__)


def _plane_supports_cylinders(
    plane: dict[str, Any], cylinders: list[dict[str, Any]], axis: list[float]
) -> bool:
    endpoint = plane.get("Endpoint") or {}
    plane_box = endpoint.get("FaceBoxLocal")
    plane_center = endpoint.get("FaceCenterLocal")
    if not isinstance(plane_box, list) or len(plane_box) != 6:
        return False
    if not isinstance(plane_center, list) or len(plane_center) != 3:
        return False
    axis_index = _dominant_axis(axis)
    tolerance = 1e-6
    for cylinder in cylinders:
        cylinder_endpoint = cylinder.get("Endpoint") or {}
        origin = cylinder_endpoint.get("CylinderOriginLocal")
        cylinder_box = cylinder_endpoint.get("FaceBoxLocal")
        if not isinstance(origin, list) or len(origin) != 3:
            return False
        if not isinstance(cylinder_box, list) or len(cylinder_box) != 6:
            return False
        # The support face must overlap each axis in the two in-plane
        # coordinates, rather than merely share a normal direction elsewhere
        # on the same part.
        for index in range(3):
            if index == axis_index:
                continue
            if not (
                float(plane_box[index]) - tolerance
                <= float(origin[index])
                <= float(plane_box[index + 3]) + tolerance
            ):
                return False
        # The plane must terminate or touch the cylindrical face along its
        # axis; this rejects unrelated parallel planes through the same body.
        coordinate = float(plane_center[axis_index])
        if not (
            float(cylinder_box[axis_index]) - tolerance
            <= coordinate
            <= float(cylinder_box[axis_index + 3]) + tolerance
        ):
            return False
    return True


def _cad_path(module: dict[str, Any]) -> str:
    paths = [
        str(item.get("path") or "")
        for item in module.get("cadSources") or []
        if str(item.get("path") or "")
    ]
    if not paths:
        raise CrossProjectSlotAcquisitionError("目标基座没有登记CAD路径。")
    return paths[0]


def build_calibration_slot_acquisition_request(
    catalog: dict[str, Any],
    *,
    geometry_capture: dict[str, Any],
    installation_surface: dict[str, Any],
    installation_frame: dict[str, Any],
    source_project: str = "project03",
    source_token: str = "AH00",
    target_base_project: str = "project02",
    target_base_token: str = "A600",
    native_target_project: str = "project02",
    native_target_token: str = "A500",
    native_slot_alias: str = "A600.a500_installation",
) -> dict[str, Any]:
    """Describe exactly what must be captured before an alternate slot exists."""

    validate_global_module_catalog(catalog)
    source = _module(catalog, project_id=source_project, module_token=source_token)
    base = _module(
        catalog, project_id=target_base_project, module_token=target_base_token
    )
    native_target = _module(
        catalog, project_id=native_target_project, module_token=native_target_token
    )
    source_port = _port_with_roles(
        catalog,
        source["moduleDefinitionId"],
        {"support_plane", "locating_hole_1", "locating_hole_2"},
    )
    native_slot = _port_by_alias(
        catalog, base["moduleDefinitionId"], native_slot_alias
    )
    hole_1 = _endpoint(source_port, "locating_hole_1")
    hole_2 = _endpoint(source_port, "locating_hole_2")
    # Normalize harmless floating-point residue so the acquisition contract is
    # stable across JSON serialization and Python/runtime versions.
    spacing = round(
        _distance(hole_1["faceCenterLocal"], hole_2["faceCenterLocal"]), 12
    )

    native_roles = [
        str(item.get("role") or "")
        for item in native_slot.get("endpointEvidence") or []
    ]
    leaf_counts = Counter(
        str(item.get("relativeLeafHierarchyPath") or "")
        for item in native_slot.get("endpointEvidence") or []
        if str(item.get("relativeLeafHierarchyPath") or "")
    )
    if not leaf_counts:
        raise CrossProjectSlotAcquisitionError("原生槽位缺少叶零件证据。")
    primary_leaf = leaf_counts.most_common(1)[0][0]
    body_indices = sorted(
        {
            int(item["bodyIndex"])
            for item in native_slot.get("endpointEvidence") or []
            if item.get("relativeLeafHierarchyPath") == primary_leaf
            and isinstance(item.get("bodyIndex"), int)
        }
    )

    capture_schema = str(geometry_capture.get("schemaVersion") or "")
    surface_schema = str(installation_surface.get("schemaVersion") or "")
    frame_schema = str(installation_frame.get("schemaVersion") or "")
    if capture_schema != "project02-a600-installation-geometry-capture/v1":
        raise CrossProjectSlotAcquisitionError("A600几何捕获版本不受支持。")
    if surface_schema != "project02-a600-installation-surface/v1":
        raise CrossProjectSlotAcquisitionError("A600安装面版本不受支持。")
    if frame_schema != "project02-a600-installation-frame/v1":
        raise CrossProjectSlotAcquisitionError("A600安装坐标系版本不受支持。")

    body_summary = geometry_capture.get("a600LeafBodyEnvelopes") or {}
    core = {
        "schemaVersion": SCHEMA,
        "status": "geometry_capture_required",
        "intent": (
            f"在{target_base_project}/{target_base_token}上寻找可安装"
            f"{source_project}/{source_token}校准模组的备用槽位"
        ),
        "sourceModule": {
            "projectId": source_project,
            "moduleToken": source_token,
            "moduleDefinitionId": source["moduleDefinitionId"],
            "cadPath": _cad_path(source),
            "installationPortId": source_port["globalPortId"],
        },
        "targetBase": {
            "projectId": target_base_project,
            "moduleToken": target_base_token,
            "moduleDefinitionId": base["moduleDefinitionId"],
            "cadPath": _cad_path(base),
        },
        "nativeTargetReference": {
            "projectId": native_target_project,
            "moduleToken": native_target_token,
            "moduleDefinitionId": native_target["moduleDefinitionId"],
            "nativeSlotPortId": native_slot["globalPortId"],
            "nativeEndpointRoles": native_roles,
            "topologyConclusion": "native_slot_not_equivalent_to_two_hole_pattern",
        },
        "requiredInterface": {
            "interfaceFamily": "support-plane-plus-two-location-features",
            "endpointRequirements": [
                {
                    "role": "support_plane",
                    "geometry": "planar_face",
                    "count": 1,
                },
                {
                    "role": "locating_feature_1",
                    "geometry": "cylindrical_face_or_stable_axis",
                    "count": 1,
                },
                {
                    "role": "locating_feature_2",
                    "geometry": "cylindrical_face_or_stable_axis",
                    "count": 1,
                },
            ],
            "locatingPairSpacingMeters": spacing,
            "spacingToleranceMeters": 0.0005,
            "spacingToleranceAuthority": "engineering-screening-estimate",
            "parallelLocatingAxesRequired": True,
            "featuresMustBelongToStaticBaseStructure": True,
        },
        "targetedCapturePlan": {
            "mode": "targeted-read-only-face-catalog",
            "primaryLeafHierarchyPath": primary_leaf,
            "priorityBodyIndicesFromNativeSlot": body_indices,
            "searchOrder": [
                "scan the primary static support leaf for planar and cylindrical faces",
                "filter pairs by parallel axes and 50 mm center spacing",
                "verify both locating features share a usable support plane",
                "if no candidate exists, capture two user-selected locating faces and one support face",
            ],
            "fallbackMode": "three-user-selected-faces",
            "fullAssemblyBlindScanRequired": False,
        },
        "existingEvidenceAssessment": {
            "geometryCapture": {
                "schemaVersion": capture_schema,
                "leafComponentCount": body_summary.get("LeafComponentCount"),
                "bodyCount": body_summary.get("BodyCount"),
                "coverageComplete": body_summary.get("CoverageComplete"),
                "sufficientForHoleTopology": False,
                "reason": "body AABB capture has no authoritative face or hole topology",
            },
            "installationSurface": {
                "schemaVersion": surface_schema,
                "usableForCoarseLayout": installation_surface.get(
                    "usableForCoarseLayout"
                ),
                "authoritativeForFinalCollision": installation_surface.get(
                    "authoritativeForFinalCollision"
                ),
                "sufficientForHoleTopology": False,
                "reason": "rasterized support and keepout regions do not identify locating faces",
            },
            "installationFrame": {
                "schemaVersion": frame_schema,
                "status": installation_frame.get("status"),
                "sufficientForHoleTopology": False,
                "reason": "the installation frame defines global planes, not local hole pairs",
            },
            "nativeSlot": {
                "endpointRoles": native_roles,
                "sufficientForRequiredInterface": False,
                "reason": "native A500 slot uses plane/width/offset topology instead of two locating features",
            },
        },
        "acceptanceChecks": [
            "恢复1个稳定支承面和2个稳定圆柱面或轴",
            "两定位轴平行且中心距满足50 mm筛选容差",
            "端点属于A600静止安装结构，不属于门板、护罩或运动件",
            "生成稳定端点目录并完成保存重开恢复测试",
            "端口证据发布后才允许编译跨项目安装事务",
        ],
        "executionPolicy": {
            "cadExecutionAllowed": False,
            "failClosedReason": "TARGET_SLOT_GEOMETRY_NOT_REGISTERED",
            "adapterGeometryInvented": False,
            "unregisteredSlotInferred": False,
            "collisionOrBrepRequiredAtThisStage": False,
        },
    }
    return {**core, "requestDigest": _digest(core)}


def screen_slot_capture(
    request: dict[str, Any], face_catalog: dict[str, Any]
) -> dict[str, Any]:
    """Screen a leaf-scoped face catalog; never publish or authorize a slot."""

    if request.get("schemaVersion") != SCHEMA:
        raise CrossProjectSlotAcquisitionError("不支持的采集请求版本。")
    if face_catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CrossProjectSlotAcquisitionError("不支持的面端点目录版本。")
    required = request["requiredInterface"]
    target_spacing = float(required["locatingPairSpacingMeters"])
    tolerance = float(required["spacingToleranceMeters"])
    target_leaf = str(
        request["targetedCapturePlan"].get("primaryLeafHierarchyPath") or ""
    )
    endpoints = list(face_catalog.get("Endpoints") or [])
    scoped = []
    for row in endpoints:
        endpoint = row.get("Endpoint") or {}
        relative_leaf = str(endpoint.get("RelativeLeafHierarchyPath") or "")
        # A deliberately leaf-scoped catalog may omit the parent path prefix;
        # a bounded source-mate catalog must match the requested leaf exactly.
        if target_leaf and relative_leaf and not (
            relative_leaf == target_leaf
            or target_leaf.endswith(relative_leaf)
            or relative_leaf.endswith(target_leaf)
        ):
            continue
        scoped.append(row)

    planes = []
    cylinders = []
    for row in scoped:
        endpoint = row.get("Endpoint") or {}
        surface_type = str(
            endpoint.get("SurfaceType") or row.get("GeometryClass") or ""
        ).lower()
        if surface_type == "plane" and endpoint.get("FaceNormalLocal"):
            planes.append(row)
        if (
            surface_type == "cylinder"
            and endpoint.get("CylinderOriginLocal")
            and endpoint.get("CylinderAxisLocal")
        ):
            cylinders.append(row)

    candidates = []
    for first_index, first in enumerate(cylinders):
        first_endpoint = first["Endpoint"]
        first_axis = first_endpoint["CylinderAxisLocal"]
        for second in cylinders[first_index + 1 :]:
            second_endpoint = second["Endpoint"]
            second_axis = second_endpoint["CylinderAxisLocal"]
            if first_endpoint.get("BodyIndex") != second_endpoint.get("BodyIndex"):
                continue
            first_radius = first_endpoint.get("CylinderRadius")
            second_radius = second_endpoint.get("CylinderRadius")
            if first_radius is None or second_radius is None:
                continue
            if abs(float(first_radius) - float(second_radius)) > 1e-6:
                continue
            parallel_cosine = abs(_dot(first_axis, second_axis))
            if parallel_cosine < 0.999:
                continue
            spacing = _parallel_axis_spacing(
                first_endpoint["CylinderOriginLocal"],
                second_endpoint["CylinderOriginLocal"],
                first_axis,
            )
            if abs(spacing - target_spacing) > tolerance:
                continue
            compatible_planes = []
            for plane in planes:
                plane_endpoint = plane.get("Endpoint") or {}
                normal = plane_endpoint.get("FaceNormalLocal")
                if (
                    plane_endpoint.get("BodyIndex")
                    == first_endpoint.get("BodyIndex")
                    and normal
                    and abs(_dot(normal, first_axis)) >= 0.999
                    and _plane_supports_cylinders(
                        plane, [first, second], first_axis
                    )
                ):
                    compatible_planes.append(plane)
            if not compatible_planes:
                continue
            candidates.append(
                {
                    "supportPlaneEndpointIds": sorted(
                        str(row.get("EndpointId") or "")
                        for row in compatible_planes
                    ),
                    "locatingEndpointIds": sorted(
                        [
                            str(first.get("EndpointId") or ""),
                            str(second.get("EndpointId") or ""),
                        ]
                    ),
                    "bodyIndex": first_endpoint.get("BodyIndex"),
                    "locatingRadiusMeters": float(first_radius),
                    "axisParallelCosine": parallel_cosine,
                    "axisSpacingMeters": spacing,
                    "spacingResidualMeters": abs(spacing - target_spacing),
                }
            )

    status = (
        "candidate_geometry_found_manual_review_required"
        if candidates
        else "no_matching_geometry_in_supplied_catalog"
    )
    core = {
        "schemaVersion": SCREENING_SCHEMA,
        "status": status,
        "requestDigest": request.get("requestDigest"),
        "catalogMode": face_catalog.get("CatalogMode"),
        "catalogEndpointCount": len(endpoints),
        "scopedEndpointCount": len(scoped),
        "planarEndpointCount": len(planes),
        "cylindricalEndpointCount": len(cylinders),
        "candidateCount": len(candidates),
        "candidates": sorted(
            candidates,
            key=lambda row: (
                row["spacingResidualMeters"],
                row["locatingEndpointIds"],
            ),
        ),
        "decision": {
            "semanticPortPublished": False,
            "cadExecutionAllowed": False,
            "nextAction": (
                "manual-review-and-endpoint-recovery-test"
                if candidates
                else "run-targeted-leaf-face-capture-or-user-select-three-faces"
            ),
        },
    }
    return {**core, "screeningDigest": _digest(core)}


def select_operation_side_candidate(
    request: dict[str, Any],
    screening: dict[str, Any],
    face_catalog: dict[str, Any],
    installation_frame: dict[str, Any],
) -> dict[str, Any]:
    """Rank screened candidates by the declared operation-side preference."""

    if request.get("schemaVersion") != SCHEMA:
        raise CrossProjectSlotAcquisitionError("不支持的采集请求版本。")
    if screening.get("schemaVersion") != SCREENING_SCHEMA:
        raise CrossProjectSlotAcquisitionError("不支持的候选筛选版本。")
    if screening.get("requestDigest") != request.get("requestDigest"):
        raise CrossProjectSlotAcquisitionError("候选筛选与采集请求摘要不匹配。")
    if not screening.get("candidates"):
        raise CrossProjectSlotAcquisitionError("没有可供排序的几何候选。")
    if installation_frame.get("schemaVersion") != (
        "project02-a600-installation-frame/v1"
    ):
        raise CrossProjectSlotAcquisitionError("不支持的A600安装坐标系版本。")
    endpoint_index = {
        str(row.get("EndpointId") or ""): row
        for row in face_catalog.get("Endpoints") or []
    }
    origin = installation_frame.get("originWorldMeters")
    axes = installation_frame.get("axesWorld") or {}
    x_axis = axes.get("xIntoMachine")
    y_axis = axes.get("yTransportLateral")
    z_axis = axes.get("zUp")
    if not all(isinstance(row, list) and len(row) == 3 for row in (origin, x_axis, y_axis, z_axis)):
        raise CrossProjectSlotAcquisitionError("A600安装坐标系缺少三维原点或轴。")

    ranked = []
    for candidate in screening["candidates"]:
        locating_ids = [
            str(endpoint_id) for endpoint_id in candidate.get("locatingEndpointIds") or []
        ]
        locating = [endpoint_index.get(endpoint_id) for endpoint_id in locating_ids]
        if len(locating) != 2 or any(row is None for row in locating):
            raise CrossProjectSlotAcquisitionError("候选定位端点不能在面目录中恢复。")
        world_origins = [
            (row.get("Endpoint") or {}).get("CylinderOriginWorld") for row in locating
        ]
        if not all(
            isinstance(row, list) and len(row) == 3 for row in world_origins
        ):
            raise CrossProjectSlotAcquisitionError("候选缺少圆柱轴世界坐标。")
        center = [
            sum(float(row[index]) for row in world_origins) / len(world_origins)
            for index in range(3)
        ]
        delta = [center[index] - float(origin[index]) for index in range(3)]
        frame_position = {
            "xIntoMachineMeters": sum(
                delta[index] * float(x_axis[index]) for index in range(3)
            ),
            "yTransportLateralMeters": sum(
                delta[index] * float(y_axis[index]) for index in range(3)
            ),
            "zUpMeters": sum(
                delta[index] * float(z_axis[index]) for index in range(3)
            ),
        }
        locating_positions = []
        for endpoint_id, world_origin in zip(locating_ids, world_origins):
            endpoint_delta = [
                float(world_origin[index]) - float(origin[index]) for index in range(3)
            ]
            locating_positions.append(
                {
                    "endpointId": endpoint_id,
                    "xIntoMachineMeters": sum(
                        endpoint_delta[index] * float(x_axis[index])
                        for index in range(3)
                    ),
                    "yTransportLateralMeters": sum(
                        endpoint_delta[index] * float(y_axis[index])
                        for index in range(3)
                    ),
                    "zUpMeters": sum(
                        endpoint_delta[index] * float(z_axis[index])
                        for index in range(3)
                    ),
                }
            )
        locating_positions.sort(
            key=lambda row: (-row["yTransportLateralMeters"], row["endpointId"])
        )
        ranked.append(
            {
                **deepcopy(candidate),
                "candidateCenterWorldMeters": center,
                "candidateCenterInA600FrameMeters": frame_position,
                "locatingEndpointsInA600FrameMeters": locating_positions,
                "roleAssignment": {
                    "rule": "descending_y_transport_lateral",
                    "meaning": (
                        "assign locating_hole_1 to the hole with the greater "
                        "A600 lateral coordinate; never derive mate orientation from endpoint hash order"
                    ),
                    "locating_hole_1": locating_positions[0]["endpointId"],
                    "locating_hole_2": locating_positions[1]["endpointId"],
                },
            }
        )
    ranked.sort(
        key=lambda row: (
            row["candidateCenterInA600FrameMeters"]["xIntoMachineMeters"],
            row["spacingResidualMeters"],
            row["locatingEndpointIds"],
        )
    )
    selected = ranked[0]
    core = {
        "schemaVersion": SELECTION_SCHEMA,
        "status": "candidate_selected_pending_cad_validation",
        "requestDigest": request.get("requestDigest"),
        "screeningDigest": screening.get("screeningDigest"),
        "selectionRule": {
            "primary": "minimum_positive_x_into_machine",
            "meaning": "prefer the 50 mm locating column closer to the operation face",
            "authority": "cad-measured-plus-declared-process-order",
            "collisionOrBrepUsed": False,
        },
        "selectedCandidate": selected,
        "alternateCandidates": ranked[1:],
        "decision": {
            "semanticPortPublished": False,
            "cadExecutionAllowed": False,
            "nextAction": "build-candidate-port-and-run-endpoint-recovery-test",
        },
    }
    return {**core, "selectionDigest": _digest(core)}


def build_slot_port_candidate(
    request: dict[str, Any],
    selection: dict[str, Any],
    face_catalog: dict[str, Any],
    *,
    endpoint_recovery_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Package the selected faces as an unpublished target-side port candidate.

    The result deliberately remains outside the released global catalog.  A
    successful endpoint recovery check proves only that the three selected
    faces can be found again; it does not prove that AH00 can yet be inserted,
    fully constrained, saved, and reopened through those faces.
    """

    if request.get("schemaVersion") != SCHEMA:
        raise CrossProjectSlotAcquisitionError("不支持的采集请求版本。")
    if selection.get("schemaVersion") != SELECTION_SCHEMA:
        raise CrossProjectSlotAcquisitionError("不支持的候选选择版本。")
    if selection.get("requestDigest") != request.get("requestDigest"):
        raise CrossProjectSlotAcquisitionError("候选选择与采集请求摘要不匹配。")
    if face_catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CrossProjectSlotAcquisitionError("不支持的面端点目录版本。")

    selected = selection.get("selectedCandidate") or {}
    support_ids = list(selected.get("supportPlaneEndpointIds") or [])
    assignment = selected.get("roleAssignment") or {}
    locating_ids = [
        assignment.get("locating_hole_1"),
        assignment.get("locating_hole_2"),
    ]
    if any(not endpoint_id for endpoint_id in locating_ids):
        locating_ids = list(selected.get("locatingEndpointIds") or [])
    if len(support_ids) != 1 or len(locating_ids) != 2:
        raise CrossProjectSlotAcquisitionError("候选端口必须包含一个支承面和两个定位面。")
    role_ids = {
        "support_plane": support_ids[0],
        "locating_hole_1": locating_ids[0],
        "locating_hole_2": locating_ids[1],
    }
    endpoint_index = {
        str(row.get("EndpointId") or ""): row
        for row in face_catalog.get("Endpoints") or []
    }
    missing = [endpoint_id for endpoint_id in role_ids.values() if endpoint_id not in endpoint_index]
    if missing:
        raise CrossProjectSlotAcquisitionError(
            f"候选端口端点不在面目录中：{', '.join(missing)}。"
        )

    endpoint_evidence = []
    for role, endpoint_id in role_ids.items():
        row = endpoint_index[endpoint_id]
        endpoint = row.get("Endpoint") or {}
        endpoint_evidence.append(
            {
                "role": role,
                "endpointId": endpoint_id,
                "geometryClass": row.get("GeometryClass"),
                "recoveryConfidence": row.get("RecoveryConfidence"),
                "relativeLeafHierarchyPath": endpoint.get(
                    "RelativeLeafHierarchyPath"
                ),
                "bodyIndex": endpoint.get("BodyIndex"),
                "faceIndexInBody": endpoint.get("FaceIndexInBody"),
                "faceArea": endpoint.get("FaceArea"),
                "faceCenterLocal": endpoint.get("FaceCenterLocal"),
                "faceNormalLocal": endpoint.get("FaceNormalLocal"),
                "cylinderOriginLocal": endpoint.get("CylinderOriginLocal"),
                "cylinderAxisLocal": endpoint.get("CylinderAxisLocal"),
                "cylinderRadiusMeters": endpoint.get("CylinderRadius"),
                "hasPersistentReference": bool(
                    endpoint.get("SourceAssemblyPersistentReferenceBase64")
                ),
            }
        )

    recovery_results = []
    if endpoint_recovery_evidence:
        if endpoint_recovery_evidence.get("schemaVersion") != (
            "cross-project-slot-endpoint-recovery/v1"
        ):
            raise CrossProjectSlotAcquisitionError("不支持的端点恢复证据版本。")
        if endpoint_recovery_evidence.get("selectionDigest") != selection.get(
            "selectionDigest"
        ):
            raise CrossProjectSlotAcquisitionError("端点恢复证据与候选选择摘要不匹配。")
        recovery_results = list(endpoint_recovery_evidence.get("results") or [])
    recovered_ids = {
        str(row.get("endpointId") or "")
        for row in recovery_results
        if row.get("success") is True
    }
    all_recovered = recovered_ids == set(role_ids.values())
    status = (
        "endpoint_recovered_pending_cross_project_cad"
        if all_recovered
        else "endpoint_recovery_required"
    )
    core = {
        "schemaVersion": PORT_CANDIDATE_SCHEMA,
        "status": status,
        "requestDigest": request.get("requestDigest"),
        "selectionDigest": selection.get("selectionDigest"),
        "candidatePort": {
            "portId": "A600.calibration_slot_candidate.operation_side",
            "moduleToken": "A600",
            "moduleHierarchyPath": "FL9A24D062A600.001-1",
            "displayName": "A600操作面侧校准模组候选安装端口",
            "category": "mechanical",
            # Match the already released AH00 interface family only inside
            # this candidate package; the port is not merged into the global
            # catalog until the cross-project CAD closure succeeds.
            "interfaceType": "project03_calibration_frame_installation",
            "capabilities": ["calibration_support", "installation"],
            "endpointBindings": [
                {"role": role, "endpointId": endpoint_id}
                for role, endpoint_id in role_ids.items()
            ],
            "endpointEvidence": endpoint_evidence,
            "status": "provisional",
            "portable": False,
            "portabilityReasons": [
                "cross-project insertion and full-constraint CAD closure not yet executed"
            ],
        },
        "endpointRecovery": {
            "requiredEndpointIds": list(role_ids.values()),
            "allRecovered": all_recovered,
            "results": recovery_results,
        },
        "decision": {
            "semanticPortPublished": False,
            "cadExecutionAllowed": all_recovered,
            "allowedCadScope": (
                "candidate-cross-project-validation-only" if all_recovered else None
            ),
            "nextAction": (
                "run-ah00-to-a600-nonprototype-initial-pose-cad-validation"
                if all_recovered
                else "recover-all-three-candidate-endpoints"
            ),
        },
    }
    return {**core, "candidatePortDigest": _digest(core)}

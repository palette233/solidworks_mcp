"""Confirm P000 external installation from full prototype mates and face geometry.

The legacy two-plane template omits the slot mate.  Source interface evidence
allows bounded target-slot discovery, not automatic cross-project publication.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any

from demo_backend.mate_dof_analysis import analyze_target_mate_dof

SCHEMA = "project05-p000-physical-attachment-candidate/v2"
STATUS = "source_slot_installation_confirmed_target_interface_pending"


class Project05P000PhysicalAttachmentCandidateError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _sub(a, b):
    return [left - right for left, right in zip(a, b)]


def _dot(a, b):
    return sum(left * right for left, right in zip(a, b))


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    length = _length(a)
    if length < 1e-12:
        raise Project05P000PhysicalAttachmentCandidateError("zero direction")
    return [item / length for item in a]


def _single(rows, predicate, description):
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise Project05P000PhysicalAttachmentCandidateError(
            f"expected one {description}, found {len(matches)}"
        )
    return matches[0]


def _payload(row):
    endpoint = row["Endpoint"]
    return {
        "endpointId": row["EndpointId"],
        "leafHierarchyPath": endpoint["RelativeLeafHierarchyPath"],
        "leafComponentPath": endpoint["LeafComponentPath"],
        "bodyIndex": endpoint["BodyIndex"],
        "faceIndexInBody": endpoint["FaceIndexInBody"],
        "surfaceType": endpoint["SurfaceType"],
        "faceCenterLocalMeters": endpoint.get("FaceCenterLocal"),
        "cylinderOriginLocalMeters": endpoint.get("CylinderOriginLocal"),
        "cylinderRadiusMeters": endpoint.get("CylinderRadius"),
    }


def _recover(rows, endpoint):
    reference = endpoint.get("SourceAssemblyPersistentReferenceBase64")
    if not reference:
        raise Project05P000PhysicalAttachmentCandidateError("missing persistent face identity")
    return _single(rows, lambda row: (
        row["Endpoint"].get("SourceAssemblyPersistentReferenceBase64") == reference
        and row["Endpoint"].get("RelativeLeafHierarchyPath")
        == endpoint.get("RelativeLeafHierarchyPath")
    ), "persistent mate endpoint")


def build_project05_p000_physical_attachment_candidate(
    *, catalog: dict[str, Any], face_catalog: dict[str, Any],
    source_graph: dict[str, Any], base_face_catalog: dict[str, Any],
) -> dict[str, Any]:
    if catalog.get("schemaVersion") != "global-module-catalog/v1":
        raise Project05P000PhysicalAttachmentCandidateError("unsupported global catalog")
    for data in (face_catalog, base_face_catalog):
        if data.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
            raise Project05P000PhysicalAttachmentCandidateError("unsupported face catalog")
    if source_graph.get("SchemaVersion") != "solidworks-module-mate-graph/v1.4":
        raise Project05P000PhysicalAttachmentCandidateError("unsupported source mate graph")
    mates = [deepcopy(row) for row in source_graph.get("Mates") or []
             if set(row.get("ModuleTokens") or []) == {"A000", "P000"}
             and row.get("IsSuppressed") is False]
    slot_mate = _single(mates, lambda row: row.get("MateType") == 21, "active source slot mate")
    support_mate = _single(mates, lambda row: row.get("MateType") == 0, "source support mate")
    direction_mate = _single(mates, lambda row: row.get("MateType") == 3, "source direction mate")
    if (slot_mate.get("AdvancedOptions") or {}).get("SlotConstraint") != 0:
        raise Project05P000PhysicalAttachmentCandidateError("expected source free-slot semantics")

    target_rows, base_rows = face_catalog["Endpoints"], base_face_catalog["Endpoints"]

    def mate_endpoint(mate, token):
        return _single(mate["Endpoints"], lambda row: row.get("ModuleToken") == token,
                       f"{token} mate endpoint")

    support = _recover(target_rows, mate_endpoint(support_mate, "P000"))
    direction = _recover(target_rows, mate_endpoint(direction_mate, "P000"))
    slot_face = _recover(target_rows, mate_endpoint(slot_mate, "P000"))
    native_base_face = _recover(base_rows, mate_endpoint(slot_mate, "A000"))
    _recover(base_rows, mate_endpoint(support_mate, "A000"))
    _recover(base_rows, mate_endpoint(direction_mate, "A000"))
    leaf, body = (slot_face["Endpoint"][key] for key in ("RelativeLeafHierarchyPath", "BodyIndex"))
    plate = [row for row in target_rows if (
        row["Endpoint"]["RelativeLeafHierarchyPath"] == leaf
        and row["Endpoint"]["BodyIndex"] == body
    )]
    if support not in plate or direction not in plate:
        raise Project05P000PhysicalAttachmentCandidateError("source interfaces span plate bodies")
    radius = float(slot_face["Endpoint"]["CylinderRadius"])
    arcs = [row for row in plate if row["Endpoint"].get("SurfaceType") == "Cylinder"
            and math.isclose(float(row["Endpoint"]["CylinderRadius"]), radius, abs_tol=1e-8)]

    # This bounded plate uses local Z as thickness and local Y as slot travel.
    # Require rounded ends AND both straight walls, rather than guessing from
    # partial cylindrical surfaces alone.
    slots, used = [], set()
    for arc in sorted(arcs, key=lambda row: row["Endpoint"]["CylinderOriginLocal"]):
        if arc["EndpointId"] in used:
            continue
        start = arc["Endpoint"]["CylinderOriginLocal"]
        partner = _single(arcs, lambda row: row["EndpointId"] != arc["EndpointId"]
            and abs(row["Endpoint"]["CylinderOriginLocal"][0] - start[0]) < 1e-8
            and abs(row["Endpoint"]["CylinderOriginLocal"][2] - start[2]) < 1e-8,
            "same-slot companion arc")
        end = partner["Endpoint"]["CylinderOriginLocal"]
        y0, y1 = sorted([start[1], end[1]])
        walls = []
        for wall_x in (start[0] - radius, start[0] + radius):
            walls.append(_single(plate, lambda row: row["Endpoint"].get("SurfaceType") == "Plane"
                and all(abs(a - b) < 1e-8 for a, b in zip(
                    [row["Endpoint"]["FaceBoxLocal"][i] for i in (0, 1, 3, 4)],
                    [wall_x, y0, wall_x, y1])), "straight slot wall"))
        used.update([arc["EndpointId"], partner["EndpointId"]])
        world_ends = [row["Endpoint"]["CylinderOriginWorld"] for row in (arc, partner)]
        travel = _sub(world_ends[1], world_ends[0])
        axis = _unit(arc["Endpoint"]["CylinderAxisWorld"])
        travel_axis, length = _unit(travel), _length(travel)
        slot = {
            "arcEndpointIds": [arc["EndpointId"], partner["EndpointId"]],
            "wallEndpointIds": [row["EndpointId"] for row in walls],
            "centerLocalMeters": [(a + b) / 2 for a, b in zip(start, end)],
            "widthMeters": 2 * radius, "endCenterSpacingMeters": length,
            "overallLengthMeters": length + 2 * radius,
            "sourceMateReferenced": slot_face["EndpointId"] in used
                and slot_face["EndpointId"] in (arc["EndpointId"], partner["EndpointId"]),
        }
        matches = []
        for row in base_rows:
            ep = row["Endpoint"]
            if ep.get("SurfaceType") != "Cylinder" or ep.get("RelativeLeafHierarchyPath") != (
                native_base_face["Endpoint"]["RelativeLeafHierarchyPath"]
            ):
                continue
            if abs(abs(_dot(_unit(ep["CylinderAxisWorld"]), axis)) - 1) > 1e-8:
                continue
            delta = _sub(ep["CylinderOriginWorld"], world_ends[0])
            along, normal = _dot(delta, travel_axis), _dot(delta, axis)
            lateral = _length([d - along*t - normal*n for d, t, n in zip(delta, travel_axis, axis)])
            if lateral < 1e-7 and -1e-8 <= along <= length + 1e-8:
                matches.append({
                    **_payload(row), "crossTrackErrorMeters": lateral,
                    "positionAlongSlotMeters": along,
                    "referencedBySourceSlotMate": row["EndpointId"] == native_base_face["EndpointId"],
                    "evidenceLevel": "source_mate" if row == native_base_face else "prototype_geometry_alignment",
                })
        slot["nativeBaseAxisMatches"] = matches
        slots.append(slot)
        if slot["sourceMateReferenced"]:
            slot_mate["AnalysisGeometry"] = {
                "SlotDirectionWorld": travel_axis, "SlotAxisWorld": axis,
                "SlotEndOriginsWorld": world_ends,
                "ContextPinOriginWorld": native_base_face["Endpoint"]["CylinderOriginWorld"],
                "SlotLengthMeters": length,
            }
    if len(slots) != 2 or not all(len(row["nativeBaseAxisMatches"]) == 1 for row in slots):
        raise Project05P000PhysicalAttachmentCandidateError(
            "expected two closed slots with unique native axis alignment"
        )
    round_holes = [row for row in plate if row["Endpoint"].get("SurfaceType") == "Cylinder"
                   and row["EndpointId"] not in used]
    dof = analyze_target_mate_dof({"Modules": source_graph["Modules"], "Mates": mates}, "P000")
    if dof["residualDof"] != 1:
        raise Project05P000PhysicalAttachmentCandidateError("unexpected source slot residual DOF")
    template = _single(catalog["connectionTemplates"], lambda row:
        row.get("legacyTemplateId") == "P000_to_A000_source_installation", "legacy template")
    full_names = [row["MateName"] for row in mates]
    legacy_names = [row["mateName"] for row in template["mateSteps"]]
    core = {
        "schemaVersion": SCHEMA, "status": STATUS, "role": "WasteCup",
        "module": {"projectId": "project05", "moduleToken": "P000",
                   "modulePath": face_catalog["Modules"][0]["Path"]},
        "boundedStaticLeaf": {"leafHierarchyPath": leaf, "bodyIndex": body,
                              "leafComponentPath": slot_face["Endpoint"]["LeafComponentPath"]},
        "candidateInterfaceSignature": {
            "candidateKind": "support_plane_parallel_slots_and_explicit_slide_position",
            "supportPlane": _payload(support), "directionPlane": _payload(direction),
            "slots": slots, "slotCount": len(slots), "slotWidthMeters": 2*radius,
            "slotCenterlineSpacingMeters": _length(_sub(slots[0]["centerLocalMeters"], slots[1]["centerLocalMeters"])),
            "mechanicalMeaningConfirmed": True,
            "confirmationScope": "prototype_external_support_and_slot_use",
            "fastenerSpecificationConfirmed": False,
        },
        "unassignedRoundHoles": {
            "faces": [_payload(row) for row in round_holes],
            "count": len(round_holes), "externalInstallationUseConfirmed": False,
            "reason": "完整原型顶层配合引用长圆槽；两处Ø5圆孔未被引用，暂不作为定位孔签名。",
        },
        "originalTopLevelEvidence": {
            "mateNames": full_names, "mateStepCount": len(mates),
            "containsPhysicalHoleAxisOrSlotEvidence": True,
            "persistentEndpointRecoveryPassed": True,
            "legacyTemplateId": template["globalTemplateId"],
            "legacyTemplateMateNames": legacy_names,
            "matesMissingFromLegacyTemplate": sorted(set(full_names) - set(legacy_names)),
            "sourceSlotConstraint": "free", "dofAnalysis": dof,
            "sufficientForIndependentPortableInstallation": False,
        },
        "correction": {
            "supersedesSchema": "project05-p000-physical-attachment-candidate/v1",
            "reason": "旧审计遗漏槽口6，将四个槽端误排除；它们与四个直壁组成两条闭合长圆槽。",
        },
        "evidenceDigests": {"sourceGraph": _digest(source_graph),
                            "plateFaces": _digest(face_catalog), "baseFaces": _digest(base_face_catalog)},
        "targetSlotSearchAllowed": True,
        "targetSlotSearchScope": "read_only_geometry_candidate_discovery",
        "cadLaunchAllowed": False, "semanticPortPublished": False,
        "prototypeTopLevelPoseUsedForAuthorization": False,
        "prototypeWorldGeometryUsedForSourceInterfaceVerification": True,
        "collisionOrBrepRequiredAtThisStage": False,
        "nextAction": "以支承面、双槽间距及槽内可调区间匹配A600原生/备用孔位；沿槽位置采用显式安装参数，匹配后再做非原型CAD闭环。",
    }
    return {**core, "candidateDigest": _digest(core)}


def validate_project05_p000_physical_attachment_candidate(report):
    expected = _digest({key: value for key, value in report.items() if key != "candidateDigest"})
    if report.get("schemaVersion") != SCHEMA or report.get("candidateDigest") != expected:
        raise Project05P000PhysicalAttachmentCandidateError("unsupported or altered attachment report")
    if (report.get("status") != STATUS or report.get("cadLaunchAllowed") is not False
            or report.get("semanticPortPublished") is not False
            or report.get("targetSlotSearchAllowed") is not True
            or report.get("candidateInterfaceSignature", {}).get("confirmationScope")
            != "prototype_external_support_and_slot_use"):
        raise Project05P000PhysicalAttachmentCandidateError(
            "source confirmation cannot authorize cross-project CAD"
        )
    return {"success": True, "status": report["status"], "candidateDigest": expected}

"""Build coarse-layout occupancy and collision policy for Project 01.

The source captures contain conservative world AABBs for every leaf body.  A
solver cannot afford to compare thousands of boxes, and a single top-level
AABB closes the real openings in the gantry, transport and scanner structures.
This module therefore unions leaf bodies by process-relevant direct subtree and
classifies every layout-object pair before any CAD Replay is attempted.
"""

from __future__ import annotations

import itertools
import math
import re
from typing import Any, Iterable


LAYOUT_OBJECTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("frame-context", ("JJ00", "HL00")),
    ("transport-process-group", ("SS00",)),
    ("flip-positioning-module", ("FF00",)),
    ("gantry-motion-group", ("LM00", "ZZ00")),
    ("combined-service-module", ("GN00",)),
    ("calibration-module", ("BD00",)),
    ("scanner-module", ("SM00",)),
    ("glue-supply-module", ("GJ00",)),
)

CONDITIONAL_BREP_PAIRS: dict[frozenset[str], str] = {
    frozenset(("transport-process-group", "flip-positioning-module")): (
        "Flip stations occupy openings around the transport process path."
    ),
    frozenset(("transport-process-group", "gantry-motion-group")): (
        "The transport passes through the gantry working portal."
    ),
    frozenset(("flip-positioning-module", "gantry-motion-group")): (
        "The gantry covers both flip/positioning work stations."
    ),
    frozenset(("combined-service-module", "gantry-motion-group")): (
        "Valve reach must cover GN00 service ports while the gantry frame surrounds the work area."
    ),
    frozenset(("calibration-module", "gantry-motion-group")): (
        "Valve reach must cover the BD00 calibration target inside the gantry service area."
    ),
    frozenset(("scanner-module", "gantry-motion-group")): (
        "The scanner support and gantry are sparse structures with overlapping broad envelopes."
    ),
    frozenset(("scanner-module", "transport-process-group")): (
        "Scanner beams and supports intentionally approach the carrier/product path."
    ),
    frozenset(("scanner-module", "flip-positioning-module")): (
        "The moving product scanner serves the flip/positioning stations."
    ),
    frozenset(("flip-positioning-module", "combined-service-module")): (
        "Prototype leaf AABBs overlap at the FF00/GN00 boundary; exact solids must distinguish real contact from conservative body boxes."
    ),
}


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _subtract(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def _corners(bounds: list[float]) -> list[list[float]]:
    if len(bounds) != 6:
        raise ValueError("AABB must contain six coordinates")
    return [
        [x, y, z]
        for x in (float(bounds[0]), float(bounds[3]))
        for y in (float(bounds[1]), float(bounds[4]))
        for z in (float(bounds[2]), float(bounds[5]))
    ]


def _union(boxes: Iterable[list[float]]) -> list[float]:
    values = list(boxes)
    if not values:
        raise ValueError("Cannot union an empty box collection")
    return [
        min(box[axis] for box in values) for axis in range(3)
    ] + [
        max(box[axis + 3] for box in values) for axis in range(3)
    ]


def _project_box(
    bounds: list[float], origin: list[float], axes: dict[str, list[float]]
) -> dict[str, float]:
    projected = {
        axis: [_dot(_subtract(point, origin), vector) for point in _corners(bounds)]
        for axis, vector in axes.items()
    }
    return {
        "minU": min(projected["u"]),
        "maxU": max(projected["u"]),
        "minV": min(projected["v"]),
        "maxV": max(projected["v"]),
        "minN": min(projected["n"]),
        "maxN": max(projected["n"]),
    }


def _project_point(
    point: list[float], origin: list[float], axes: dict[str, list[float]]
) -> dict[str, float]:
    relative = _subtract(point, origin)
    return {axis: _dot(relative, vector) for axis, vector in axes.items()}


def _component_code(name: str) -> str:
    match = re.search(r"N074([A-Z]{2}\d{2})", str(name).upper())
    if match:
        return match.group(1)
    for code in ("JJ00", "HL00", "SS00", "FF00", "LM00", "ZZ00", "GN00", "BD00", "SM00", "GJ00"):
        if code in str(name).upper():
            return code
    return str(name)


def _subtree_key(code: str, body: dict[str, Any]) -> str:
    component = body.get("Component") or {}
    text = "/".join(
        str(component.get(key) or "")
        for key in ("HierarchyPath", "Name", "Path")
    ).upper()
    if code in {"SS00", "SM00"}:
        match = re.search(rf"{code[:2]}(?:00)?(10|20|60)", text)
        return f"{code[:2]}{match.group(1)}" if match else f"{code}-support"
    if code == "FF00":
        match = re.search(r"FF(10|80)\.001-(\d+)", text)
        return f"FF{match.group(1)}-{match.group(2)}" if match else "FF00-drive-support"
    if code == "GN00":
        for token in ("GN10", "GN20", "GN30", "FJ00"):
            if token in text:
                return token
        return "GN00-common-support"
    if code == "BD00":
        if "CCD" in text:
            return "BD00-camera-support"
        if re.search(r"BD000(?:0[7-9]|1[0-3])", text):
            return "BD00-prism-light-target"
        return "BD00-common-support"
    if code in {"LM00", "ZZ00"}:
        prefix = code[:2]
        match = re.search(rf"{prefix}(10|20|30|40|50|60)", text)
        return f"{prefix}{match.group(1)}" if match else f"{code}-common-structure"
    return f"{code}-top-level"


def _aabb_overlap(first: dict[str, float], second: dict[str, float], inflation: float = 0.0) -> bool:
    return not any(
        first[f"max{axis}"] + inflation < second[f"min{axis}"] - inflation
        or second[f"max{axis}"] + inflation < first[f"min{axis}"] - inflation
        for axis in ("U", "V", "N")
    )


def _capture_index(documents: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for document in documents:
        for capture in document.get("captures") or []:
            code = _component_code((capture.get("TopLevelComponent") or {}).get("Name", ""))
            result[code] = capture
    return result


def build_project01_occupancy_and_collision_policy(
    top_level_poses: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    leaf_capture_documents: Iterable[dict[str, Any]],
    *,
    inflation_per_side_meters: float = 0.001,
) -> dict[str, Any]:
    interface = first_stage_geometry["transportInstallationInterface"]
    origin = [float(value) for value in interface["originWorldMeters"]]
    axes = {
        "u": [float(value) for value in interface["flowAxisWorld"]],
        "v": [float(value) for value in interface["transverseAxisWorld"]],
        "n": [float(value) for value in interface["upAxisWorld"]],
    }
    poses = {
        _component_code(item["Name"]): item for item in top_level_poses.get("components") or []
    }
    captures = _capture_index(leaf_capture_documents)

    modules: dict[str, dict[str, Any]] = {}
    for code, pose in poses.items():
        world_box = [float(value) for value in pose["BoundingBoxWorld"]]
        top_box = _project_box(world_box, origin, axes)
        anchor = _project_point([float(value) for value in pose["Translation"]], origin, axes)
        capture = captures.get(code)
        grouped: dict[str, list[list[float]]] = {}
        if capture:
            for body in capture.get("Bodies") or []:
                bounds = body.get("BoundingBoxWorld")
                if not isinstance(bounds, list) or len(bounds) != 6:
                    continue
                grouped.setdefault(_subtree_key(code, body), []).append(
                    [float(value) for value in bounds]
                )
        occupancy_boxes = []
        leaf_body_boxes = []
        source = "leaf-subtree-unions" if grouped else "conservative-top-level-aabb"
        if capture:
            for body_index, body in enumerate(capture.get("Bodies") or []):
                bounds = body.get("BoundingBoxWorld")
                if not isinstance(bounds, list) or len(bounds) != 6:
                    continue
                projected = _project_box([float(value) for value in bounds], origin, axes)
                component = body.get("Component") or {}
                leaf_body_boxes.append(
                    {
                        "id": f"{code}-leaf-{body_index}",
                        "component": component.get("HierarchyPath") or component.get("Name"),
                        "installationBoundsMeters": projected,
                        "localBoundsMeters": {
                            "minU": projected["minU"] - anchor["u"],
                            "maxU": projected["maxU"] - anchor["u"],
                            "minV": projected["minV"] - anchor["v"],
                            "maxV": projected["maxV"] - anchor["v"],
                            "minN": projected["minN"] - anchor["n"],
                            "maxN": projected["maxN"] - anchor["n"],
                        },
                    }
                )
        for key, world_boxes in sorted(grouped.items()):
            projected = _project_box(_union(world_boxes), origin, axes)
            occupancy_boxes.append(
                {
                    "id": f"{code}-{key}",
                    "subtree": key,
                    "source": source,
                    "installationBoundsMeters": projected,
                    "localBoundsMeters": {
                        "minU": projected["minU"] - anchor["u"],
                        "maxU": projected["maxU"] - anchor["u"],
                        "minV": projected["minV"] - anchor["v"],
                        "maxV": projected["maxV"] - anchor["v"],
                        "minN": projected["minN"] - anchor["n"],
                        "maxN": projected["maxN"] - anchor["n"],
                    },
                    "leafBodyCount": len(world_boxes),
                }
            )
        if not occupancy_boxes:
            occupancy_boxes.append(
                {
                    "id": f"{code}-top-level",
                    "subtree": f"{code}-top-level",
                    "source": source,
                    "installationBoundsMeters": top_box,
                    "localBoundsMeters": {
                        "minU": top_box["minU"] - anchor["u"],
                        "maxU": top_box["maxU"] - anchor["u"],
                        "minV": top_box["minV"] - anchor["v"],
                        "maxV": top_box["maxV"] - anchor["v"],
                        "minN": top_box["minN"] - anchor["n"],
                        "maxN": top_box["maxN"] - anchor["n"],
                    },
                    "leafBodyCount": None,
                }
            )
        modules[code] = {
            "componentName": pose["Name"],
            "filePath": pose.get("Path"),
            "prototypeAnchorInstallationMeters": anchor,
            "topLevelBoundsInstallationMeters": top_box,
            "occupancySource": source,
            "leafCoverageComplete": bool(capture and capture.get("CoverageComplete") is True),
            "leafComponentCount": capture.get("LeafComponentCount") if capture else None,
            "bodyCount": capture.get("BodyCount") if capture else None,
            "occupancyBoxes": occupancy_boxes,
            "leafBodyOccupancyBoxes": leaf_body_boxes,
        }

    layout_objects: list[dict[str, Any]] = []
    for object_id, member_codes in LAYOUT_OBJECTS:
        primary = member_codes[0]
        primary_anchor = modules[primary]["prototypeAnchorInstallationMeters"]
        boxes = []
        leaf_boxes = []
        for code in member_codes:
            for box in modules[code]["occupancyBoxes"]:
                installation = box["installationBoundsMeters"]
                boxes.append(
                    {
                        **box,
                        "memberCode": code,
                        "localToObjectAnchorMeters": {
                            "minU": installation["minU"] - primary_anchor["u"],
                            "maxU": installation["maxU"] - primary_anchor["u"],
                            "minV": installation["minV"] - primary_anchor["v"],
                            "maxV": installation["maxV"] - primary_anchor["v"],
                            "minN": installation["minN"] - primary_anchor["n"],
                            "maxN": installation["maxN"] - primary_anchor["n"],
                        },
                    }
                )
            for box in modules[code]["leafBodyOccupancyBoxes"]:
                installation = box["installationBoundsMeters"]
                leaf_boxes.append(
                    {
                        **box,
                        "memberCode": code,
                        "localToObjectAnchorMeters": {
                            "minU": installation["minU"] - primary_anchor["u"],
                            "maxU": installation["maxU"] - primary_anchor["u"],
                            "minV": installation["minV"] - primary_anchor["v"],
                            "maxV": installation["maxV"] - primary_anchor["v"],
                            "minN": installation["minN"] - primary_anchor["n"],
                            "maxN": installation["maxN"] - primary_anchor["n"],
                        },
                    }
                )
        layout_objects.append(
            {
                "id": object_id,
                "memberCodes": list(member_codes),
                "primaryCode": primary,
                "prototypeAnchorInstallationMeters": primary_anchor,
                "occupancyBoxCount": len(boxes),
                "occupancyBoxes": boxes,
                "leafBodyOccupancyBoxCount": len(leaf_boxes),
                "leafBodyOccupancyBoxes": leaf_boxes,
            }
        )

    objects_by_id = {item["id"]: item for item in layout_objects}
    strict_pairs: list[list[str]] = []
    conditional_pairs: list[dict[str, Any]] = []
    installation_pairs: list[dict[str, Any]] = []
    strict_pair_profiles: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for first_id, second_id in itertools.combinations(objects_by_id, 2):
        key = frozenset((first_id, second_id))
        first_boxes = objects_by_id[first_id]["occupancyBoxes"]
        second_boxes = objects_by_id[second_id]["occupancyBoxes"]
        top_first = _union([
            [
                box["installationBoundsMeters"]["minU"],
                box["installationBoundsMeters"]["minV"],
                box["installationBoundsMeters"]["minN"],
                box["installationBoundsMeters"]["maxU"],
                box["installationBoundsMeters"]["maxV"],
                box["installationBoundsMeters"]["maxN"],
            ]
            for box in first_boxes
        ])
        top_second = _union([
            [
                box["installationBoundsMeters"]["minU"],
                box["installationBoundsMeters"]["minV"],
                box["installationBoundsMeters"]["minN"],
                box["installationBoundsMeters"]["maxU"],
                box["installationBoundsMeters"]["maxV"],
                box["installationBoundsMeters"]["maxN"],
            ]
            for box in second_boxes
        ])
        top_first_dict = dict(zip(("minU", "minV", "minN", "maxU", "maxV", "maxN"), top_first))
        top_second_dict = dict(zip(("minU", "minV", "minN", "maxU", "maxV", "maxN"), top_second))
        leaf_overlap_count = sum(
            _aabb_overlap(
                first["installationBoundsMeters"],
                second["installationBoundsMeters"],
                inflation_per_side_meters,
            )
            for first in first_boxes
            for second in second_boxes
        )
        if "frame-context" in key:
            classification = "installation-contact-conditional-cad"
            installation_pairs.append(
                {
                    "pair": [first_id, second_id],
                    "reason": "The module is installed on/in JJ00; support contact is expected and frame penetration is checked after Replay.",
                }
            )
        elif key in CONDITIONAL_BREP_PAIRS:
            classification = "conditional-brep-after-multibox-overlap"
            conditional_pairs.append(
                {
                    "pair": [first_id, second_id],
                    "reason": CONDITIONAL_BREP_PAIRS[key],
                }
            )
        else:
            classification = "strict-inflated-multibox-separation"
            strict_pairs.append([first_id, second_id])
            first_leaf_boxes = objects_by_id[first_id]["leafBodyOccupancyBoxes"]
            second_leaf_boxes = objects_by_id[second_id]["leafBodyOccupancyBoxes"]
            leaf_hit_count = None
            mode = "subtree-union-boxes"
            if leaf_overlap_count and first_leaf_boxes and second_leaf_boxes:
                leaf_hit_count = sum(
                    _aabb_overlap(
                        first["installationBoundsMeters"],
                        second["installationBoundsMeters"],
                        inflation_per_side_meters,
                    )
                    for first in first_leaf_boxes
                    for second in second_leaf_boxes
                )
                mode = "partner-scoped-leaf-body-boxes"
            strict_pair_profiles.append(
                {
                    "pair": [first_id, second_id],
                    "occupancyMode": mode,
                    "prototypeInflatedLeafBodyHitCount": leaf_hit_count,
                    "passesPrototypeBaseline": leaf_hit_count in (None, 0),
                }
            )
        diagnostics.append(
            {
                "pair": [first_id, second_id],
                "classification": classification,
                "prototypeConservativeTopEnvelopeOverlap": _aabb_overlap(top_first_dict, top_second_dict),
                "prototypeInflatedSubtreeBoxHitCount": leaf_overlap_count,
            }
        )

    pair_count = math.comb(len(layout_objects), 2)
    covered_pair_count = len(strict_pairs) + len(conditional_pairs) + len(installation_pairs)
    structural_codes = {"SS00", "FF00", "LM00", "ZZ00", "GN00", "BD00", "SM00"}
    structural_leaf_complete = all(modules[code]["leafCoverageComplete"] for code in structural_codes)
    strict_baseline_clear = all(
        item["passesPrototypeBaseline"] for item in strict_pair_profiles
    )
    status = (
        "PROJECT01_OCCUPANCY_AND_COLLISION_POLICY_READY"
        if structural_leaf_complete and covered_pair_count == pair_count and strict_baseline_clear
        else "PROJECT01_OCCUPANCY_OR_PAIR_POLICY_INCOMPLETE"
    )
    return {
        "schemaVersion": "project01-module-occupancy/v1",
        "projectId": "project01",
        "status": status,
        "engineeringConfirmed": False,
        "prototypeBaselineAcceptedForCoarseLayout": True,
        "installationFrame": {"originWorldMeters": origin, "axesWorld": axes},
        "operationSideBaseline": {
            "side": "+worldX/+installationV",
            "estimatedFacePlaneWorldXMeters": first_stage_geometry["operationSideInference"]["estimatedFacePlaneWorldX"],
            "source": "JJ00 top-level AABB plus GN00/BD00/GJ00 prototype service-cluster side",
            "exactFaceCaptured": False,
            "solverBlocking": False,
        },
        "modules": modules,
        "layoutObjects": layout_objects,
        "coverage": {
            "layoutObjectCount": len(layout_objects),
            "leafCapturedStructuralModuleCount": sum(
                modules[code]["leafCoverageComplete"] for code in structural_codes
            ),
            "requiredLeafCapturedStructuralModuleCount": len(structural_codes),
            "singleBoxOrdinaryModules": ["GJ00"],
            "fixedContextTopLevelBoxes": ["JJ00", "HL00"],
        },
        "staticCollisionPolicy": {
            "pairCount": pair_count,
            "coveredPairCount": covered_pair_count,
            "aabbInflationPerSideMeters": inflation_per_side_meters,
            "strictMultiAabbPairs": strict_pairs,
            "strictPairProfiles": strict_pair_profiles,
            "conditionalBrepPairs": conditional_pairs,
            "installationContactPairs": installation_pairs,
            "solverInvokesBrep": False,
            "postReplayBrepOnly": True,
            "rule": (
                "Ordinary rigid modules must separate all inflated occupancy boxes; when a direct-subtree "
                "union is too conservative, its strict pair uses partner-scoped leaf AABBs. Sparse, portal, "
                "nested and installation-contact pairs may overlap in the broad phase and enter a "
                "leaf-level CAD B-Rep gate only after a selected layout is replayed."
            ),
        },
        "prototypePairDiagnostics": diagnostics,
        "remainingProductionGates": [
            "JJ00/HL00 leaf geometry is not yet reduced into structural keep-out boxes.",
            "GJ00 uses one conservative top-level AABB because it is an ordinary external service object.",
            "Conditional pairs require leaf-level B-Rep only after a selected solution changes relative pose.",
            "The exact engineer-selected operation face and maintenance envelope remain unconfirmed.",
        ],
    }

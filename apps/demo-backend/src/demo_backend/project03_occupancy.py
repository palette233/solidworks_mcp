"""Build Project03 multi-box occupancy and the complete static pair policy.

The solver uses inexpensive, conservative boxes.  Exact CAD B-rep is deferred
until a visually selected candidate is replayed.  Sparse/portal/nested pairs
are therefore classified separately from ordinary rigid-module pairs.
"""

from __future__ import annotations

import itertools
import math
import re
from typing import Any, Iterable


LAYOUT_OBJECTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("frame-context", ("AA00", "AF00")),
    ("transport-process-group", ("AE00",)),
    ("flip-positioning-module", ("AD00",)),
    ("gantry-motion-group", ("AB00", "AC00")),
    ("combined-service-module", ("AG00",)),
    ("calibration-module", ("AH00",)),
    ("scanner-module", ("AI00",)),
    ("glue-supply-module", ("AJ00",)),
)

# These are topology classes, not inherited coordinates.  They mirror the
# common machine architecture visible in Project03: transport through a
# gantry portal, nested flip stations, sparse scanner supports, and service
# points intentionally reached by the valve heads.
CONDITIONAL_BREP_PAIRS: dict[frozenset[str], str] = {
    frozenset(("transport-process-group", "flip-positioning-module")): (
        "AD00 positioning/rotation stations are nested around the AE00 process path."
    ),
    frozenset(("transport-process-group", "gantry-motion-group")): (
        "AE00 passes through the AB00/AC00 gantry working portal."
    ),
    frozenset(("flip-positioning-module", "gantry-motion-group")): (
        "The gantry surrounds and serves the AD00 work stations."
    ),
    frozenset(("combined-service-module", "gantry-motion-group")): (
        "The dual valve reach intentionally covers AG00 service targets inside the gantry service area."
    ),
    frozenset(("calibration-module", "gantry-motion-group")): (
        "The AH00 calibration target must lie inside the dual-valve reachable area."
    ),
    frozenset(("scanner-module", "gantry-motion-group")): (
        "AI00 and the gantry are sparse structures whose broad envelopes may overlap."
    ),
    frozenset(("scanner-module", "transport-process-group")): (
        "AI00 optical heads and supports intentionally approach the carrier path."
    ),
    frozenset(("scanner-module", "flip-positioning-module")): (
        "AI00 serves carriers located by AD00, so sparse working envelopes may overlap."
    ),
    frozenset(("flip-positioning-module", "combined-service-module")): (
        "AD00 and AG00 are adjacent process structures; conservative subtree boxes can close their real gaps."
    ),
}

_CODES = ("AA00", "AB00", "AC00", "AD00", "AE00", "AF00", "AG00", "AH00", "AI00", "AJ00")
_STRUCTURAL_CODES = {"AB00", "AC00", "AD00", "AE00", "AG00", "AH00", "AI00"}


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
    return [min(box[axis] for box in values) for axis in range(3)] + [
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
    match = re.search(r"D063A([A-J])00", str(name).upper())
    if match:
        return f"A{match.group(1)}00"
    for code in _CODES:
        if code in str(name).upper():
            return code
    return str(name)


def _subtree_key(code: str, body: dict[str, Any]) -> str:
    component = body.get("Component") or {}
    text = "/".join(str(component.get(key) or "") for key in ("HierarchyPath", "Name", "Path")).upper()
    prefix = code[1]
    configured = {
        "AB00": ("10", "20", "30", "40", "50", "60"),
        "AC00": ("10", "20", "30", "40"),
        "AD00": ("10", "20", "30", "40", "50", "60", "70", "80"),
        "AE00": ("10", "20", "30", "40", "90"),
        "AG00": ("10", "20", "30", "40"),
        "AH00": ("10",),
        "AI00": ("10",),
    }.get(code, ())
    if configured:
        matches = re.findall(rf"D063A{prefix}({'|'.join(configured)})", text)
        if matches:
            # The captured hierarchy repeats its ancestors.  The deepest
            # configured assembly token is the useful process subtree.
            return f"A{prefix}{matches[-1]}"
    return f"{code}-common-structure"


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


def _bounds_list(box: dict[str, float]) -> list[float]:
    return [box[key] for key in ("minU", "minV", "minN", "maxU", "maxV", "maxN")]


def build_project03_occupancy_and_collision_policy(
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
    poses = {_component_code(item["Name"]): item for item in top_level_poses.get("components") or []}
    poses = {code: pose for code, pose in poses.items() if code in _CODES}
    captures = _capture_index(leaf_capture_documents)

    modules: dict[str, dict[str, Any]] = {}
    for code in _CODES:
        pose = poses.get(code)
        if pose is None:
            raise ValueError(f"Project03 top-level pose is missing for {code}")
        world_box = [float(value) for value in pose["BoundingBoxWorld"]]
        top_box = _project_box(world_box, origin, axes)
        anchor = _project_point([float(value) for value in pose["Translation"]], origin, axes)
        capture = captures.get(code)
        grouped: dict[str, list[list[float]]] = {}
        leaf_boxes = []
        if capture:
            for body_index, body in enumerate(capture.get("Bodies") or []):
                bounds = body.get("BoundingBoxWorld")
                if not isinstance(bounds, list) or len(bounds) != 6:
                    continue
                world_bounds = [float(value) for value in bounds]
                grouped.setdefault(_subtree_key(code, body), []).append(world_bounds)
                projected = _project_box(world_bounds, origin, axes)
                component = body.get("Component") or {}
                leaf_boxes.append(
                    {
                        "id": f"{code}-leaf-{body_index}",
                        "component": component.get("HierarchyPath") or component.get("Name"),
                        "installationBoundsMeters": projected,
                        "localBoundsMeters": {
                            "minU": projected["minU"] - anchor["u"], "maxU": projected["maxU"] - anchor["u"],
                            "minV": projected["minV"] - anchor["v"], "maxV": projected["maxV"] - anchor["v"],
                            "minN": projected["minN"] - anchor["n"], "maxN": projected["maxN"] - anchor["n"],
                        },
                    }
                )
        source = "leaf-subtree-unions" if grouped else "conservative-top-level-aabb"
        occupancy_boxes = []
        for key, world_boxes in sorted(grouped.items()):
            projected = _project_box(_union(world_boxes), origin, axes)
            occupancy_boxes.append(
                {
                    "id": f"{code}-{key}", "subtree": key, "source": source,
                    "installationBoundsMeters": projected,
                    "localBoundsMeters": {
                        "minU": projected["minU"] - anchor["u"], "maxU": projected["maxU"] - anchor["u"],
                        "minV": projected["minV"] - anchor["v"], "maxV": projected["maxV"] - anchor["v"],
                        "minN": projected["minN"] - anchor["n"], "maxN": projected["maxN"] - anchor["n"],
                    },
                    "leafBodyCount": len(world_boxes),
                }
            )
        if not occupancy_boxes:
            occupancy_boxes.append(
                {
                    "id": f"{code}-top-level", "subtree": f"{code}-top-level", "source": source,
                    "installationBoundsMeters": top_box,
                    "localBoundsMeters": {
                        "minU": top_box["minU"] - anchor["u"], "maxU": top_box["maxU"] - anchor["u"],
                        "minV": top_box["minV"] - anchor["v"], "maxV": top_box["maxV"] - anchor["v"],
                        "minN": top_box["minN"] - anchor["n"], "maxN": top_box["maxN"] - anchor["n"],
                    },
                    "leafBodyCount": None,
                }
            )
        modules[code] = {
            "componentName": pose["Name"], "filePath": pose.get("Path"),
            "prototypeAnchorInstallationMeters": anchor,
            "topLevelBoundsInstallationMeters": top_box,
            "occupancySource": source,
            "leafCoverageComplete": bool(capture and capture.get("CoverageComplete") is True),
            "leafComponentCount": capture.get("LeafComponentCount") if capture else None,
            "bodyCount": capture.get("BodyCount") if capture else None,
            "occupancyBoxes": occupancy_boxes,
            "leafBodyOccupancyBoxes": leaf_boxes,
        }

    layout_objects = []
    for object_id, member_codes in LAYOUT_OBJECTS:
        primary = member_codes[0]
        primary_anchor = modules[primary]["prototypeAnchorInstallationMeters"]
        boxes, leaf_boxes = [], []
        for code in member_codes:
            for source_name, target in (("occupancyBoxes", boxes), ("leafBodyOccupancyBoxes", leaf_boxes)):
                for box in modules[code][source_name]:
                    installation = box["installationBoundsMeters"]
                    target.append(
                        {
                            **box, "memberCode": code,
                            "localToObjectAnchorMeters": {
                                "minU": installation["minU"] - primary_anchor["u"], "maxU": installation["maxU"] - primary_anchor["u"],
                                "minV": installation["minV"] - primary_anchor["v"], "maxV": installation["maxV"] - primary_anchor["v"],
                                "minN": installation["minN"] - primary_anchor["n"], "maxN": installation["maxN"] - primary_anchor["n"],
                            },
                        }
                    )
        layout_objects.append(
            {
                "id": object_id, "memberCodes": list(member_codes), "primaryCode": primary,
                "prototypeAnchorInstallationMeters": primary_anchor,
                "occupancyBoxCount": len(boxes), "occupancyBoxes": boxes,
                "leafBodyOccupancyBoxCount": len(leaf_boxes), "leafBodyOccupancyBoxes": leaf_boxes,
            }
        )

    objects_by_id = {item["id"]: item for item in layout_objects}
    strict_pairs, conditional_pairs, installation_pairs = [], [], []
    strict_profiles, diagnostics = [], []
    for first_id, second_id in itertools.combinations(objects_by_id, 2):
        key = frozenset((first_id, second_id))
        first_boxes = objects_by_id[first_id]["occupancyBoxes"]
        second_boxes = objects_by_id[second_id]["occupancyBoxes"]
        first_top = dict(zip(("minU", "minV", "minN", "maxU", "maxV", "maxN"), _union(_bounds_list(box["installationBoundsMeters"]) for box in first_boxes)))
        second_top = dict(zip(("minU", "minV", "minN", "maxU", "maxV", "maxN"), _union(_bounds_list(box["installationBoundsMeters"]) for box in second_boxes)))
        subtree_hit_count = sum(
            _aabb_overlap(first["installationBoundsMeters"], second["installationBoundsMeters"], inflation_per_side_meters)
            for first in first_boxes for second in second_boxes
        )
        if "frame-context" in key:
            classification = "installation-contact-conditional-cad"
            installation_pairs.append({"pair": [first_id, second_id], "reason": "The module is installed on/in AA00/AF00; intended support contact is checked only after Replay."})
        elif key in CONDITIONAL_BREP_PAIRS:
            classification = "conditional-brep-after-multibox-overlap"
            conditional_pairs.append({"pair": [first_id, second_id], "reason": CONDITIONAL_BREP_PAIRS[key]})
        else:
            classification = "strict-inflated-multibox-separation"
            strict_pairs.append([first_id, second_id])
            first_leaf = objects_by_id[first_id]["leafBodyOccupancyBoxes"]
            second_leaf = objects_by_id[second_id]["leafBodyOccupancyBoxes"]
            leaf_hit_count = None
            mode = "subtree-union-boxes"
            if subtree_hit_count and first_leaf and second_leaf:
                leaf_hit_count = sum(
                    _aabb_overlap(first["installationBoundsMeters"], second["installationBoundsMeters"], inflation_per_side_meters)
                    for first in first_leaf for second in second_leaf
                )
                mode = "partner-scoped-leaf-body-boxes"
            strict_profiles.append({"pair": [first_id, second_id], "occupancyMode": mode, "prototypeInflatedLeafBodyHitCount": leaf_hit_count, "passesPrototypeBaseline": leaf_hit_count in (None, 0)})
        diagnostics.append({"pair": [first_id, second_id], "classification": classification, "prototypeConservativeTopEnvelopeOverlap": _aabb_overlap(first_top, second_top), "prototypeInflatedSubtreeBoxHitCount": subtree_hit_count})

    pair_count = math.comb(len(layout_objects), 2)
    covered_pair_count = len(strict_pairs) + len(conditional_pairs) + len(installation_pairs)
    structural_leaf_complete = all(modules[code]["leafCoverageComplete"] for code in _STRUCTURAL_CODES)
    strict_baseline_clear = all(item["passesPrototypeBaseline"] for item in strict_profiles)
    ready = structural_leaf_complete and covered_pair_count == pair_count and strict_baseline_clear
    return {
        "schemaVersion": "project03-module-occupancy/v1", "projectId": "project03",
        "status": "PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY" if ready else "PROJECT03_OCCUPANCY_OR_PAIR_POLICY_INCOMPLETE",
        "engineeringConfirmed": False, "prototypeBaselineAcceptedForCoarseLayout": True,
        "installationFrame": {"originWorldMeters": origin, "axesWorld": axes},
        "operationSideBaseline": {
            "side": "+worldX/+installationV",
            "estimatedFacePlaneWorldXMeters": first_stage_geometry["operationSideInference"]["estimatedFacePlaneWorldX"],
            "source": "AA00 top-level AABB plus AG00/AH00/AJ00 prototype service-cluster side",
            "exactFaceCaptured": False, "solverBlocking": False,
        },
        "modules": modules, "layoutObjects": layout_objects,
        "coverage": {
            "layoutObjectCount": len(layout_objects),
            "leafCapturedStructuralModuleCount": sum(modules[code]["leafCoverageComplete"] for code in _STRUCTURAL_CODES),
            "requiredLeafCapturedStructuralModuleCount": len(_STRUCTURAL_CODES),
            "capturedLeafBodyCount": sum(int(modules[code]["bodyCount"] or 0) for code in _STRUCTURAL_CODES),
            "singleBoxOrdinaryModules": ["AJ00"], "fixedContextTopLevelBoxes": ["AA00", "AF00"],
        },
        "staticCollisionPolicy": {
            "pairCount": pair_count, "coveredPairCount": covered_pair_count,
            "aabbInflationPerSideMeters": inflation_per_side_meters,
            "strictMultiAabbPairs": strict_pairs, "strictPairProfiles": strict_profiles,
            "conditionalBrepPairs": conditional_pairs, "installationContactPairs": installation_pairs,
            "solverInvokesBrep": False, "postReplayBrepOnly": True,
            "rule": "Ordinary rigid pairs must separate inflated multi-box occupancy. Sparse, portal, nested and installation-contact pairs may overlap in the broad phase and enter leaf-level CAD B-rep only after a selected layout is replayed.",
        },
        "prototypePairDiagnostics": diagnostics,
        "remainingProductionGates": [
            "AA00/AF00 are fixed installation context and currently use conservative top-level boxes.",
            "AJ00 uses one conservative top-level AABB because no leaf capture is required for the coarse ordinary external service object.",
            "Conditional pairs require leaf-level B-rep only after a selected solution changes relative pose.",
            "The exact engineer-selected operation face and maintenance envelope remain unconfirmed.",
        ],
    }

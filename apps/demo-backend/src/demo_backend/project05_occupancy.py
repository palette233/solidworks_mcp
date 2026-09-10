"""Build the Project05 occupancy evidence and complete object-pair policy.

The pair taxonomy is available before every leaf capture finishes.  Missing
leaf geometry remains explicit: conservative top-level boxes are placeholders
and never promote the Project05 solver to ready on their own.
"""

from __future__ import annotations

import itertools
import math
import re
from typing import Any, Iterable


LAYOUT_OBJECTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("frame-context", ("A000", "E000")),
    ("transport-process-group", ("D000",)),
    ("lift-positioning-module", ("K000",)),
    ("gantry-motion-group", ("B000", "Z000")),
    ("scanner-module", ("F000",)),
    ("calibration-weighing-module", ("G000",)),
    ("product-ccd-module", ("M000",)),
    ("cleaning-module", ("N000",)),
    ("drain-module", ("P000",)),
)

CONDITIONAL_BREP_PAIRS: dict[frozenset[str], str] = {
    frozenset(("transport-process-group", "lift-positioning-module")): (
        "K000 lift stations are nested around the D000 carrier path."
    ),
    frozenset(("transport-process-group", "gantry-motion-group")): (
        "D000 passes through the B000/Z000 gantry working portal."
    ),
    frozenset(("lift-positioning-module", "gantry-motion-group")): (
        "The gantry surrounds and serves the K000 work stations."
    ),
    frozenset(("scanner-module", "transport-process-group")): (
        "F000 optical heads approach the D000 buffer barcode station."
    ),
    frozenset(("scanner-module", "gantry-motion-group")): (
        "F000 and the gantry are sparse structures whose broad envelopes may overlap."
    ),
    frozenset(("scanner-module", "lift-positioning-module")): (
        "F000 serves carriers positioned along the D000/K000 process path; sparse support envelopes may overlap."
    ),
    frozenset(("scanner-module", "product-ccd-module")): (
        "F000 and M000 are sparse optical structures aligned to the same transport lane."
    ),
    frozenset(("product-ccd-module", "transport-process-group")): (
        "M000 observes products on D000, so optical/support envelopes may overlap."
    ),
    frozenset(("product-ccd-module", "lift-positioning-module")): (
        "M000 observes products located by K000 at the two work positions."
    ),
    frozenset(("product-ccd-module", "gantry-motion-group")): (
        "M000 is installed inside or beside the gantry working channel."
    ),
    frozenset(("calibration-weighing-module", "gantry-motion-group")): (
        "G000 service targets must lie inside the dual-valve reachable area."
    ),
    frozenset(("cleaning-module", "gantry-motion-group")): (
        "N000 cleaning target must lie inside the dual-valve reachable area."
    ),
    frozenset(("drain-module", "gantry-motion-group")): (
        "P000 drain targets must lie inside the dual-valve reachable area."
    ),
}

_REQUIRED_CODES = {code for _, codes in LAYOUT_OBJECTS for code in codes}


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _corners(bounds: list[float]) -> list[list[float]]:
    if len(bounds) != 6:
        raise ValueError("AABB must contain six coordinates")
    return [
        [x, y, z]
        for x in (float(bounds[0]), float(bounds[3]))
        for y in (float(bounds[1]), float(bounds[4]))
        for z in (float(bounds[2]), float(bounds[5]))
    ]


def _project_box(bounds: list[float], frame: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in frame["originWorldMeters"]]
    axes = {
        "U": frame["flowAxisWorld"],
        "V": frame["transverseAxisWorld"],
        "N": frame["upAxisWorld"],
    }
    projected = {
        axis: [_dot([point[i] - origin[i] for i in range(3)], vector) for point in _corners(bounds)]
        for axis, vector in axes.items()
    }
    return {
        "minU": min(projected["U"]), "maxU": max(projected["U"]),
        "minV": min(projected["V"]), "maxV": max(projected["V"]),
        "minN": min(projected["N"]), "maxN": max(projected["N"]),
    }


def _code(value: str) -> str | None:
    match = re.search(r"(?:254098|251093)([A-Z]000)", str(value).upper())
    return match.group(1) if match else None


def _overlap(first: dict[str, float], second: dict[str, float], inflation: float = 0.0) -> bool:
    return all(
        first[f"max{axis}"] + inflation >= second[f"min{axis}"] - inflation
        and second[f"max{axis}"] + inflation >= first[f"min{axis}"] - inflation
        for axis in "UVN"
    )


def build_project05_occupancy_and_collision_policy(
    top_level_poses: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    k000_world_capture: dict[str, Any] | None = None,
    *,
    inflation_per_side_meters: float = 0.001,
) -> dict[str, Any]:
    frame = first_stage_geometry["installationFrame"]
    poses: dict[str, dict[str, Any]] = {}
    for pose in top_level_poses.get("components") or []:
        bounds = pose.get("BoundingBoxWorld")
        code = _code(pose.get("Name") or "")
        if code in _REQUIRED_CODES and isinstance(bounds, list) and len(bounds) == 6:
            if code in poses:
                raise ValueError(f"Multiple active Project05 poses found for {code}")
            poses[code] = pose
    missing = sorted(_REQUIRED_CODES - set(poses))
    if missing:
        raise ValueError(f"Project05 active top-level poses missing: {missing}")

    modules: dict[str, dict[str, Any]] = {}
    for code in sorted(_REQUIRED_CODES):
        pose = poses[code]
        top_box = _project_box([float(value) for value in pose["BoundingBoxWorld"]], frame)
        boxes = [{
            "id": f"{code}-top-level",
            "source": "conservative-top-level-aabb",
            "installationBoundsMeters": top_box,
            "leafBodyCount": None,
        }]
        leaf_complete = False
        leaf_body_count = 0
        if code == "K000" and k000_world_capture:
            if not k000_world_capture.get("coverageComplete"):
                raise ValueError("Project05 K000 world capture is incomplete")
            grouped: dict[str, list[list[float]]] = {}
            for body in k000_world_capture.get("bodies") or []:
                component = body.get("Component") or {}
                hierarchy = str(component.get("HierarchyPath") or component.get("Name") or "")
                bounds = body.get("BoundingBoxWorld")
                if isinstance(bounds, list) and len(bounds) == 6:
                    grouped.setdefault(hierarchy.split("/")[0], []).append([float(v) for v in bounds])
            boxes = []
            for subtree, values in sorted(grouped.items()):
                union = [min(box[i] for box in values) for i in range(3)] + [
                    max(box[i + 3] for box in values) for i in range(3)
                ]
                boxes.append({
                    "id": f"K000-{subtree}",
                    "subtree": subtree,
                    "source": "complete-leaf-subtree-union",
                    "installationBoundsMeters": _project_box(union, frame),
                    "leafBodyCount": len(values),
                })
            leaf_complete = True
            leaf_body_count = sum(int(item["leafBodyCount"] or 0) for item in boxes)
        modules[code] = {
            "componentName": pose["Name"],
            "filePath": pose.get("Path"),
            "topLevelBoundsInstallationMeters": top_box,
            "leafCoverageComplete": leaf_complete,
            "leafBodyCount": leaf_body_count,
            "occupancySource": "complete-leaf-subtree-union" if leaf_complete else "conservative-top-level-aabb",
            "occupancyBoxes": boxes,
        }

    layout_objects = []
    for object_id, member_codes in LAYOUT_OBJECTS:
        boxes = [
            {**box, "memberCode": code}
            for code in member_codes
            for box in modules[code]["occupancyBoxes"]
        ]
        layout_objects.append({
            "id": object_id,
            "memberCodes": list(member_codes),
            "occupancyBoxes": boxes,
            "leafCoverageComplete": all(modules[code]["leafCoverageComplete"] for code in member_codes),
        })

    by_id = {item["id"]: item for item in layout_objects}
    strict_pairs, conditional_pairs, installation_pairs, diagnostics = [], [], [], []
    for first_id, second_id in itertools.combinations(by_id, 2):
        key = frozenset((first_id, second_id))
        if "frame-context" in key:
            classification = "installation-contact-conditional-cad"
            installation_pairs.append({
                "pair": [first_id, second_id],
                "reason": "The module is mounted on/in A000/E000; intended support contact is audited after Replay.",
            })
        elif key in CONDITIONAL_BREP_PAIRS:
            classification = "conditional-brep-after-multibox-overlap"
            conditional_pairs.append({"pair": [first_id, second_id], "reason": CONDITIONAL_BREP_PAIRS[key]})
        else:
            classification = "strict-inflated-multibox-separation"
            strict_pairs.append([first_id, second_id])
        hit_count = sum(
            _overlap(a["installationBoundsMeters"], b["installationBoundsMeters"], inflation_per_side_meters)
            for a in by_id[first_id]["occupancyBoxes"]
            for b in by_id[second_id]["occupancyBoxes"]
        )
        diagnostics.append({
            "pair": [first_id, second_id],
            "classification": classification,
            "prototypeInflatedBoxHitCount": hit_count,
            "geometryCompleteForBothObjects": (
                by_id[first_id]["leafCoverageComplete"] and by_id[second_id]["leafCoverageComplete"]
            ),
        })

    pair_count = math.comb(len(layout_objects), 2)
    covered = len(strict_pairs) + len(conditional_pairs) + len(installation_pairs)
    complete_codes = sorted(code for code, item in modules.items() if item["leafCoverageComplete"])
    return {
        "schemaVersion": "project05-module-occupancy/v1",
        "projectId": "project05",
        "status": "PROJECT05_COLLISION_POLICY_READY_OCCUPANCY_PARTIAL",
        "engineeringConfirmed": False,
        "coarseDisplayUsable": True,
        "solverOccupancyReady": len(complete_codes) == len(_REQUIRED_CODES),
        "installationFrame": frame,
        "modules": modules,
        "layoutObjects": layout_objects,
        "coverage": {
            "layoutObjectCount": len(layout_objects),
            "requiredModuleCount": len(_REQUIRED_CODES),
            "leafCompleteModuleCodes": complete_codes,
            "leafCompleteModuleCount": len(complete_codes),
            "capturedLeafBodyCount": sum(item["leafBodyCount"] for item in modules.values()),
        },
        "staticCollisionPolicy": {
            "pairCount": pair_count,
            "coveredPairCount": covered,
            "pairPolicyComplete": covered == pair_count,
            "aabbInflationPerSideMeters": inflation_per_side_meters,
            "strictMultiAabbPairs": strict_pairs,
            "conditionalBrepPairs": conditional_pairs,
            "installationContactPairs": installation_pairs,
            "solverInvokesBrep": False,
            "postReplayBrepOnly": True,
        },
        "prototypePairDiagnostics": diagnostics,
        "interpretationLimits": [
            "Only K000 currently has complete leaf-derived multi-box occupancy.",
            "Other top-level AABBs are display placeholders and cannot certify strict collision clearance.",
            "Pair taxonomy is complete, but solver occupancy remains gated until the required structural captures are available.",
        ],
    }

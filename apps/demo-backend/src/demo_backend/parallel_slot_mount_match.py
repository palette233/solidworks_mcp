"""Bounded two-hole / two-parallel-slot geometry, in metres.

This is a candidate finder, not a mechanical compatibility authorizer. Hole
purpose and finite support must still be checked before building a CAD graph.
No prototype transform is an input to the placement parameter calculation.
"""
from __future__ import annotations

import math


def slot_pair_positions(hole_spacing: float, *, slot_spacing: float = .082,
                        slot_travel: float = .05, end_margin: float = .002) -> dict:
    """Choose symmetric travel positions with an explicit reserve at both ends.

    Hole spacing is measured *in the support plane*. Rotating the module is
    allowed, hence it need not equal the transverse slot centreline spacing.
    Two mirror orientations exist and must not be silently conflated.
    """
    values = (hole_spacing, slot_spacing, slot_travel, end_margin)
    if not all(math.isfinite(v) for v in values) or min(values[:3]) <= 0:
        raise ValueError("finite positive lengths required")
    if not 0 <= end_margin < slot_travel / 2:
        raise ValueError("invalid slot end reserve")
    if hole_spacing < slot_spacing - 1e-9:
        return {"fits": False, "reason": "hole_pair_shorter_than_slot_spacing"}
    delta = math.sqrt(max(0, hole_spacing ** 2 - slot_spacing ** 2))
    available = slot_travel - 2 * end_margin
    if delta > available + 1e-9:
        return {"fits": False, "reason": "insufficient_along_slot_travel",
                "requiredAlongDifferenceMeters": delta,
                "availableAlongDifferenceMeters": available}
    low, high = end_margin, slot_travel - end_margin - delta
    first = (low + high) / 2
    return {"fits": True, "reason": "two_slot_centerlines_match",
            "holePairSpacingMeters": hole_spacing,
            "alongDifferenceMeters": delta,
            "firstSlotFeasibleIntervalMeters": [low, high],
            "selectedPositionsFromStartMeters": [first, first + delta],
            "minimumEndReserveMeters": first,
            "angleToHolePairDegrees": math.degrees(math.atan2(delta, slot_spacing)),
            "parameterPolicy": "midpoint_of_common_feasible_interval",
            "endMarginMeters": end_margin,
            "positionSource": "target_hole_geometry_and_explicit_design_policy"}


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _unit(a):
    length = math.sqrt(_dot(a, a))
    if not math.isfinite(length) or length < 1e-10:
        raise ValueError("invalid geometry direction")
    return [x / length for x in a]


def screen_catalog(catalog: dict, *, slot_width: float = .0066,
                   slot_spacing: float = .082, slot_travel: float = .05,
                   end_margin: float = .002) -> dict:
    """Screen same-body holes meeting an axis-aligned support plane.

    Only horizontal world-Y support surfaces are considered for these A600
    catalogs. Leaf local axes can differ. Exported surface normals are not used
    to infer the outward side: the intended side needs source mate evidence.
    FaceBox is only a broad-phase support check, explicitly not B-rep proof.
    """
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise ValueError("unsupported face catalog")
    rows = catalog.get("Endpoints") or []
    groups = {}
    for row in rows:
        ep = row["Endpoint"]
        groups.setdefault((ep["RelativeLeafHierarchyPath"], ep["BodyIndex"]), []).append(row)
    candidates = []
    seen = set()
    counts = {"planeCount": 0, "holeCount": 0, "pairCount": 0,
              "travelRejectedCount": 0}
    for (leaf, body), group in groups.items():
        planes = [r for r in group if r["Endpoint"].get("SurfaceType") == "Plane"
                  and abs(r["Endpoint"].get("FaceNormalWorld", [0, 0, 0])[1]) > .99999
                  and r["Endpoint"].get("FaceArea", 0) > .008]
        for plane in planes:
            ep = plane["Endpoint"]
            box, normal = ep["FaceBoxLocal"], _unit(ep["FaceNormalLocal"])
            axial = max(range(3), key=lambda k: abs(normal[k]))
            planar = [k for k in range(3) if k != axial]
            if abs(normal[axial]) < .99999 or abs(box[axial+3]-box[axial]) > 1e-7:
                continue
            counts["planeCount"] += 1
            holes = []
            for row in group:
                hp = row["Endpoint"]
                if hp.get("SurfaceType") != "Cylinder":
                    continue
                radius = hp["CylinderRadius"]
                if not .001 <= radius <= slot_width / 2:
                    continue
                if abs(_dot(_unit(hp["CylinderAxisLocal"]), normal)) < .99999:
                    continue
                origin, hb = hp["CylinderOriginLocal"], hp["FaceBoxLocal"]
                if not hb[axial] - 1e-7 <= box[axial] <= hb[axial+3] + 1e-7:
                    continue
                # A complete round axis at the support surface, not an isolated
                # semicircular slot end or a circular boss guessed from a radius.
                if any(abs((hb[k+3] - hb[k]) - 2*radius) > 1e-6 for k in planar):
                    continue
                height = hb[axial+3] - hb[axial]
                expected_area = 2 * math.pi * radius * height
                if height <= 1e-7 or not math.isclose(
                    hp.get("FaceArea", -1), expected_area, rel_tol=1e-4, abs_tol=1e-10
                ):
                    continue
                if not all(box[k]+radius <= origin[k] <= box[k+3]-radius for k in planar):
                    continue
                holes.append(row)
            counts["holeCount"] += len(holes)
            for i, a in enumerate(holes):
                for b in holes[i+1:]:
                    pa, pb = a["Endpoint"], b["Endpoint"]
                    delta = [pb["CylinderOriginLocal"][k]-pa["CylinderOriginLocal"][k]
                             for k in planar]
                    distance = math.hypot(*delta)
                    if distance < slot_spacing-1e-9 or distance > math.hypot(slot_spacing, slot_travel)+1e-9:
                        continue
                    counts["pairCount"] += 1
                    positions = slot_pair_positions(distance, slot_spacing=slot_spacing,
                        slot_travel=slot_travel, end_margin=end_margin)
                    if not positions["fits"]:
                        counts["travelRejectedCount"] += 1
                    key = (plane["EndpointId"], *sorted((a["EndpointId"], b["EndpointId"])))
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append({"leafHierarchyPath": leaf, "bodyIndex": body,
                        "supportEndpointId": plane["EndpointId"],
                        "supportFaceIndex": ep["FaceIndexInBody"],
                        "supportFaceBoxLocalMeters": box,
                        "holeEndpointIds": [a["EndpointId"], b["EndpointId"]],
                        "holeFaceIndices": [pa["FaceIndexInBody"], pb["FaceIndexInBody"]],
                        "holeOriginsLocalMeters": [pa["CylinderOriginLocal"], pb["CylinderOriginLocal"]],
                        "holeRadiiMeters": [pa["CylinderRadius"], pb["CylinderRadius"]],
                        "positions": positions,
                        "cadLaunchAllowed": False,
                        "supportExtentStatus": "axis_intersection_only_footprint_pending",
                        "targetHolePurposeConfirmed": False})
    return {"scope": "same_body_horizontal_support_and_round_axes",
            "leafCount": len({key[0] for key in groups}), "bodyCount": len(groups),
            "endpointCount": len(rows), "counts": counts,
            "candidates": candidates, "cadLaunchAllowed": False}

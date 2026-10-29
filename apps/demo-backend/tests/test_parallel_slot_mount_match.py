"""Synthetic geometry checks for candidate-only parallel-slot discovery."""

import math

import pytest

from demo_backend.parallel_slot_mount_match import screen_catalog, slot_pair_positions


def _catalog(spacing=.082):
    """An 18 mm plate whose local Z is the assembly's vertical world Y."""
    leaf = "base/static-mount-plate-1"
    common = {"RelativeLeafHierarchyPath": leaf, "BodyIndex": 0}
    support = {
        "EndpointId": "support",
        "Endpoint": {
            **common,
            "SurfaceType": "Plane",
            "FaceIndexInBody": 8,
            "FaceNormalLocal": [0, 0, -1],
            "FaceNormalWorld": [0, -1, 0],
            "FaceArea": .16,
            "FaceBoxLocal": [-.2, -.2, .018, .2, .2, .018],
        },
    }
    rows = [support]
    for index, x in enumerate((-spacing / 2, spacing / 2)):
        radius = .0021
        rows.append({
            "EndpointId": f"hole-{index}",
            "Endpoint": {
                **common,
                "SurfaceType": "Cylinder",
                "FaceIndexInBody": 93 + index,
                "CylinderRadius": radius,
                "CylinderAxisLocal": [0, 0, 1],
                "CylinderOriginLocal": [x, 0, .018],
                "FaceArea": 2 * math.pi * radius * .018,
                "FaceBoxLocal": [x - radius, -radius, 0,
                                 x + radius, radius, .018],
            },
        })
    return {"SchemaVersion": "solidworks-face-endpoint-catalog/v1", "Endpoints": rows}


def test_equal_transverse_spacing_selects_midpoints_without_a_prototype_pose():
    result = slot_pair_positions(.082)
    assert result["fits"] is True
    assert result["alongDifferenceMeters"] == pytest.approx(0)
    assert result["selectedPositionsFromStartMeters"] == pytest.approx([.025, .025])
    assert result["firstSlotFeasibleIntervalMeters"] == pytest.approx([.002, .048])
    assert result["minimumEndReserveMeters"] == pytest.approx(.025)
    assert result["angleToHolePairDegrees"] == pytest.approx(0)
    assert result["positionSource"] == "target_hole_geometry_and_explicit_design_policy"


def test_rotated_pair_uses_transverse_spacing_and_explicit_along_slot_parameters():
    # Actual plate candidate: 36.5 mm by 78 mm separation, not an 82 mm round pair.
    separation = math.hypot(.0365, .078)
    result = slot_pair_positions(separation)
    along = math.sqrt(separation ** 2 - .082 ** 2)
    assert separation == pytest.approx(.086117652081324)
    assert result["fits"] is True
    assert along == pytest.approx(.026310644233845)
    assert result["alongDifferenceMeters"] == pytest.approx(along)
    assert result["selectedPositionsFromStartMeters"] == pytest.approx(
        [(.05 - along) / 2, (.05 + along) / 2]
    )
    low, high = result["firstSlotFeasibleIntervalMeters"]
    assert high - low == pytest.approx(.05 - .004 - along)
    assert .002 <= low <= result["selectedPositionsFromStartMeters"][0] <= high
    assert math.hypot(.082, along) == pytest.approx(separation)


def test_96mm_pair_is_rejected_with_two_mm_reserve_but_geometrically_fits_without_it():
    rejected = slot_pair_positions(.096)
    assert rejected["fits"] is False
    assert rejected["reason"] == "insufficient_along_slot_travel"
    assert rejected["requiredAlongDifferenceMeters"] == pytest.approx(.04991993589739474)
    assert rejected["availableAlongDifferenceMeters"] == pytest.approx(.046)
    assert slot_pair_positions(.096, end_margin=0)["fits"] is True


@pytest.mark.parametrize("spacing,reason", [
    (.081, "hole_pair_shorter_than_slot_spacing"),
    (.1, "insufficient_along_slot_travel"),
])
def test_too_close_and_too_far_holes_are_not_relaxed_to_fit(spacing, reason):
    result = slot_pair_positions(spacing)
    assert result["fits"] is False
    assert result["reason"] == reason


@pytest.mark.parametrize("kwargs", [
    {"hole_spacing": math.nan},
    {"hole_spacing": math.inf},
    {"hole_spacing": -.082},
    {"hole_spacing": .082, "slot_spacing": math.nan},
    {"hole_spacing": .082, "slot_travel": math.nan},
    {"hole_spacing": .082, "end_margin": math.nan},
    {"hole_spacing": .082, "end_margin": -.001},
    {"hole_spacing": .082, "end_margin": .025},
])
def test_invalid_lengths_and_reserves_fail_explicitly(kwargs):
    with pytest.raises(ValueError):
        slot_pair_positions(**kwargs)


def test_screen_accepts_local_z_plate_but_never_authorizes_cad_or_hole_purpose():
    report = screen_catalog(_catalog())
    assert report["leafCount"] == report["bodyCount"] == 1
    assert report["counts"]["planeCount"] == 1
    assert report["counts"]["holeCount"] == 2
    assert report["counts"]["pairCount"] == 1
    candidate, = report["candidates"]
    assert candidate["holeEndpointIds"] == ["hole-0", "hole-1"]
    assert candidate["supportEndpointId"] == "support"
    assert candidate["positions"]["selectedPositionsFromStartMeters"] == pytest.approx([.025, .025])
    assert candidate["supportExtentStatus"] == "axis_intersection_only_footprint_pending"
    assert candidate["targetHolePurposeConfirmed"] is False
    assert candidate["cadLaunchAllowed"] is report["cadLaunchAllowed"] is False


def test_screen_preserves_96mm_rejection_as_evidence_not_an_authorized_candidate():
    report = screen_catalog(_catalog(.096))
    candidate, = report["candidates"]
    assert report["counts"]["travelRejectedCount"] == 1
    assert candidate["positions"]["fits"] is False
    assert candidate["cadLaunchAllowed"] is report["cadLaunchAllowed"] is False


def test_screen_rejects_partial_circumference_even_when_bounds_span_the_full_diameter():
    catalog = _catalog()
    # A 270-degree trimmed cylinder can have the same XYZ box as a complete one.
    # Radius and box alone must not upgrade it to an independent round hole.
    catalog["Endpoints"][2]["Endpoint"]["FaceArea"] *= .75
    report = screen_catalog(catalog)
    assert report["counts"]["holeCount"] == 1
    assert report["candidates"] == []
    assert report["cadLaunchAllowed"] is False


def test_screen_rejects_hole_missing_cylinder_area_evidence():
    catalog = _catalog()
    del catalog["Endpoints"][2]["Endpoint"]["FaceArea"]
    report = screen_catalog(catalog)
    assert report["counts"]["holeCount"] == 1
    assert report["candidates"] == []
    assert report["cadLaunchAllowed"] is False


@pytest.mark.parametrize("hole_spacing", [.06, .09])
def test_screen_uses_explicit_source_slot_spacing_and_travel(hole_spacing):
    report = screen_catalog(_catalog(hole_spacing), slot_spacing=.06, slot_travel=.08)
    candidate, = report["candidates"]
    along = math.sqrt(max(0, hole_spacing ** 2 - .06 ** 2))
    assert candidate["positions"]["fits"] is True
    assert candidate["positions"]["selectedPositionsFromStartMeters"] == pytest.approx(
        [(.08 - along) / 2, (.08 + along) / 2]
    )
    assert candidate["positions"]["holePairSpacingMeters"] == pytest.approx(hole_spacing)
    assert candidate["cadLaunchAllowed"] is report["cadLaunchAllowed"] is False


@pytest.mark.parametrize("mutation", [
    "nonparallel_axis", "semicircular_endpoint", "support_height_mismatch",
    "different_body", "different_leaf", "outside_support_bounds", "nonhorizontal_world_plane",
])
def test_invalid_hole_or_support_evidence_does_not_form_a_pair(mutation):
    catalog = _catalog()
    plane = catalog["Endpoints"][0]["Endpoint"]
    second = catalog["Endpoints"][2]["Endpoint"]
    if mutation == "nonparallel_axis":
        second["CylinderAxisLocal"] = [0, 1, 0]
    elif mutation == "semicircular_endpoint":
        second["FaceBoxLocal"][3] = second["CylinderOriginLocal"][0]
    elif mutation == "support_height_mismatch":
        plane["FaceBoxLocal"][2] = plane["FaceBoxLocal"][5] = .020
    elif mutation == "different_body":
        second["BodyIndex"] = 1
    elif mutation == "different_leaf":
        second["RelativeLeafHierarchyPath"] = "base/other-plate-1"
    elif mutation == "outside_support_bounds":
        plane["FaceBoxLocal"][3] = .03
    else:
        plane["FaceNormalWorld"] = [1, 0, 0]
    report = screen_catalog(catalog)
    assert report["candidates"] == []
    assert report["cadLaunchAllowed"] is False


def test_screen_rejects_invalid_schema():
    with pytest.raises(ValueError, match="unsupported face catalog"):
        screen_catalog({"Endpoints": []})


def test_screen_rejects_invalid_axis_instead_of_issuing_a_candidate():
    catalog = _catalog()
    catalog["Endpoints"][2]["Endpoint"]["CylinderAxisLocal"] = [0, 0, math.nan]
    with pytest.raises(ValueError, match="invalid geometry direction"):
        screen_catalog(catalog)

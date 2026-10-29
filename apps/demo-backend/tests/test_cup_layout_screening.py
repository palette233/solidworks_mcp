from copy import deepcopy
import pytest
from demo_backend.cup_function_point import compare_two_cup_layouts


def pair(spacing):
    return [{"pointId": str(i), "centerModuleLocalMeters": [i*spacing, 0, 0],
             "openingNormalModuleLocal": [0,1,0], "internalGeometryRigid": True} for i in range(2)]


def test_90_and_130_mm_cannot_match_both_centers():
    result = compare_two_cup_layouts(pair(.13), pair(.09))
    assert result["centerAlignmentPossible"] is False
    assert result["minimumMaximumCenterErrorLowerBoundMeters"] == pytest.approx(.02)
    assert not result["cadLaunchAllowed"] and result["functionalPassed"] is None


def test_equal_spacing_is_only_a_necessary_condition_and_frame_independent():
    target = pair(.13)
    for point in target:
        x = point["centerModuleLocalMeters"][0]
        point["centerModuleLocalMeters"] = [1, 2, 3+x]
    result = compare_two_cup_layouts(pair(.13), list(reversed(target)))
    assert result["status"] == "necessary_spacing_check_passed"
    assert result["centerAlignmentPossible"] is None


@pytest.mark.parametrize("case", ["count", "duplicate", "flexible", "axes"])
def test_unknown_geometry_does_not_claim_incompatibility(case):
    points = deepcopy(pair(.13))
    if case == "count": points.pop()
    if case == "duplicate": points[1]["pointId"] = points[0]["pointId"]
    if case == "flexible": points[0]["internalGeometryRigid"] = False
    if case == "axes": points[0]["openingNormalModuleLocal"] = [1,0,0]
    assert compare_two_cup_layouts(points, pair(.09))["status"] == "not_evaluated"

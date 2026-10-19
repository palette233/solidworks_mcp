from demo_backend.project02_prototype_dynamic_estimates import (
    build_estimate,
    evaluate_vertical_stroke_scenarios,
    expand_function_zone,
    union_box,
)


def test_union_box():
    assert union_box([[0, 1, 2, 3, 4, 5], [-1, 2, 1, 2, 8, 4]]) == [-1, 1, 1, 3, 8, 5]


def test_function_zone_expands_only_operation_side_and_height():
    assert expand_function_zone([1, 2, 3, 4, 5, 6], operator_outward_meters=0.1, service_height_meters=4) == [0.9, 2.0, 3.0, 4.0, 6.0, 6.0]


def test_build_estimate_keeps_production_closed():
    request = {
        "moduleSemantics": {
            "FL9A24D062A100.001-1": {
                "regions": {
                    "leftValveReach": {"minU": 0, "maxU": 1, "minV": 2, "maxV": 3},
                    "rightValveReach": {"minU": 0.1, "maxU": 1.1, "minV": 2, "maxV": 3},
                    "dualValveReach": {"minU": 0.1, "maxU": 1, "minV": 2, "maxV": 3},
                }
            },
            "FL9A24D062A800.001-1": {"parameters": {"interactionHeightRangeMeters": [0, 0.38]}},
            "FL9A24D062A500.001-1": {"parameters": {"interactionHeightRangeMeters": [0, 0.258]}},
            "FL9A24D062A300.001-1": {"parameters": {"interactionHeightRangeMeters": [0, 0.209]}},
        }
    }
    capture = {
        "Bodies": [
            {"Component": {"Name": "A710"}, "BoundingBoxWorld": [0, 0, 0, 1, 1, 1]},
            {"Component": {"Name": "A720"}, "BoundingBoxWorld": [1, 0, 0, 2, 1, 1]},
            {"Component": {"Name": "A730"}, "BoundingBoxWorld": [3, 0, 0, 4, 1, 1]},
        ]
    }
    result = build_estimate(
        request,
        capture,
        static_closure_passed=True,
        service_access_passed=True,
        reach_audit_passed=True,
    )
    assert result["gate"]["prototypeEstimatedDynamicDemoPassed"] is True
    assert result["gate"]["productionDynamicReleaseAllowed"] is False
    assert result["a700"]["modelKind"] == "single-static-installation-with-functional-zones"
    assert round(result["a100"]["minimumRequiredVerticalStrokeMeters"], 4) == 0.2455
    assert round(result["a100"]["verticalStrokeEstimateMeters"], 4) == 0.2655


def test_vertical_stroke_sensitivity_rejects_short_case_and_accepts_nominal():
    estimate = {"a100": {"minimumRequiredVerticalStrokeMeters": 0.2455}}
    result = evaluate_vertical_stroke_scenarios(estimate, [0.2, 0.2455, 0.2655, 0.3])
    assert [row["accepted"] for row in result["scenarios"]] == [False, True, True, True]

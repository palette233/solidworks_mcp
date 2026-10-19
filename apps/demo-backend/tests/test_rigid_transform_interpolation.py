from __future__ import annotations

import math

import pytest

from demo_backend.rigid_transform_interpolation import (
    build_rigid_interpolation,
    build_screw_interpolation,
    compose_transform,
    rebase_parent_frame_motion,
    relative_transform,
)


def transform_about_z(angle_degrees: float, pivot_x: float = 1.0) -> list[float]:
    angle = math.radians(angle_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    rotation = [cosine, sine, 0.0, -sine, cosine, 0.0, 0.0, 0.0, 1.0]
    translation = [pivot_x * (1.0 - cosine), -pivot_x * sine, 0.0]
    return [*rotation, *translation, 1.0, 0.0, 0.0, 0.0]


def test_screw_interpolation_reproduces_endpoints_and_midpoint() -> None:
    result = build_screw_interpolation(
        transform_about_z(0.0),
        transform_about_z(25.0),
        sample_angles_degrees=[0.0, 5.0, 10.0, 15.0, 20.0, 25.0],
    )
    assert abs(result["recoveredAngleDegrees"] - 25.0) < 1e-9
    assert result["endpointError"]["maxRotationElementError"] < 1e-12
    assert result["endpointError"]["translationErrorMeters"] < 1e-12
    expected_mid = transform_about_z(10.0)
    actual_mid = result["samples"][2]["transform"]
    assert max(abs(a - b) for a, b in zip(actual_mid, expected_mid)) < 1e-12


def test_rigid_interpolation_supports_linked_linear_slider() -> None:
    start = transform_about_z(0.0)
    end = list(start)
    end[9:12] = [0.025, -0.0125, 0.0]

    result = build_rigid_interpolation(
        start,
        end,
        sample_angles_degrees=[0.0, 5.0, 10.0, 15.0, 20.0, 25.0],
    )

    assert result["motionType"] == "linear-translation"
    assert all(
        abs(actual - expected) < 1e-12
        for actual, expected in zip(
            result["samples"][2]["transform"][9:12],
            [0.01, -0.005, 0.0],
        )
    )
    assert result["endpointError"]["maxRotationElementError"] < 1e-12
    assert result["endpointError"]["translationErrorMeters"] < 1e-12


def test_rigid_interpolation_maps_mechanism_parameter_to_component_rotation() -> None:
    result = build_rigid_interpolation(
        transform_about_z(0.0),
        transform_about_z(25.0),
        sample_angles_degrees=[0.0, 5.0, 25.0],
        endpoint_parameter_degrees=25.0,
    )

    assert result["motionType"] == "screw"
    assert result["samples"][1]["mechanismParameterDegrees"] == 5.0
    assert max(
        abs(a - b)
        for a, b in zip(result["samples"][1]["transform"], transform_about_z(5.0))
    ) < 1e-12


def test_compose_and_relative_transform_round_trip() -> None:
    parent = [
        0.0, 0.0, 1.0,
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        -0.7835384568873234, -0.29537103655958147, -0.06449421656520789,
        1.0, 0.0, 0.0, 0.0,
    ]
    child = [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
        0.017790935686556264, 0.1693750586385744, 0.06321005883184065,
        1.0, 0.0, 0.0, 0.0,
    ]

    world = compose_transform(parent, child)

    assert world[9:12] == pytest.approx(
        [-0.614163398248749, -0.232160977727741, -0.046703280878652], abs=1e-12
    )
    assert relative_transform(parent, world) == pytest.approx(child, abs=1e-12)


def test_rebase_parent_frame_motion_preserves_motion_delta_at_corrected_start() -> None:
    original_start = transform_about_z(0.0, pivot_x=1.0)
    original_sample = transform_about_z(10.0, pivot_x=1.0)
    corrected_start = list(original_start)
    corrected_start[9:12] = [0.2, -0.1, 0.05]

    rebased = rebase_parent_frame_motion(original_start, original_sample, corrected_start)

    # The corrected origin follows the same ten-degree motion about the same
    # parent-frame pivot, while retaining its calibrated Z offset.
    angle = math.radians(10.0)
    expected_x = math.cos(angle) * 0.2 - math.sin(angle) * -0.1 + 1.0 - math.cos(angle)
    expected_y = math.sin(angle) * 0.2 + math.cos(angle) * -0.1 - math.sin(angle)
    assert rebased[9:12] == pytest.approx([expected_x, expected_y, 0.05], abs=1e-12)
    assert rebased[:9] == pytest.approx(original_sample[:9], abs=1e-12)

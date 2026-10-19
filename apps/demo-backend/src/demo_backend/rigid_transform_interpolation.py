from __future__ import annotations

import math
from typing import Any


Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]


def _dot(a: Vector, b: Vector) -> float:
    return sum(a[index] * b[index] for index in range(3))


def _cross(a: Vector, b: Vector) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _add(a: Vector, b: Vector) -> Vector:
    return tuple(a[index] + b[index] for index in range(3))  # type: ignore[return-value]


def _subtract(a: Vector, b: Vector) -> Vector:
    return tuple(a[index] - b[index] for index in range(3))  # type: ignore[return-value]


def _scale(value: Vector, factor: float) -> Vector:
    return tuple(item * factor for item in value)  # type: ignore[return-value]


def _norm(value: Vector) -> float:
    return math.sqrt(_dot(value, value))


def _transpose(matrix: Matrix) -> Matrix:
    return tuple(tuple(matrix[column][row] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def _multiply(first: Matrix, second: Matrix) -> Matrix:
    second_t = _transpose(second)
    return tuple(tuple(_dot(row, column) for column in second_t) for row in first)  # type: ignore[return-value]


def _matrix_vector(matrix: Matrix, vector: Vector) -> Vector:
    return tuple(_dot(row, vector) for row in matrix)  # type: ignore[return-value]


def _identity() -> Matrix:
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _rodrigues(axis: Vector, angle: float) -> Matrix:
    x, y, z = axis
    cosine, sine, one_minus = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    return (
        (cosine + x * x * one_minus, x * y * one_minus - z * sine, x * z * one_minus + y * sine),
        (y * x * one_minus + z * sine, cosine + y * y * one_minus, y * z * one_minus - x * sine),
        (z * x * one_minus - y * sine, z * y * one_minus + x * sine, cosine + z * z * one_minus),
    )


def _rotation_axis_angle(rotation: Matrix) -> tuple[Vector, float]:
    trace = rotation[0][0] + rotation[1][1] + rotation[2][2]
    angle = math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0)))
    if angle < 1e-9:
        raise ValueError("Endpoint transforms do not contain a measurable rotation.")
    denominator = 2.0 * math.sin(angle)
    axis = (
        (rotation[2][1] - rotation[1][2]) / denominator,
        (rotation[0][2] - rotation[2][0]) / denominator,
        (rotation[1][0] - rotation[0][1]) / denominator,
    )
    length = _norm(axis)
    if length < 1e-9:
        raise ValueError("Unable to recover a stable rotation axis.")
    return _scale(axis, 1.0 / length), angle


def _decode(transform: list[float]) -> tuple[Matrix, Vector, float, tuple[float, float, float]]:
    if len(transform) != 16 or not all(math.isfinite(float(value)) for value in transform):
        raise ValueError("Transform2 must contain 16 finite values.")
    # SolidWorks exposes local X/Y/Z axes consecutively. Use them as columns
    # of the local-to-parent rotation matrix.
    axes = (
        (float(transform[0]), float(transform[1]), float(transform[2])),
        (float(transform[3]), float(transform[4]), float(transform[5])),
        (float(transform[6]), float(transform[7]), float(transform[8])),
    )
    rotation = _transpose(axes)
    translation = (float(transform[9]), float(transform[10]), float(transform[11]))
    return rotation, translation, float(transform[12]), (
        float(transform[13]), float(transform[14]), float(transform[15])
    )


def _encode(rotation: Matrix, translation: Vector, scale: float, tail: tuple[float, float, float]) -> list[float]:
    axes = _transpose(rotation)
    return [
        *axes[0], *axes[1], *axes[2],
        *translation,
        scale,
        *tail,
    ]


def build_screw_interpolation(
    start_transform: list[float],
    end_transform: list[float],
    *,
    sample_angles_degrees: list[float],
) -> dict[str, Any]:
    start_r, start_t, start_scale, start_tail = _decode(start_transform)
    end_r, end_t, end_scale, end_tail = _decode(end_transform)
    if abs(start_scale - end_scale) > 1e-9 or abs(start_scale - 1.0) > 1e-6:
        raise ValueError("Endpoint Transform2 scales must both be one.")
    if any(abs(start_tail[index] - end_tail[index]) > 1e-9 for index in range(3)):
        raise ValueError("Endpoint Transform2 tails differ.")
    relative_r = _multiply(end_r, _transpose(start_r))
    axis, angle = _rotation_axis_angle(relative_r)
    relative_translation = _subtract(end_t, _matrix_vector(relative_r, start_t))
    axial_displacement = _dot(axis, relative_translation)
    perpendicular = _subtract(relative_translation, _scale(axis, axial_displacement))
    cotangent_half = 1.0 / math.tan(angle / 2.0)
    pivot_perpendicular = _scale(
        _add(perpendicular, _scale(_cross(axis, perpendicular), cotangent_half)),
        0.5,
    )
    samples = []
    total_degrees = math.degrees(angle)
    for requested_degrees in sample_angles_degrees:
        fraction = float(requested_degrees) / total_degrees
        if fraction < -1e-9 or fraction > 1.0 + 1e-9:
            raise ValueError("Sample angle lies outside the recovered endpoint interval.")
        partial_r = _rodrigues(axis, angle * fraction)
        partial_q = _add(
            _subtract(pivot_perpendicular, _matrix_vector(partial_r, pivot_perpendicular)),
            _scale(axis, axial_displacement * fraction),
        )
        rotation = _multiply(partial_r, start_r)
        translation = _add(_matrix_vector(partial_r, start_t), partial_q)
        samples.append(
            {
                "requestedAngleDegrees": float(requested_degrees),
                "fraction": fraction,
                "transform": _encode(rotation, translation, start_scale, start_tail),
            }
        )
    end_reconstructed = build_endpoint_error(samples[-1]["transform"], end_transform)
    return {
        "schemaVersion": "rigid-screw-interpolation/v1",
        "motionType": "screw",
        "rotationAxisParent": list(axis),
        "recoveredAngleDegrees": total_degrees,
        "pivotPointPerpendicularParentMeters": list(pivot_perpendicular),
        "axialDisplacementMeters": axial_displacement,
        "endpointError": end_reconstructed,
        "samples": samples,
    }


def build_rigid_interpolation(
    start_transform: list[float],
    end_transform: list[float],
    *,
    sample_angles_degrees: list[float],
    endpoint_parameter_degrees: float = 25.0,
) -> dict[str, Any]:
    """Interpolate a SolidWorks rigid transform across an engineering-state parameter.

    Rotating components use exact screw interpolation. Components whose endpoint
    orientations are equal use linear translation, which is required for linked
    sliders inside mechanisms such as Project03 AD20.
    """
    start_r, start_t, start_scale, start_tail = _decode(start_transform)
    end_r, end_t, end_scale, end_tail = _decode(end_transform)
    if abs(start_scale - end_scale) > 1e-9 or abs(start_scale - 1.0) > 1e-6:
        raise ValueError("Endpoint Transform2 scales must both be one.")
    if any(abs(start_tail[index] - end_tail[index]) > 1e-9 for index in range(3)):
        raise ValueError("Endpoint Transform2 tails differ.")
    if endpoint_parameter_degrees <= 0.0:
        raise ValueError("endpoint_parameter_degrees must be positive.")

    relative_r = _multiply(end_r, _transpose(start_r))
    trace = relative_r[0][0] + relative_r[1][1] + relative_r[2][2]
    angle = math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0)))
    rotation_element_delta = max(
        abs(relative_r[row][column] - _identity()[row][column])
        for row in range(3)
        for column in range(3)
    )
    # acos(trace) magnifies floating-point noise near identity. Use the matrix
    # residual as the authoritative distinction between a slider and a rotating
    # body, otherwise an unchanged orientation can appear as a ~1e-6 degree turn.
    if rotation_element_delta > 1e-8:
        result = build_screw_interpolation(
            start_transform,
            end_transform,
            sample_angles_degrees=[
                float(value) * math.degrees(angle) / endpoint_parameter_degrees
                for value in sample_angles_degrees
            ],
        )
        for sample, requested in zip(result["samples"], sample_angles_degrees):
            sample["mechanismParameterDegrees"] = float(requested)
        result["endpointParameterDegrees"] = float(endpoint_parameter_degrees)
        return result

    translation_delta = _subtract(end_t, start_t)
    samples = []
    for requested in sample_angles_degrees:
        fraction = float(requested) / endpoint_parameter_degrees
        if fraction < -1e-9 or fraction > 1.0 + 1e-9:
            raise ValueError("Sample parameter lies outside the endpoint interval.")
        translation = _add(start_t, _scale(translation_delta, fraction))
        samples.append(
            {
                "requestedAngleDegrees": 0.0,
                "mechanismParameterDegrees": float(requested),
                "fraction": fraction,
                "transform": _encode(start_r, translation, start_scale, start_tail),
            }
        )
    return {
        "schemaVersion": "rigid-translation-interpolation/v1",
        "motionType": "linear-translation",
        "rotationAxisParent": None,
        "recoveredAngleDegrees": 0.0,
        "endpointParameterDegrees": float(endpoint_parameter_degrees),
        "translationDeltaMeters": list(translation_delta),
        "endpointError": build_endpoint_error(samples[-1]["transform"], end_transform),
        "samples": samples,
    }


def build_endpoint_error(first: list[float], second: list[float]) -> dict[str, float]:
    first_r, first_t, _, _ = _decode(first)
    second_r, second_t, _, _ = _decode(second)
    return {
        "maxRotationElementError": max(
            abs(first_r[row][column] - second_r[row][column])
            for row in range(3)
            for column in range(3)
        ),
        "translationErrorMeters": _norm(_subtract(first_t, second_t)),
    }


def compose_transform(parent_transform: list[float], child_transform: list[float]) -> list[float]:
    """Compose SolidWorks local-to-parent transforms into one world transform."""
    parent_r, parent_t, parent_scale, parent_tail = _decode(parent_transform)
    child_r, child_t, child_scale, child_tail = _decode(child_transform)
    if abs(parent_scale - 1.0) > 1e-9 or abs(child_scale - 1.0) > 1e-9:
        raise ValueError("Transform composition currently requires unit scale.")
    if parent_tail != child_tail:
        raise ValueError("Transform tails differ and cannot be composed safely.")
    rotation = _multiply(parent_r, child_r)
    translation = _add(_matrix_vector(parent_r, child_t), parent_t)
    return _encode(rotation, translation, 1.0, parent_tail)


def relative_transform(parent_world_transform: list[float], child_world_transform: list[float]) -> list[float]:
    """Recover a child local transform from parent and child world transforms."""
    parent_r, parent_t, parent_scale, parent_tail = _decode(parent_world_transform)
    child_r, child_t, child_scale, child_tail = _decode(child_world_transform)
    if abs(parent_scale - 1.0) > 1e-9 or abs(child_scale - 1.0) > 1e-9:
        raise ValueError("Relative transform recovery currently requires unit scale.")
    if parent_tail != child_tail:
        raise ValueError("Transform tails differ and cannot be compared safely.")
    inverse_parent_r = _transpose(parent_r)
    rotation = _multiply(inverse_parent_r, child_r)
    translation = _matrix_vector(inverse_parent_r, _subtract(child_t, parent_t))
    return _encode(rotation, translation, 1.0, parent_tail)


def rebase_parent_frame_motion(
    original_start_transform: list[float],
    original_sample_transform: list[float],
    rebased_start_transform: list[float],
) -> list[float]:
    """Apply an observed parent-frame rigid motion to a corrected start pose.

    This is useful when a mechanism's native configuration provides the motion
    delta, but its zero-degree pose must be calibrated from a higher assembly
    context.  The result is exact at the corrected start and preserves the
    original sample's parent-frame rigid displacement.
    """
    original_r, original_t, original_scale, original_tail = _decode(original_start_transform)
    sample_r, sample_t, sample_scale, sample_tail = _decode(original_sample_transform)
    rebased_r, rebased_t, rebased_scale, rebased_tail = _decode(rebased_start_transform)
    if any(abs(scale - 1.0) > 1e-9 for scale in (original_scale, sample_scale, rebased_scale)):
        raise ValueError("Motion rebasing currently requires unit scale.")
    if original_tail != sample_tail or original_tail != rebased_tail:
        raise ValueError("Transform tails differ and cannot be rebased safely.")

    delta_r = _multiply(sample_r, _transpose(original_r))
    delta_t = _subtract(sample_t, _matrix_vector(delta_r, original_t))
    result_r = _multiply(delta_r, rebased_r)
    result_t = _add(_matrix_vector(delta_r, rebased_t), delta_t)
    return _encode(result_r, result_t, 1.0, original_tail)

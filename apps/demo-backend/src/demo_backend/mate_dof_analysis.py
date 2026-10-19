"""Conservative top-level rigid-body DOF analysis for face-based mate graphs.

The result is explanatory, not a replacement for the SolidWorks solver.  It
builds a small six-column constraint Jacobian for the selected target module
and reports its numeric rank.  Unsupported endpoint geometry is left unknown
instead of being optimistically counted as constrained.
"""

from __future__ import annotations

import math
from typing import Any, Iterable


class MateDofAnalysisError(ValueError):
    pass


def _vector(value: Any, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) < 3:
        raise MateDofAnalysisError(f"{field} requires three coordinates.")
    result = [float(item) for item in value[:3]]
    if any(not math.isfinite(item) for item in result):
        raise MateDofAnalysisError(f"{field} contains a non-finite coordinate.")
    return result


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(item * item for item in vector))
    if length <= 1e-12:
        raise MateDofAnalysisError("Face normal has zero length.")
    return [item / length for item in vector]


def _cross(first: list[float], second: list[float]) -> list[float]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def _tangent_basis(normal: list[float]) -> tuple[list[float], list[float]]:
    reference = [1.0, 0.0, 0.0] if abs(normal[0]) < 0.8 else [0.0, 1.0, 0.0]
    first = _normalize(_cross(normal, reference))
    second = _normalize(_cross(normal, first))
    return first, second


def _rank(rows: Iterable[list[float]], tolerance: float = 1e-9) -> int:
    matrix = [list(row) for row in rows if any(abs(value) > tolerance for value in row)]
    if not matrix:
        return 0
    row_count = len(matrix)
    column_count = len(matrix[0])
    rank = 0
    for column in range(column_count):
        pivot = max(range(rank, row_count), key=lambda index: abs(matrix[index][column]))
        if abs(matrix[pivot][column]) <= tolerance:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        scale = matrix[rank][column]
        matrix[rank] = [value / scale for value in matrix[rank]]
        for index in range(row_count):
            if index == rank:
                continue
            factor = matrix[index][column]
            if abs(factor) <= tolerance:
                continue
            matrix[index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(matrix[index], matrix[rank])
            ]
        rank += 1
        if rank == row_count:
            break
    return rank


def _nullspace_basis(
    rows: Iterable[list[float]], column_count: int = 6, tolerance: float = 1e-9
) -> list[list[float]]:
    """Return a deterministic RREF null-space basis for explanatory output."""

    matrix = [list(row[:column_count]) for row in rows]
    if not matrix:
        return [
            [1.0 if row == column else 0.0 for row in range(column_count)]
            for column in range(column_count)
        ]
    pivot_columns: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        pivot = max(
            range(pivot_row, len(matrix)),
            key=lambda index: abs(matrix[index][column]),
        )
        if abs(matrix[pivot][column]) <= tolerance:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        scale = matrix[pivot_row][column]
        matrix[pivot_row] = [value / scale for value in matrix[pivot_row]]
        for index in range(len(matrix)):
            if index == pivot_row:
                continue
            factor = matrix[index][column]
            if abs(factor) <= tolerance:
                continue
            matrix[index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(matrix[index], matrix[pivot_row])
            ]
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    free_columns = [
        column for column in range(column_count) if column not in pivot_columns
    ]
    basis: list[list[float]] = []
    for free_column in free_columns:
        vector = [0.0] * column_count
        vector[free_column] = 1.0
        for row_index, pivot_column in reversed(
            list(enumerate(pivot_columns))
        ):
            vector[pivot_column] = -sum(
                matrix[row_index][column] * vector[column]
                for column in free_columns
            )
        maximum = max(abs(value) for value in vector)
        if maximum > tolerance:
            vector = [
                0.0 if abs(value / maximum) <= tolerance else value / maximum
                for value in vector
            ]
        basis.append(vector)
    return basis


def _target_endpoint(mate: dict[str, Any], target: str) -> dict[str, Any] | None:
    matches = [
        endpoint
        for endpoint in mate.get("Endpoints") or []
        if str(endpoint.get("ModuleToken") or "").upper() == target
    ]
    return matches[0] if len(matches) == 1 else None


def _target_endpoints(mate: dict[str, Any], target: str) -> list[dict[str, Any]]:
    return [
        endpoint
        for endpoint in mate.get("Endpoints") or []
        if str(endpoint.get("ModuleToken") or "").upper() == target
    ]


def _midpoint(first: list[float], second: list[float]) -> list[float]:
    return [(left + right) / 2.0 for left, right in zip(first, second)]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(left * right for left, right in zip(first, second))


def _slot_direction(mate: dict[str, Any]) -> list[float]:
    geometry = mate.get("AnalysisGeometry") or mate.get("analysisGeometry") or {}
    return _normalize(
        _vector(
            geometry.get("SlotDirectionWorld")
            or geometry.get("slotDirectionWorld"),
            "AnalysisGeometry.SlotDirectionWorld",
        )
    )


def _slot_axis_and_reference(
    mate: dict[str, Any], target_endpoints: list[dict[str, Any]]
) -> tuple[list[float], list[float]]:
    """Return the slot axis and a point used by the rigid-body Jacobian.

    SolidWorks may export a slot mate with either the cylindrical pin or one
    planar wall of the slot on the target-module side.  The former carries an
    analytic cylinder axis directly.  For the latter, discovery code records
    the slot axis explicitly and the mating pin supplies a stable reference
    point.  Treating both representations identically is required for N000,
    whose target endpoint is the slot wall rather than the A000 pin.
    """

    geometry = mate.get("AnalysisGeometry") or mate.get("analysisGeometry") or {}
    target_cylinders = [
        endpoint
        for endpoint in target_endpoints
        if endpoint.get("CylinderAxisWorld") is not None
        and endpoint.get("CylinderOriginWorld") is not None
    ]
    if len(target_cylinders) == 1:
        endpoint = target_cylinders[0]
        return (
            _normalize(_vector(endpoint.get("CylinderAxisWorld"), "CylinderAxisWorld")),
            _vector(endpoint.get("CylinderOriginWorld"), "CylinderOriginWorld"),
        )

    axis = _normalize(
        _vector(
            geometry.get("SlotAxisWorld") or geometry.get("slotAxisWorld"),
            "AnalysisGeometry.SlotAxisWorld",
        )
    )
    reference_value = (
        geometry.get("SlotReferencePointWorld")
        or geometry.get("slotReferencePointWorld")
    )
    if reference_value is None:
        other_cylinders = [
            endpoint
            for endpoint in mate.get("Endpoints") or []
            if endpoint not in target_endpoints
            and endpoint.get("CylinderOriginWorld") is not None
        ]
        if len(other_cylinders) == 1:
            reference_value = other_cylinders[0].get("CylinderOriginWorld")
    return axis, _vector(reference_value, "AnalysisGeometry.SlotReferencePointWorld")


def analyze_target_mate_dof(
    effective_graph: dict[str, Any], target_module_token: str
) -> dict[str, Any]:
    """Estimate constrained and residual rigid-body DOF for one graph module."""

    target = str(target_module_token or "").strip().upper()
    if not target:
        raise MateDofAnalysisError("target_module_token is required.")
    module_tokens = {
        str(module.get("ModuleToken") or "").upper()
        for module in effective_graph.get("Modules") or []
    }
    if target not in module_tokens:
        raise MateDofAnalysisError(f"Target module {target} is outside the effective graph.")

    rows: list[list[float]] = []
    relations: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for mate in effective_graph.get("Mates") or []:
        if bool(mate.get("IsSuppressed", False)):
            continue
        tokens = {str(value).upper() for value in mate.get("ModuleTokens") or []}
        if target not in tokens:
            continue
        mate_type = int(mate.get("MateType", -1))
        target_endpoints = _target_endpoints(mate, target)
        if mate_type == 1:  # concentric: align two analytic cylinder axes
            if len(target_endpoints) != 1:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "concentric_target_requires_one_cylindrical_face",
                })
                continue
            target_endpoint = target_endpoints[0]
            other_endpoints = [
                endpoint
                for endpoint in mate.get("Endpoints") or []
                if endpoint is not target_endpoint
            ]
            if len(other_endpoints) != 1:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "concentric_context_requires_one_cylindrical_face",
                })
                continue
            other_endpoint = other_endpoints[0]
            try:
                target_axis = _normalize(
                    _vector(target_endpoint.get("CylinderAxisWorld"), "CylinderAxisWorld")
                )
                target_origin = _vector(
                    target_endpoint.get("CylinderOriginWorld"), "CylinderOriginWorld"
                )
                other_axis = _normalize(
                    _vector(other_endpoint.get("CylinderAxisWorld"), "CylinderAxisWorld")
                )
                _vector(other_endpoint.get("CylinderOriginWorld"), "CylinderOriginWorld")
            except MateDofAnalysisError as exc:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": f"concentric_axis_geometry_missing: {exc}",
                })
                continue
            if abs(_dot(target_axis, other_axis)) < 0.95:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "concentric_cylinder_axes_are_not_parallel",
                })
                continue
            tangent_first, tangent_second = _tangent_basis(target_axis)
            mate_rows = [
                [*tangent_first, *_cross(target_origin, tangent_first)],
                [*tangent_second, *_cross(target_origin, tangent_second)],
                [0.0, 0.0, 0.0, *tangent_first],
                [0.0, 0.0, 0.0, *tangent_second],
            ]
            before = _rank(rows)
            rows.extend(mate_rows)
            after = _rank(rows)
            relations.append({
                "mateName": mate.get("MateName"),
                "mateType": mate_type,
                "rowCount": len(mate_rows),
                "independentConstraintCount": after - before,
                "cumulativeRank": after,
                "conservativeModel": "coaxial_axis_alignment_four_constraints",
            })
            continue

        if mate_type == 11:  # width: conservatively count only center-plane offset
            if len(target_endpoints) != 2:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "width_target_requires_two_faces",
                })
                continue
            try:
                first_normal = _normalize(
                    _vector(target_endpoints[0].get("FaceNormalWorld"), "FaceNormalWorld")
                )
                second_normal = _normalize(
                    _vector(target_endpoints[1].get("FaceNormalWorld"), "FaceNormalWorld")
                )
                first_center = _vector(
                    target_endpoints[0].get("FaceCenterWorld"), "FaceCenterWorld"
                )
                second_center = _vector(
                    target_endpoints[1].get("FaceCenterWorld"), "FaceCenterWorld"
                )
            except MateDofAnalysisError as exc:
                unsupported.append({"mateName": mate.get("MateName"), "reason": str(exc)})
                continue
            if abs(_dot(first_normal, second_normal)) < 0.95:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "width_target_faces_are_not_parallel",
                })
                continue
            center = _midpoint(first_center, second_center)
            mate_rows = [[*first_normal, *_cross(center, first_normal)]]
            before = _rank(rows)
            rows.extend(mate_rows)
            after = _rank(rows)
            relations.append({
                "mateName": mate.get("MateName"),
                "mateType": mate_type,
                "rowCount": len(mate_rows),
                "independentConstraintCount": after - before,
                "cumulativeRank": after,
                "conservativeModel": "width_center_plane_offset_only",
            })
            continue

        if mate_type == 21:  # slot: axis alignment plus cross-slot positioning
            if len(target_endpoints) != 1:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "slot_target_requires_one_face",
                })
                continue
            other_endpoints = [
                endpoint
                for endpoint in mate.get("Endpoints") or []
                if endpoint not in target_endpoints
            ]
            if len(other_endpoints) != 1:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "slot_context_requires_one_cylindrical_face",
                })
                continue
            try:
                target_axis, target_origin = _slot_axis_and_reference(
                    mate, target_endpoints
                )
                other_axis_value = other_endpoints[0].get("CylinderAxisWorld")
                other_axis = (
                    _normalize(_vector(other_axis_value, "CylinderAxisWorld"))
                    if other_axis_value is not None
                    else target_axis
                )
                direction = _slot_direction(mate)
            except MateDofAnalysisError as exc:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": f"slot_direction_geometry_missing: {exc}",
                })
                continue
            if abs(_dot(target_axis, other_axis)) < 0.95:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "slot_cylinder_axes_are_not_parallel",
                })
                continue
            if abs(_dot(target_axis, direction)) > 0.05:
                unsupported.append({
                    "mateName": mate.get("MateName"),
                    "reason": "slot_direction_is_not_perpendicular_to_axis",
                })
                continue
            cross_slot = _normalize(_cross(target_axis, direction))
            tangent_first, tangent_second = _tangent_basis(target_axis)
            mate_rows = [
                [*cross_slot, *_cross(target_origin, cross_slot)],
                [0.0, 0.0, 0.0, *tangent_first],
                [0.0, 0.0, 0.0, *tangent_second],
            ]
            advanced = mate.get("AdvancedOptions") or mate.get("advancedOptions") or {}
            constraint = int(advanced.get("SlotConstraint", 0))
            if constraint in {1, 2, 3}:  # centered, distance, or percent closes along-slot travel
                mate_rows.append([*direction, *_cross(target_origin, direction)])
            before = _rank(rows)
            rows.extend(mate_rows)
            after = _rank(rows)
            relations.append({
                "mateName": mate.get("MateName"),
                "mateType": mate_type,
                "slotConstraint": constraint,
                "slotConstraintName": {
                    0: "free",
                    1: "centered",
                    2: "distance",
                    3: "percent",
                }.get(constraint, "unknown"),
                "rowCount": len(mate_rows),
                "independentConstraintCount": after - before,
                "cumulativeRank": after,
                "conservativeModel": (
                    "slot_axis_alignment_plus_cross_slot_position"
                    if constraint == 0
                    else "slot_axis_alignment_plus_fixed_along_slot_position"
                ),
            })
            continue

        endpoint = _target_endpoint(mate, target)
        if endpoint is None:
            unsupported.append({"mateName": mate.get("MateName"), "reason": "target_endpoint_not_unique"})
            continue
        try:
            normal = _normalize(_vector(endpoint.get("FaceNormalWorld"), "FaceNormalWorld"))
            center = _vector(endpoint.get("FaceCenterWorld"), "FaceCenterWorld")
        except MateDofAnalysisError as exc:
            unsupported.append({"mateName": mate.get("MateName"), "reason": str(exc)})
            continue
        tangent_first, tangent_second = _tangent_basis(normal)
        mate_rows: list[list[float]] = []
        if mate_type in {0, 5}:  # coincident or distance: plane offset + parallel normals
            mate_rows.append([*normal, *_cross(center, normal)])
            mate_rows.append([0.0, 0.0, 0.0, *tangent_first])
            mate_rows.append([0.0, 0.0, 0.0, *tangent_second])
        elif mate_type == 3:  # parallel
            mate_rows.append([0.0, 0.0, 0.0, *tangent_first])
            mate_rows.append([0.0, 0.0, 0.0, *tangent_second])
        elif mate_type == 2:  # perpendicular: one rotational scalar
            other = next(
                (
                    item
                    for item in mate.get("Endpoints") or []
                    if item is not endpoint and item.get("FaceNormalWorld") is not None
                ),
                None,
            )
            if other is None:
                unsupported.append({"mateName": mate.get("MateName"), "reason": "other_face_normal_missing"})
                continue
            other_normal = _normalize(_vector(other.get("FaceNormalWorld"), "FaceNormalWorld"))
            axis = _cross(normal, other_normal)
            mate_rows.append([0.0, 0.0, 0.0, *axis])
        else:
            unsupported.append({
                "mateName": mate.get("MateName"),
                "mateType": mate_type,
                "reason": (
                    "slot_direction_geometry_missing"
                    if mate_type == 21
                    else "mate_type_not_yet_linearized"
                ),
            })
            continue
        before = _rank(rows)
        rows.extend(mate_rows)
        after = _rank(rows)
        relations.append({
            "mateName": mate.get("MateName"),
            "mateType": mate_type,
            "rowCount": len(mate_rows),
            "independentConstraintCount": after - before,
            "cumulativeRank": after,
        })

    rank = _rank(rows)
    residual = max(0, 6 - rank)
    column_order = ["tx", "ty", "tz", "rx", "ry", "rz"]
    residual_basis = []
    for vector in _nullspace_basis(rows):
        dominant = [
            name
            for name, value in zip(column_order, vector)
            if abs(value) >= 0.5
        ]
        residual_basis.append(
            {
                "vector": {
                    name: round(value, 12)
                    for name, value in zip(column_order, vector)
                },
                "dominantComponents": dominant,
            }
        )
    if residual == 0:
        recommendation = "面级刚体约束秩已闭合；仍须以CAD保存重开后的求解状态为准。"
    elif rank <= 3:
        recommendation = "当前约束方向不足；优先增加与已有面法向不平行的第二安装基准。"
    elif residual == 1:
        recommendation = "仍有一个自由度；增加孔轴、边方向或第三基准面以消除最后的滑移/转动。"
    else:
        recommendation = "继续增加独立方向的面、轴或孔基准，避免重复使用共面或平行基准。"
    return {
        "schemaVersion": "mate-dof-analysis/v1",
        "targetModuleToken": target,
        "assumption": "target_as_single_rigid_body_against_fixed_context",
        "jacobianColumnOrder": column_order,
        "constraintRank": rank,
        "residualDof": residual,
        "residualDofBasis": residual_basis,
        "closed": residual == 0,
        "relations": relations,
        "unsupportedRelations": unsupported,
        "authoritativeCadSolveRequired": True,
        "recommendation": recommendation,
    }

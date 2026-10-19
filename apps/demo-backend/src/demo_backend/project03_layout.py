"""Project03 sequential Top-3 wrapper over the shared bounded solver."""

from __future__ import annotations

from typing import Any

from .project01_layout import solve_project01_top3


def solve_project03_top3(
    occupancy: dict[str, Any],
    work_positions: dict[str, Any],
    service_points: dict[str, Any],
    valve_reach: dict[str, Any],
    scanner_geometry: dict[str, Any],
) -> dict[str, Any]:
    """Solve Project03 using portable rules and Project03-only evidence.

    The 20 mm containment tolerance records the observed AE00 mounting-edge
    overhang beyond the conservative AA00 outer AABB (about 17.2 mm).  It is
    not inherited from another case and does not permit arbitrary movement.
    """

    return solve_project01_top3(
        occupancy,
        work_positions,
        service_points,
        valve_reach,
        scanner_geometry,
        expected_occupancy_status="PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY",
        case_id="project03",
        case_label="项目03",
        containment_tolerance_meters=0.020,
        solver_mode="project03-sequential-bounded-top-k",
        anchor_target_source="AA00-AE00 one coincident support plane plus two concentric locating holes",
        assumption_warnings=[
            "项目03只使用自身原型参数，不继承项目01/02数值。",
            "20 mm安装边缘容差来自AE00相对AA00保守外包络约17.2 mm的原型伸出。",
            "操作侧、100 mm扫描光束和双阀尺度仅授权粗布局，尚非厂商确认。",
            "候选选中后才Replay；条件B-rep不在求解阶段调用。",
        ],
        sequence=[
            "AA00/AF00 fixed context",
            "AE00 transport installation",
            "AD00 two work positions",
            "AI00 scanner optical alignment",
            "AG00/AH00/AJ00 operation-side service placement",
            "AB00+AC00 inverse dual-valve reach coverage",
        ],
    )

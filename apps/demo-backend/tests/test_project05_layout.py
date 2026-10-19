from __future__ import annotations

import json
from pathlib import Path

from demo_backend.layout_preview import solve_case_preview
from demo_backend.project05_layout import solve_project05_top3


WORKSPACE = Path(__file__).resolve().parents[3]


def _load(name: str) -> dict:
    return json.loads((WORKSPACE / "demo/layout_previews" / name).read_text(encoding="utf-8-sig"))


def test_project05_top3_uses_complete_leaf_geometry_and_keeps_production_blocked() -> None:
    result = solve_project05_top3(
        _load("project05_module_occupancy.json"),
        _load("project05_work_positions.json"),
        _load("project05_service_points.json"),
        _load("project05_dual_valve_reach.json"),
        _load("project05_optical_geometry.json"),
        _load("project05_operation_side.json"),
    )
    plan = result["constraintPlan"]
    solutions = plan["jointSearch"]["solutions"]

    assert len(solutions) == 3
    assert plan["jointSearch"]["acceptedCandidateCounts"]["joint"] > 3
    assert plan["staticCollisionPolicy"]["strictPairOccupancyMode"] == "complete-leaf-body-aabbs"
    assert plan["staticCollisionPolicy"]["strictAabbPairCount"] == 15
    assert plan["staticCollisionPolicy"]["brepOnAabbOverlapPairCount"] == 13
    assert plan["validation"]["productionReady"] is False
    assert result["prototypePoseUsedForSolving"] is True
    assert result["sourceCapturePoseUsedForAnchoring"] is True
    assert solutions[0]["movedObjectIds"] == []
    assert any(solution["movedObjectIds"] for solution in solutions[1:])


def test_project05_preview_exposes_three_visual_review_candidates() -> None:
    preview = solve_case_preview(WORKSPACE, "project05", persist=False)

    assert preview["caseId"] == "project05"
    assert preview["metrics"]["hardFeasible"] is True
    assert len(preview["solutions"]) == 3
    assert [solution["rank"] for solution in preview["solutions"]] == [1, 2, 3]
    assert preview["prototypePoseUsedForSolving"] is True
    assert preview["sourceCapturePoseUsedForAnchoring"] is True
    assert preview["staticCollisionPolicy"]["strictAabbPairCount"] == 15
    assert preview["staticCollisionPolicy"]["brepOnAabbOverlapPairCount"] == 13
    assert any(item["title"] == "严格碰撞前置门禁" for item in preview["reviewItems"])

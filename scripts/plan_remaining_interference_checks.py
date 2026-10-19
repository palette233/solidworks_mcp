"""Prioritize exact CAD checks after conservative world-AABB screening."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENING = ROOT / "demo" / "FL9A24D062A000_allowed_overlap_3d_screening.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_interference_check_plan.json"

MODULE_LABELS = {
    "FL9A24D062A800.001-1": "A800 传输",
    "FL9A24D062A180.001-1": "A180 扫描",
    "FL9A24D062A200.001-1": "A200 CCD",
    "FL9A24D062A500.001-1": "A500 校准",
    "FL9A24D062A700.001-1": "A700 清洁+称重",
    "FL9A24D062A300.001-1": "A300 排胶杯",
    "T401AA-07388-0-1": "T401 供胶",
}

EXPECTED_INTERACTIONS = {
    frozenset(("FL9A24D062A800.001-1", "FL9A24D062A200.001-1")): "CCD Portal 跨越传输线",
    frozenset(("FL9A24D062A800.001-1", "FL9A24D062A180.001-1")): "扫描器靠近传输条码入口",
    frozenset(("FL9A24D062A800.001-1", "FL9A24D062A500.001-1")): "传输与校准服务区相邻",
    frozenset(("FL9A24D062A800.001-1", "FL9A24D062A700.001-1")): "传输与清洁/称重服务区相邻",
    frozenset(("FL9A24D062A800.001-1", "FL9A24D062A300.001-1")): "传输与排胶服务区相邻",
    frozenset(("FL9A24D062A200.001-1", "T401AA-07388-0-1")): "CCD Portal 与供胶组件空间交叉",
}


def priority(item: dict, tolerance: float) -> tuple[int, str]:
    volume = item["intersectionBoxVolumeCubicMeters"]
    distance = item["minimumAabbDistanceMeters"]
    if distance <= tolerance and (not item["aabbOverlaps3d"] or volume <= 1e-12):
        return 0, "near_touch_or_numerical_contact"
    if volume <= 0.002:
        return 1, "small_aabb_intersection"
    return 2, "large_or_intentional_pass_through_aabb_intersection"


def main() -> None:
    screening = json.loads(SCREENING.read_text(encoding="utf-8"))
    tolerance = screening["separationToleranceMeters"]
    checks: list[dict] = []
    for item in screening["diagnostics"]:
        if item["status"] != "needs_brep_check":
            continue
        rank, reason = priority(item, tolerance)
        first, second = item["components"]
        checks.append(
            {
                "priority": f"P{rank}",
                "priorityRank": rank,
                "components": [first, second],
                "moduleLabels": [MODULE_LABELS[first], MODULE_LABELS[second]],
                "reason": reason,
                "expectedInteraction": EXPECTED_INTERACTIONS.get(
                    frozenset((first, second)), "功能模组之间的空间邻接"
                ),
                "minimumAabbDistanceMeters": item["minimumAabbDistanceMeters"],
                "intersectionBoxVolumeCubicMeters": item[
                    "intersectionBoxVolumeCubicMeters"
                ],
                "requiredChecks": [
                    "isolated_brep_interference",
                    "minimum_clearance",
                    "maintenance_or_motion_clearance",
                ],
            }
        )

    checks.sort(
        key=lambda item: (
            item["priorityRank"],
            item["intersectionBoxVolumeCubicMeters"],
            item["components"],
        )
    )
    for index, item in enumerate(checks, start=1):
        item["executionOrder"] = index

    result = {
        "success": True,
        "sourceScreening": str(SCREENING),
        "pendingPairCount": len(checks),
        "priorityCounts": {
            priority_name: sum(item["priority"] == priority_name for item in checks)
            for priority_name in ("P0", "P1", "P2")
        },
        "policy": {
            "P0": "近接触/数值接触：禁止 AABB 短路，优先做实体干涉和最小间隙。",
            "P1": "小范围包围盒相交：逐对隔离执行 B-Rep，失败时保留待检。",
            "P2": "较大或工艺预期穿越：实体干涉后还需运动及维护空间检查。",
        },
        "checks": checks,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

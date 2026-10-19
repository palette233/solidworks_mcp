#!/usr/bin/env python3
"""Finalize the three discrete AD00 full-context state gates into one machine closure."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def configuration_equivalent(result: dict[str, Any]) -> bool:
    requested = str(result.get("RequestedConfiguration", result.get("requestedConfiguration", "")))
    actual = str(result.get("ActualConfiguration", result.get("actualConfiguration", "")))
    normalized_actual = re.sub(r"-_flexible\d+$", "", actual, flags=re.IGNORECASE)
    return bool(requested and normalized_actual == requested)


def state_summary(
    name: str,
    construction_path: Path,
    assessment_path: Path,
    expected_left: str,
    expected_right: str,
) -> dict[str, Any]:
    construction = load(construction_path)
    assessment = load(assessment_path)
    left = construction.get("leftConfiguration") or {}
    right = construction.get("rightConfiguration") or {}
    requested = construction.get("requestedConfigurations") or {}
    config_gate = (
        requested.get("left") == expected_left
        and requested.get("right") == expected_right
        and configuration_equivalent(left)
        and configuration_equivalent(right)
    )
    passed = bool(
        construction.get("sourceFilesUnchanged")
        and config_gate
        and assessment.get("passed")
    )
    effective_construction_status = (
        "PASSED_AFTER_CLEAN_RESTART_RECOVERY"
        if passed and construction.get("status") == "ERROR"
        else construction.get("status")
    )
    return {
        "state": name,
        "passed": passed,
        "constructionClosure": str(construction_path.resolve()),
        "assessment": str(assessment_path.resolve()),
        "constructionStatus": construction.get("status"),
        "effectiveConstructionStatus": effective_construction_status,
        "recoveredAfterCleanRestart": bool(
            passed and construction.get("status") == "ERROR"
        ),
        "sourceFilesUnchanged": construction.get("sourceFilesUnchanged"),
        "configurationGatePassed": config_gate,
        "requestedConfigurations": requested,
        "actualConfigurations": {
            "left": left.get("ActualConfiguration", left.get("actualConfiguration")),
            "right": right.get("ActualConfiguration", right.get("actualConfiguration")),
        },
        "collisionGateStatus": assessment.get("status"),
        "interferingBodyPairCount": assessment.get("actualInterferingBodyPairCount"),
        "newLeafSourcePairs": assessment.get("newLeafSourcePairs"),
        "constructionDurationSeconds": construction.get("durationSeconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-construction", required=True, type=Path)
    parser.add_argument("--baseline-assessment", required=True, type=Path)
    parser.add_argument("--left-construction", required=True, type=Path)
    parser.add_argument("--left-assessment", required=True, type=Path)
    parser.add_argument("--right-construction", required=True, type=Path)
    parser.add_argument("--right-assessment", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    states = [
        state_summary("both-0deg", args.baseline_construction, args.baseline_assessment, "0度", "0度"),
        state_summary("left-25deg", args.left_construction, args.left_assessment, "25度", "0度"),
        state_summary("right-25deg", args.right_construction, args.right_assessment, "0度", "25度"),
    ]
    passed = all(state["passed"] for state in states)
    payload = {
        "schemaVersion": "project03-ad00-three-state-full-context-closure/v1",
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "PASSED_PROJECT03_AD00_THREE_DISCRETE_FULL_CONTEXT_STATES"
            if passed
            else "FAILED_PROJECT03_AD00_THREE_DISCRETE_FULL_CONTEXT_STATES"
        ),
        "passed": passed,
        "productionReady": False,
        "states": states,
        "remainingBlockers": [
            "0度到25度之间的连续扫掠体尚未验证。",
            "左右翻转动作的厂商轴限位、速度和安全间隙尚未确认。",
            "当前直接上下文基线来自已发布十对象混合静态装配；其柔性状态与原型6对接触基线不同。",
        ],
    }
    args.output.resolve().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output.resolve())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

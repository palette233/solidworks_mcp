"""Evidence-backed Project03 AD20 dynamic request gate.

The gate deliberately distinguishes a saved discrete CAD pose from a motion
through an angle range.  A sampled pose may be reusable evidence, while a
continuous move remains blocked until swept-volume evidence exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DYNAMIC_CLOSURE_SCHEMA = "project03-ad20-context-rebased-dynamic-closure/v1"


def parse_project03_ad20_process_request(text: str) -> dict[str, Any]:
    source = " ".join(str(text or "").split())
    relevant = bool(
        re.search(r"AD20|翻转|旋转|转动|翻转模组|举升定位模组", source, re.IGNORECASE)
    )
    angles = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*度", source)]
    if not relevant or not angles:
        return {
            "requested": False,
            "mode": "static_assembly_only",
            "sourceText": None,
        }

    discrete = bool(
        re.search(r"(?:验证|检查|核验).{0,12}(?:静态|离散).{0,8}(?:状态|姿态)", source)
        or re.search(r"(?:静态|离散).{0,8}(?:状态|姿态).{0,12}(?:验证|检查|核验)", source)
    )
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*度?\s*(?:到|至|→|-)\s*(\d+(?:\.\d+)?)\s*度",
        source,
    )
    if range_match:
        start_angle = float(range_match.group(1))
        target_angle = float(range_match.group(2))
    elif discrete:
        start_angle = None
        target_angle = angles[-1]
    else:
        start_angle = 0.0
        target_angle = angles[-1]

    return {
        "requested": True,
        "mode": "discrete_state_validation" if discrete else "continuous_motion",
        "startAngleDegrees": start_angle,
        "targetAngleDegrees": target_angle,
        "maximumRequestedAngleDegrees": max(
            abs(value) for value in angles
        ),
        "sourceText": source,
    }


def load_project03_ad20_dynamic_closure(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"项目03 AD20动态闭包不存在：{resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if payload.get("schemaVersion") != DYNAMIC_CLOSURE_SCHEMA:
        raise ValueError("项目03 AD20动态闭包版本不受支持。")
    payload["evidencePath"] = str(resolved)
    return payload


def _sample_at(closure: dict[str, Any], angle: float) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in closure.get("states") or []
            if abs(float(row.get("angleDegrees") or 0.0) - angle) <= 1e-9
        ),
        None,
    )


def evaluate_project03_ad20_process_request(
    request: dict[str, Any], closure: dict[str, Any]
) -> dict[str, Any]:
    if request.get("requested") is not True:
        return {
            "requested": False,
            "accepted": True,
            "status": "STATIC_ASSEMBLY_ONLY_DYNAMIC_GATE_NOT_REQUESTED",
            "scope": "static-assembly",
            "message": "命令未请求AD20动态动作；本次只允许静态装配闭环。",
            "evidencePath": closure.get("evidencePath"),
        }

    mode = str(request.get("mode") or "")
    target = float(request.get("targetAngleDegrees") or 0.0)
    if mode == "discrete_state_validation":
        state = _sample_at(closure, target)
        if state is None:
            return {
                "requested": True,
                "accepted": False,
                "status": "REJECTED_UNSAMPLED_DISCRETE_STATE",
                "scope": "discrete-state",
                "requestedAngleDegrees": target,
                "verifiedSafeSampledAnglesDegrees": closure.get(
                    "verifiedSafeSampledAnglesDegrees"
                ) or [],
                "message": f"{target:g}°没有保存重开及叶级B-rep证据，禁止执行。",
                "evidencePath": closure.get("evidencePath"),
            }
        accepted = state.get("passedNoNewInterferenceGate") is True
        return {
            "requested": True,
            "accepted": accepted,
            "status": (
                "ACCEPTED_VERIFIED_DISCRETE_STATE"
                if accepted
                else "REJECTED_DISCRETE_STATE_INTERFERENCE"
            ),
            "scope": "discrete-state",
            "requestedAngleDegrees": target,
            "exactCheckComplete": state.get("exactCheckComplete") is True,
            "newLeafSourcePairs": state.get("newLeafSourcePairs") or [],
            "message": (
                f"{target:g}°静态姿态已有保存重开、位姿复测和叶级B-rep证据。"
                if accepted
                else f"{target:g}°静态姿态出现新增叶级实体干涉，禁止执行。"
            ),
            "evidencePath": closure.get("evidencePath"),
        }

    continuous_verified = closure.get("continuousPathVerified") is True
    full_range_passed = closure.get("fullRequestedRangePassed") is True
    accepted = continuous_verified and full_range_passed
    bracket = closure.get("firstObservedCollisionBracketDegrees")
    pair_refinement = closure.get("knownPairFirstContactRefinement") or {}
    pair_bracket = pair_refinement.get("firstObservedCollisionBracketDegrees")
    rejected_angles = closure.get("rejectedSampledAnglesDegrees") or []
    return {
        "requested": True,
        "accepted": accepted,
        "status": (
            "ACCEPTED_CONTINUOUS_MOTION"
            if accepted
            else "REJECTED_CONTINUOUS_PATH_NOT_VERIFIED"
        ),
        "scope": "continuous-motion",
        "startAngleDegrees": request.get("startAngleDegrees"),
        "targetAngleDegrees": target,
        "continuousPathVerified": continuous_verified,
        "firstObservedCollisionBracketDegrees": bracket,
        "knownPairFirstObservedCollisionBracketDegrees": pair_bracket,
        "rejectedSampledAnglesDegrees": rejected_angles,
        "message": (
            "连续运动已有权威扫掠证据。"
            if accepted
            else (
                "离散姿态不能证明连续路径安全；"
                + (
                    f"首次观测碰撞区间为({bracket[0]:g}°,{bracket[1]:g}°]。"
                    if isinstance(bracket, list) and len(bracket) == 2
                    else f"已拒绝采样角度为{rejected_angles}。"
                )
                + (
                    f"已知碰撞叶对的局部精检首碰区间为({pair_bracket[0]:g}°,{pair_bracket[1]:g}°]，"
                    "但该局部结果不代表整机连续安全。"
                    if isinstance(pair_bracket, list) and len(pair_bracket) == 2
                    else ""
                )
            )
        ),
        "evidencePath": closure.get("evidencePath"),
    }

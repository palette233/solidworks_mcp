"""Project02 discrete process-state gate.

This is intentionally an evidence gate, not a motion simulator.  It converts
the existing prototype-derived service points and common dual-valve reach into
explicit states that can be rejected before CAD replay.  Production release
remains blocked until swept envelopes and authoritative axis limits exist.
"""

from __future__ import annotations

import math
from typing import Any


DYNAMIC_GATE_SCHEMA = "project02-discrete-process-gate/v1"

REQUIRED_REACH_CHECKS = {
    "transport-work-position-1": "auto-work-reach-FL9A24D062A800.001-1-workPosition1-dualValveReach",
    "transport-work-position-2": "auto-work-reach-FL9A24D062A800.001-1-workPosition2-dualValveReach",
    "calibration": "auto-calibration-reach-FL9A24D062A500.001-1-dualValveReach",
    "cleaning": "auto-cleaning-reach-FL9A24D062A700.001-1-dualValveReach",
    "weighing": "coarse-a700-weighing-reach",
    "drain-left": "coarse-left-drain-reach",
    "drain-right": "coarse-right-drain-reach",
}

PROCESS_SEQUENCE = [
    {"stateId": "transport-work-position-1", "moduleToken": "A800", "kind": "work"},
    {"stateId": "transport-work-position-2", "moduleToken": "A800", "kind": "work"},
    {"stateId": "calibration", "moduleToken": "A500", "kind": "service"},
    {"stateId": "cleaning", "moduleToken": "A700", "kind": "service"},
    {"stateId": "weighing", "moduleToken": "A700", "kind": "service"},
    {"stateId": "drain-left", "moduleToken": "A300", "kind": "service"},
    {"stateId": "drain-right", "moduleToken": "A300", "kind": "service"},
]


class DynamicProcessGateError(ValueError):
    pass


def _valid_aabb(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 6
        and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value)
        and all(float(value[index]) < float(value[index + 3]) for index in range(3))
    )


def evaluate_a700_swept_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    payload = evidence or {}
    by_id = {str(row.get("stateId")): row for row in payload.get("states") or []}
    required = ("cleaning", "weighing", "maintenance")
    states = []
    for state_id in required:
        row = by_id.get(state_id) or {}
        accepted = bool(
            row.get("saveReopenVerified") is True
            and row.get("collisionGateAccepted") is True
            and _valid_aabb(row.get("sweptEnvelopeAabb"))
        )
        states.append(
            {
                "stateId": state_id,
                "accepted": accepted,
                "saveReopenVerified": row.get("saveReopenVerified") is True,
                "collisionGateAccepted": row.get("collisionGateAccepted") is True,
                "validSweptEnvelopeAabb": _valid_aabb(row.get("sweptEnvelopeAabb")),
                "assemblyPath": row.get("assemblyPath"),
                "collisionEvidencePath": row.get("collisionEvidencePath"),
            }
        )
    accepted = bool(
        payload.get("success") is True
        and payload.get("allStatesCollisionFree") is True
        and all(row["accepted"] for row in states)
    )
    return {"accepted": accepted, "states": states, "requiredStateIds": list(required)}


def evaluate_a100_axis_limit_evidence(
    evidence: dict[str, Any] | None,
    legacy_authority: str,
) -> dict[str, Any]:
    payload = evidence or {}
    authority = str(payload.get("authority") or legacy_authority)
    axes = payload.get("valves") or {}
    required_axes = ("x", "y", "z")

    def valve_valid(name: str) -> bool:
        row = axes.get(name) or {}
        for axis in required_axes:
            limits = row.get(axis)
            if (
                not isinstance(limits, list)
                or len(limits) != 2
                or not all(isinstance(value, (int, float)) for value in limits)
                or float(limits[0]) >= float(limits[1])
            ):
                return False
        return True

    source_reference = str(payload.get("sourceReference") or "").strip()
    accepted = bool(
        authority in {"vendor-confirmed", "measured-limits"}
        and source_reference
        and valve_valid("left")
        and valve_valid("right")
    )
    return {
        "accepted": accepted,
        "authority": authority,
        "sourceReference": source_reference or None,
        "leftValveLimitsValid": valve_valid("left"),
        "rightValveLimitsValid": valve_valid("right"),
    }


def evaluate_project02_discrete_process_gate(
    reach_audit: dict[str, Any],
    service_access_audit: dict[str, Any],
    *,
    a700_swept_envelope_evidence: dict[str, Any] | None = None,
    axis_limit_authority: str = "prototype-estimated",
    a100_axis_limit_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if reach_audit.get("success") is not True:
        raise DynamicProcessGateError("A100双阀可达性证据不可用。")
    if service_access_audit.get("success") is not True:
        raise DynamicProcessGateError("服务维护空间证据不可用。")

    reach_rows = {
        str(row.get("id")): row
        for row in reach_audit.get("targetAndContainmentChecks") or []
    }
    access_rows = {
        str(row.get("moduleCode")): row
        for row in service_access_audit.get("modules") or []
    }
    states: list[dict[str, Any]] = []
    blockers: list[str] = []
    for state in PROCESS_SEQUENCE:
        reach_id = REQUIRED_REACH_CHECKS[state["stateId"]]
        reach_row = reach_rows.get(reach_id)
        reach_passed = bool(reach_row and reach_row.get("passed") is True)
        access_row = access_rows.get(state["moduleToken"])
        access_required = state["kind"] == "service"
        access_passed = not access_required or bool(
            access_row and access_row.get("passed") is True
        )
        accepted = reach_passed and access_passed
        if not reach_passed:
            blockers.append(f"{state['stateId']}不在双阀公共可达区。")
        if not access_passed:
            blockers.append(f"{state['stateId']}缺少维护/进入通道。")
        states.append(
            {
                **state,
                "reachCheckId": reach_id,
                "reachPassed": reach_passed,
                "serviceAccessRequired": access_required,
                "serviceAccessPassed": access_passed,
                "coarseStateAccepted": accepted,
            }
        )

    swept_result = evaluate_a700_swept_evidence(a700_swept_envelope_evidence)
    swept_passed = swept_result["accepted"] is True
    if not swept_passed:
        blockers.append("A700仅完成离散服务点验证，尚无各动态状态的扫掠包络/实体干涉证据。")
    axis_result = evaluate_a100_axis_limit_evidence(
        a100_axis_limit_evidence,
        axis_limit_authority,
    )
    authoritative_axis = axis_result["accepted"] is True
    if not authoritative_axis:
        blockers.append("A100公共行程仍为项目02原型估计，未由厂商行程或机械限位确认。")

    coarse_passed = all(state["coarseStateAccepted"] for state in states)
    production_passed = coarse_passed and swept_passed and authoritative_axis
    return {
        "schemaVersion": DYNAMIC_GATE_SCHEMA,
        "projectId": "project02",
        "gateKind": "representative-discrete-states",
        "states": states,
        "summary": {
            "stateCount": len(states),
            "coarseAcceptedCount": sum(
                1 for state in states if state["coarseStateAccepted"]
            ),
            "coarseProcessGatePassed": coarse_passed,
            "a700SweptEnvelopePassed": swept_passed,
            "a100AxisLimitsAuthoritative": authoritative_axis,
            "productionDynamicGatePassed": production_passed,
        },
        "releaseDecision": {
            "staticDemoMayProceed": coarse_passed,
            "productionMotionReleaseAllowed": production_passed,
        },
        "blockingIssues": list(dict.fromkeys(blockers)),
        "evidenceAuthority": {
            "reach": reach_audit.get("status"),
            "serviceAccess": service_access_audit.get("status"),
            "axisLimits": axis_result["authority"],
            "isMotionSimulation": False,
        },
        "dynamicEvidence": {
            "a700SweptStates": swept_result,
            "a100AxisLimits": axis_result,
        },
    }

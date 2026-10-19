from demo_backend.dynamic_process_gate import evaluate_project02_discrete_process_gate


IDS = [
    "auto-work-reach-FL9A24D062A800.001-1-workPosition1-dualValveReach",
    "auto-work-reach-FL9A24D062A800.001-1-workPosition2-dualValveReach",
    "auto-calibration-reach-FL9A24D062A500.001-1-dualValveReach",
    "auto-cleaning-reach-FL9A24D062A700.001-1-dualValveReach",
    "coarse-a700-weighing-reach",
    "coarse-left-drain-reach",
    "coarse-right-drain-reach",
]


def evidence():
    reach = {
        "success": True,
        "status": "prototype-estimated",
        "targetAndContainmentChecks": [{"id": value, "passed": True} for value in IDS],
    }
    access = {
        "success": True,
        "status": "coarse",
        "modules": [
            {"moduleCode": value, "passed": True}
            for value in ("A500", "A700", "A300")
        ],
    }
    return reach, access


def test_coarse_gate_passes_without_claiming_motion_release():
    reach, access = evidence()
    result = evaluate_project02_discrete_process_gate(reach, access)
    assert result["summary"]["coarseProcessGatePassed"] is True
    assert result["summary"]["productionDynamicGatePassed"] is False
    assert result["releaseDecision"]["staticDemoMayProceed"] is True
    assert result["evidenceAuthority"]["isMotionSimulation"] is False


def test_authoritative_limits_and_swept_envelope_close_production_gate():
    reach, access = evidence()
    result = evaluate_project02_discrete_process_gate(
        reach,
        access,
        a700_swept_envelope_evidence={
            "success": True,
            "allStatesCollisionFree": True,
            "states": [
                {
                    "stateId": state_id,
                    "saveReopenVerified": True,
                    "collisionGateAccepted": True,
                    "sweptEnvelopeAabb": [0, 0, 0, 1, 1, 1],
                }
                for state_id in ("cleaning", "weighing", "maintenance")
            ],
        },
        a100_axis_limit_evidence={
            "authority": "measured-limits",
            "sourceReference": "measurement-run-001",
            "valves": {
                side: {axis: [-1.0, 1.0] for axis in ("x", "y", "z")}
                for side in ("left", "right")
            },
        },
    )
    assert result["summary"]["productionDynamicGatePassed"] is True
    assert result["blockingIssues"] == []


def test_labels_without_state_geometry_or_axis_values_cannot_unlock_production():
    reach, access = evidence()
    result = evaluate_project02_discrete_process_gate(
        reach,
        access,
        a700_swept_envelope_evidence={
            "success": True,
            "allStatesCollisionFree": True,
        },
        axis_limit_authority="measured-limits",
    )
    assert result["summary"]["productionDynamicGatePassed"] is False
    assert result["dynamicEvidence"]["a700SweptStates"]["accepted"] is False
    assert result["dynamicEvidence"]["a100AxisLimits"]["accepted"] is False


def test_unreachable_state_is_a_hard_coarse_failure():
    reach, access = evidence()
    reach["targetAndContainmentChecks"][0]["passed"] = False
    result = evaluate_project02_discrete_process_gate(reach, access)
    assert result["summary"]["coarseProcessGatePassed"] is False
    assert result["releaseDecision"]["staticDemoMayProceed"] is False

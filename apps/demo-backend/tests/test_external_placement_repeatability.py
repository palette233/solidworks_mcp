from demo_backend.external_placement_repeatability import (
    ExternalPlacementRepeatabilityError,
    build_repeatability_confirmation_graph,
)


def _graph():
    return {
        "Modules": [
            {"ModuleToken": "A000", "SourceTransform": [1.0] * 16},
            {"ModuleToken": "G000", "SourceTransform": [2.0] * 16},
        ],
        "EditPolicy": {
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
        },
    }


def _run():
    return {
        "success": True,
        "outputAssemblyPath": "first.SLDASM",
        "outputAssemblySha256": "abc",
        "toolResult": {
            "Success": True,
            "TargetCaseAnchored": False,
            "RequestedTargetLeafPoseAnchorCount": 0,
            "ReopenedTargetRootTransform": [float(value) for value in range(16)],
        },
    }


def test_builds_validation_only_second_seed_graph():
    result = build_repeatability_confirmation_graph(_graph(), _run(), "g000", 2)

    target = next(row for row in result["Modules"] if row["ModuleToken"] == "G000")
    assert target["SourceTransform"] == [float(value) for value in range(16)]
    assert result["EditPolicy"]["initialPlacementVariant"] == 2
    assert result["ExternalPlacementRepeatabilityAudit"][
        "witnessIsValidationOnly"
    ] is True
    assert result["ExternalPlacementRepeatabilityAudit"]["poseAnchorUsed"] is False


def test_rejects_anchored_first_run():
    run = _run()
    run["toolResult"]["TargetCaseAnchored"] = True

    try:
        build_repeatability_confirmation_graph(_graph(), run, "G000", 1)
    except ExternalPlacementRepeatabilityError as exc:
        assert "锚点" in str(exc)
    else:
        raise AssertionError("anchored evidence must be rejected")

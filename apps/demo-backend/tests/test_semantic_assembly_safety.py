from demo_backend.semantic_assembly_safety import (
    build_semantic_assembly_release_gate,
    compare_interference_pair_to_baseline,
)


def reconstruction(passed=True, validation_passed=True):
    return {
        "Success": passed,
        "ValidationResults": [{"Passed": validation_passed}],
    }


def interference(count=0, *, complete=True, kernel_failures=0):
    return {
        "status": "PASSED_ZERO_INTERFERENCE" if count == 0 else "FAILED_INTERFERENCE_OR_INCOMPLETE",
        "componentCount": 3,
        "allTopLevelPairCount": 3,
        "aabbProvenPairCount": 0,
        "exactCandidatePairCount": 3,
        "completedExactPairCount": 3 if complete else 2,
        "incompleteExactPairCount": 0 if complete else 1,
        "kernelFailurePairCount": kernel_failures,
        "interferingModulePairCount": count,
        "interferingModulePairs": [["A500", "A700"]] if count else [],
    }


def test_release_requires_all_three_gates():
    result = build_semantic_assembly_release_gate(reconstruction(), interference())
    assert result["releaseAllowed"] is True
    assert result["status"] == "RELEASE_ALLOWED"


def test_collision_rejects_otherwise_valid_reconstruction():
    result = build_semantic_assembly_release_gate(reconstruction(), interference(2))
    assert result["releaseAllowed"] is False
    assert result["checks"]["cadReconstructionPassed"] is True
    assert result["checks"]["validateOnlyRelationsPassed"] is True
    assert result["checks"]["zeroUnacceptedInterference"] is False
    assert "原型基线" in result["blockingIssues"][0]


def test_incomplete_exact_check_is_not_treated_as_safe():
    result = build_semantic_assembly_release_gate(reconstruction(), interference(complete=False))
    assert result["releaseAllowed"] is False
    assert result["checks"]["exactInterferenceCheckComplete"] is False


def test_failed_validation_relation_rejects_release():
    result = build_semantic_assembly_release_gate(
        reconstruction(validation_passed=False), interference()
    )
    assert result["releaseAllowed"] is False
    assert result["checks"]["validateOnlyRelationsPassed"] is False


def test_cli_wrapper_reads_tool_result_validation():
    result = build_semantic_assembly_release_gate(
        {"success": True, "toolResult": reconstruction()}, interference()
    )
    assert result["releaseAllowed"] is True
    assert result["checks"]["validateOnlyRelationCount"] == 1


def exact_pair(*pairs):
    return {
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Path": first[0], "Name": f"changed/root/{first[1]}"},
                "SecondComponent": {"Path": second[0], "Name": f"other/root/{second[1]}"},
            }
            for first, second in pairs
        ]
    }


def test_baseline_comparison_ignores_changed_root_but_preserves_instance_identity():
    shared = (("C:/models/part.sldprt", "part-1"), ("C:/models/tool.sldprt", "tool-1"))
    added = (("C:/models/part.sldprt", "part-2"), ("C:/models/tool.sldprt", "tool-1"))
    result = compare_interference_pair_to_baseline(exact_pair(shared, added), exact_pair(shared))
    assert result["acceptedBaselineMatchCount"] == 1
    assert result["newInterferenceCount"] == 1
    assert result["passesNoNewInterferenceGate"] is False


def test_release_accepts_only_fully_covered_baseline_interference():
    report = interference(1)
    result = build_semantic_assembly_release_gate(
        reconstruction(),
        report,
        [{"acceptedBaselineMatchCount": 4, "newInterferenceCount": 0, "passesNoNewInterferenceGate": True}],
    )
    assert result["releaseAllowed"] is True
    assert result["interferenceSummary"]["baselineAcceptedInterferenceCount"] == 4


def test_release_accepts_complete_conditional_batch_with_only_baseline_interference():
    batch = {
        "requestedPairCount": 3,
        "completedPairCount": 3,
        "pairs": [
            {
                "pair": ["A500", "A700"],
                "hasInterference": False,
                "exactCheckComplete": True,
                "failedBodyPairCount": 0,
                "acceptance": {"policy": "zeroInterference", "accepted": True},
            },
            {
                "pair": ["A500", "A600"],
                "hasInterference": False,
                "exactCheckComplete": True,
                "failedBodyPairCount": 0,
                "acceptance": {"policy": "zeroInterference", "accepted": True},
            },
            {
                "pair": ["A600", "A700"],
                "hasInterference": True,
                "interferingBodyPairCount": 4,
                "exactCheckComplete": True,
                "failedBodyPairCount": 0,
                "acceptance": {
                    "policy": "noNewInterferenceOverAcceptedBaseline",
                    "accepted": True,
                    "baselinePath": "prototype.json",
                    "baselineInterferingPairCount": 4,
                    "addedInterferingPairs": [],
                    "missingBaselinePairs": [],
                },
            },
        ],
    }
    result = build_semantic_assembly_release_gate(reconstruction(), batch)
    assert result["releaseAllowed"] is True
    assert result["checks"]["exactInterferenceCheckComplete"] is True
    assert result["interferenceSummary"]["baselineAcceptedInterferenceCount"] == 4
    assert result["interferenceSummary"]["newInterferenceCount"] == 0


def test_release_rejects_conditional_batch_with_added_interference():
    batch = {
        "requestedPairCount": 1,
        "completedPairCount": 1,
        "pairs": [
            {
                "pair": ["A500", "A700"],
                "hasInterference": True,
                "exactCheckComplete": True,
                "failedBodyPairCount": 0,
                "acceptance": {
                    "policy": "noNewInterferenceOverAcceptedBaseline",
                    "accepted": False,
                    "baselinePath": "prototype.json",
                    "baselineInterferingPairCount": 0,
                    "addedInterferingPairs": [["new-a", "new-b"]],
                },
            }
        ],
    }
    result = build_semantic_assembly_release_gate(reconstruction(), batch)
    assert result["releaseAllowed"] is False
    assert result["interferenceSummary"]["newInterferenceCount"] == 1

from __future__ import annotations

from typing import Any


STRICT_SCHEMA = "checkpoint-selected-face-context-insert-run/v1"
LEGACY_SCHEMA = "context-incremental-insert-run/v1"


def assess_external_placement_repeatability(
    baseline: dict[str, Any],
    confirmation: dict[str, Any],
    confirmation_graph: dict[str, Any],
    *,
    expected_mate_count: int,
) -> dict[str, Any]:
    """Validate a two-seed, zero-anchor external root-pose witness."""

    first = assess_driving_insert_evidence(
        baseline, expected_mate_count=expected_mate_count
    )
    second = assess_driving_insert_evidence(
        confirmation, expected_mate_count=expected_mate_count
    )
    first_tool = baseline.get("toolResult") or {}
    second_tool = confirmation.get("toolResult") or {}
    audit = confirmation_graph.get("ExternalPlacementRepeatabilityAudit") or {}
    first_transform = first_tool.get("ReopenedTargetRootTransform")
    witness_transform = audit.get("witnessTransform")
    checks = {
        "baselineCheckpointPassed": first.get("checkpointPassed") is True,
        "confirmationCheckpointPassed": second.get("checkpointPassed") is True,
        "baselineAnchorFree": (
            first_tool.get("TargetCaseAnchored") is False
            and int(first_tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(first_tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
        ),
        "confirmationAnchorFree": (
            second_tool.get("TargetCaseAnchored") is False
            and int(second_tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(second_tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
        ),
        "differentInitialPlacementVariant": (
            int(audit.get("initialPlacementVariant") or 0) > 0
        ),
        "witnessIsValidationOnly": audit.get("witnessIsValidationOnly") is True,
        "witnessDoesNotUsePoseAnchor": audit.get("poseAnchorUsed") is False,
        "witnessMatchesBaselineRootTransform": (
            isinstance(first_transform, list)
            and len(first_transform) >= 13
            and witness_transform == first_transform
        ),
        "witnessMatchesBaselineArtifact": (
            bool(baseline.get("outputAssemblySha256"))
            and audit.get("firstRunOutputAssemblySha256")
            == baseline.get("outputAssemblySha256")
        ),
        "confirmationConvergedToWitness": (
            second_tool.get("ExternalPlacementEquivalencePassed") is True
        ),
    }
    return {
        "schemaVersion": "external-placement-repeatability-assessment/v1",
        "passed": all(checks.values()),
        "checks": checks,
        "baselineAssessment": first,
        "confirmationAssessment": second,
        "translationErrorMeters": second_tool.get(
            "ExternalPlacementTranslationErrorMeters"
        ),
        "rotationError": second_tool.get("ExternalPlacementRotationError"),
    }


def assess_driving_insert_evidence(
    payload: dict[str, Any],
    *,
    expected_mate_count: int | None = None,
) -> dict[str, Any]:
    """Assess whether one CAD insert proves portable mate-driven placement.

    The legacy envelope already proves that the target was inserted from an
    independent module at a deterministic non-source pose.  It does not prove
    that the source/output documents were left unchanged and closed, so it is
    useful historical evidence but cannot authorize a release by itself.
    """

    tool = payload.get("toolResult") or {}
    requested = int(tool.get("RequestedMateCount") or 0)
    created = int(tool.get("CreatedMateCount") or 0)
    mate_results = list(tool.get("MateResults") or [])
    verifications = list(tool.get("MateVerifications") or [])
    validations = list(tool.get("ValidationResults") or [])
    expected = requested if expected_mate_count is None else int(expected_mate_count)

    target_fully_constrained = tool.get("TargetFullyConstrained") is True
    target_constraint_state_accepted = (
        tool.get("TargetConstraintStateAccepted") is True
    )
    external_placement_equivalence_proven = bool(
        target_fully_constrained
        or tool.get("ExternalPlacementEquivalencePassed") is True
    )
    semantic_checks = {
        "runSucceeded": payload.get("success") is True and tool.get("Success") is True,
        "contextIncrementalInsertMode": (
            tool.get("ExecutionMode") == "context_incremental_insert"
        ),
        "independentComponentInserted": (
            tool.get("IndependentComponentInserted") is True
        ),
        "originalTargetRemovedOrConfirmedAbsent": (
            tool.get("OriginalComponentRemoved") is True
        ),
        "casePoseAnchorNotUsed": tool.get("TargetCaseAnchored") is False,
        "leafPoseAnchorNotUsed": (
            int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
        ),
        "positiveExpectedMateCount": expected > 0,
        "mateCountMatches": requested == expected and created == expected,
        "mateCreationPassed": (
            len(mate_results) == expected
            and all(row.get("Success") is True for row in mate_results)
        ),
        "reopenMateVerificationPassed": (
            len(verifications) == expected
            and all(
                row.get("Found") is True
                and row.get("TypeMatches") is True
                and row.get("AlignmentMatches") is True
                and row.get("DistanceMatches") is True
                and row.get("AngleMatches") is True
                and row.get("AdvancedOptionsMatch") is True
                for row in verifications
            )
        ),
        "readOnlyRelationsPassed": all(
            row.get("EndpointsResolved", True) is True
            and row.get("Passed", True) is True
            for row in validations
        ),
        "reopened": tool.get("Reopened") is True,
        "reopenedMateParametersMatch": (
            tool.get("ReopenedMateParametersMatch") is True
        ),
        # SOLIDWORKS reports a flexible subassembly as not fully constrained
        # when its internal mechanism remains movable.  That observation alone
        # does not prove external placement: internal motion can absorb parent
        # mates while the whole module follows a wrong pose branch.
        "targetConstraintStateAccepted": target_constraint_state_accepted,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "componentSemanticsMatch": tool.get("ComponentSemanticsMatch") is True,
    }
    semantic_passed = all(semantic_checks.values())
    schema = str(payload.get("schemaVersion") or "")
    checkpoint_checks = {
        "checkpointEnvelope": schema == STRICT_SCHEMA,
        "sourceAssemblyUnchanged": payload.get("sourceAssemblyUnchanged") is True,
        "outputSaved": bool(payload.get("outputAssemblySha256")),
        "outputClosedAfterVerification": (
            payload.get("outputClosedAfterVerification") is True
        ),
        "targetSourceSessionClean": (
            payload.get("targetSourceSessionClean") is True
        ),
    }
    checkpoint_passed = semantic_passed and all(checkpoint_checks.values())
    if checkpoint_passed:
        status = "release_candidate"
    elif semantic_passed and schema == LEGACY_SCHEMA:
        status = "checkpoint_refresh_required"
    else:
        status = "blocked"
    blockers = [
        key
        for key, value in {**semantic_checks, **checkpoint_checks}.items()
        if value is not True
    ]
    return {
        "schemaVersion": "global-cad-driving-evidence-assessment/v1",
        "status": status,
        "evidenceSchemaVersion": schema,
        "targetModuleToken": payload.get("targetModuleToken")
        or tool.get("TargetModuleToken"),
        "requestedMateCount": requested,
        "createdMateCount": created,
        "semanticChecks": semantic_checks,
        "constraintStateObservation": {
            "targetFullyConstrained": target_fully_constrained,
            "targetConstraintStateAccepted": target_constraint_state_accepted,
            "acceptedFlexibleInternalState": (
                target_constraint_state_accepted and not target_fully_constrained
            ),
            "externalPlacementEquivalenceProven": (
                external_placement_equivalence_proven
            ),
            "residualDofScope": (
                "internal_mechanism"
                if not target_fully_constrained
                and external_placement_equivalence_proven
                else "none"
                if target_fully_constrained
                else "unclassified_without_external_placement_witness"
            ),
        },
        "checkpointChecks": checkpoint_checks,
        "semanticPassed": semantic_passed,
        "checkpointPassed": checkpoint_passed,
        "portablePlacementProven": (
            checkpoint_passed and external_placement_equivalence_proven
        ),
        "blockers": blockers,
    }

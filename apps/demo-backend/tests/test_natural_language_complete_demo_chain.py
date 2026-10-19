from copy import deepcopy

from demo_backend.natural_language_complete_demo_chain import (
    build_complete_demo_chain_closure,
)


def _job():
    steps = []
    for index, token in enumerate(("SS00", "AI00", "BD00"), start=1):
        steps.append(
            {
                "stepId": f"packet-{index:03d}",
                "moduleToken": token,
                "status": "succeeded",
                "attemptCount": 1,
                "attempts": [{"durationSeconds": 10.0}],
            }
        )
    return {
        "schemaVersion": "ordered-assembly-job/v2",
        "jobId": "job",
        "status": "succeeded",
        "assemblyStatus": "assembled",
        "collisionStatus": "not_evaluated",
        "executionDurationSeconds": 30,
        "plan": {
            "relationReleaseBinding": {"releaseId": "release"},
            "commandAudit": {"payload": {"commands": []}},
        },
        "steps": steps,
        "lastCommittedCheckpoint": {"assemblyPath": "three.sldasm"},
    }


def _results():
    values = []
    previous = None
    for index in range(1, 4):
        output = f"{index}.sldasm"
        values.append(
            {
                "success": True,
                "sourceAssemblyPath": previous or "base.sldasm",
                "outputAssemblyPath": output,
                "sourceAssemblyUnchanged": True,
                "outputAssemblySha256": f"sha256-{index}",
                "outputClosedAfterVerification": True,
                "targetSourceSessionClean": True,
                "toolResult": {
                    "Success": True,
                    "RequestedMateCount": 3,
                    "CreatedMateCount": 3,
                    "MateResults": [{"Success": True} for _ in range(3)],
                    "MateVerifications": [
                        {
                            "Found": True,
                            "TypeMatches": True,
                            "AlignmentMatches": True,
                            "DistanceMatches": True,
                            "AngleMatches": True,
                            "AdvancedOptionsMatch": True,
                        }
                        for _ in range(3)
                    ],
                    "TargetFullyConstrained": True,
                    "TargetConstraintStateAccepted": True,
                    "MateSolveClean": True,
                    "Reopened": True,
                    "ReopenedMateParametersMatch": True,
                    "TargetCaseAnchored": False,
                    "RequestedTargetLeafPoseAnchorCount": 0,
                    "AppliedTargetLeafPoseAnchorCount": 0,
                },
            }
        )
        previous = output
    return values


def _build(job=None, results=None, process="pending", **kwargs):
    return build_complete_demo_chain_closure(
        job or _job(),
        results or _results(),
        expected_release_id="release",
        expected_order=["SS00", "AI00", "BD00"],
        base_module_token="AA00",
        scanner_process_status=process,
        **kwargs,
    )


def test_mechanical_chain_passes_without_overclaiming_optical_process():
    report = _build()
    assert report["mechanicalDemoChainPassed"] is True
    assert report["completeFunctionalDemoPassed"] is False
    assert report["status"] == "mechanical_demo_chain_passed_scanner_process_pending"
    assert report["moduleSequence"] == ["AA00", "SS00", "AI00", "BD00"]


def test_complete_status_requires_explicit_scanner_process_pass():
    report = _build(process="passed")
    assert report["completeFunctionalDemoPassed"] is True
    assert report["status"] == "complete_demo_chain_passed"


def test_coarse_process_evidence_is_reported_as_partial_not_complete():
    report = _build(
        process="coarse_geometry_compatible_working_distance_unconfirmed"
    )
    assert report["mechanicalDemoChainPassed"] is True
    assert report["completeFunctionalDemoPassed"] is False
    assert report["status"] == (
        "mechanical_demo_chain_passed_scanner_process_partial"
    )
    assert report["nextAction"] == (
        "confirm-ai00-working-distance-range-and-register-ss00-barcode-surface"
    )


def test_static_demo_proxy_closes_demo_without_claiming_production():
    report = _build(process="static_demo_passed_barcode_surface_proxy")
    assert report["status"] == "complete_demo_chain_passed"
    assert report["completeFunctionalDemoPassed"] is True
    assert report["scannerProcessValidation"]["evidenceLevel"] == "static_demo_proxy"
    assert report["scannerProcessValidation"]["productionReady"] is False


def test_broken_checkpoint_chain_fails_mechanical_closure():
    results = _results()
    results[2]["sourceAssemblyPath"] = "wrong.sldasm"
    report = _build(results=results)
    assert report["checks"]["cumulativeCheckpointChain"] is False
    assert report["mechanicalDemoChainPassed"] is False


def test_missing_reopen_gate_fails_mechanical_closure():
    results = _results()
    results[1]["toolResult"]["ReopenedMateParametersMatch"] = False
    report = _build(results=results)
    assert report["checks"]["packet2CadPassed"] is False
    assert report["mechanicalDemoChainPassed"] is False


def test_pose_anchor_or_unclosed_output_fails_mechanical_closure():
    results = _results()
    results[0]["toolResult"]["TargetCaseAnchored"] = True
    results[2]["outputClosedAfterVerification"] = False
    report = _build(results=results)
    assert report["checks"]["packet1CadPassed"] is False
    assert report["checks"]["packet3CadPassed"] is False
    assert report["mechanicalDemoChainPassed"] is False


def test_mixed_positive_mate_bundle_sizes_are_supported():
    results = _results()
    tool = results[1]["toolResult"]
    tool["RequestedMateCount"] = 4
    tool["CreatedMateCount"] = 4
    tool["MateResults"] = [{"Success": True} for _ in range(4)]
    tool["MateVerifications"] = [
        {
            "Found": True,
            "TypeMatches": True,
            "AlignmentMatches": True,
            "DistanceMatches": True,
            "AngleMatches": True,
            "AdvancedOptionsMatch": True,
        }
        for _ in range(4)
    ]
    report = _build(results=results)
    assert report["checks"]["packet2CadPassed"] is True
    assert report["mechanicalDemoChainPassed"] is True


def test_flexible_module_passes_with_explicit_external_placement_equivalence():
    results = _results()
    tool = results[1]["toolResult"]
    tool["TargetFullyConstrained"] = False
    tool["ExternalPlacementEquivalencePassed"] = True
    report = _build(results=results)
    assert report["checks"]["packet2CadPassed"] is True
    assert report["cadPackets"][1]["fullyConstrained"] is False
    assert report["cadPackets"][1]["externalPlacementEquivalencePassed"] is True
    assert report["cadPackets"][1]["externalPlacementProven"] is True
    assert report["mechanicalDemoChainPassed"] is True


def test_flexible_module_without_external_placement_proof_is_blocked():
    results = _results()
    tool = results[1]["toolResult"]
    tool["TargetFullyConstrained"] = False
    tool.pop("ExternalPlacementEquivalencePassed", None)
    report = _build(results=results)
    assert report["checks"]["packet2CadPassed"] is False
    assert report["cadPackets"][1]["externalPlacementEquivalencePassed"] is None
    assert report["cadPackets"][1]["externalPlacementProven"] is False
    assert report["mechanicalDemoChainPassed"] is False


def test_flexible_module_accepts_exact_release_bound_two_pose_proof():
    job = _job()
    job["plan"]["relationReleaseBinding"].update(
        {
            "releaseDigest": "release-digest",
            "catalogDigest": "catalog-digest",
            "authorizedDrivingTemplateIds": ["template-flexible"],
        }
    )
    results = _results()
    tool = results[1]["toolResult"]
    tool["TargetFullyConstrained"] = False
    tool.pop("ExternalPlacementEquivalencePassed", None)
    release_manifest = {
        "releaseId": "release",
        "releaseDigest": "release-digest",
        "catalogDigest": "catalog-digest",
    }
    release_evidence = {
        "outputCatalogDigest": "catalog-digest",
        "derivations": [
            {
                "entry": {"legacyTemplateId": "flexible_v1"},
                "result": {"derivedGlobalTemplateId": "template-flexible"},
            }
        ],
        "cadAssessments": {
            "flexible_v1": {
                "portablePlacementProven": True,
                "externalPlacementRepeatability": {"passed": True},
            }
        },
    }
    report = _build(
        job=job,
        results=results,
        packet_template_ids=["template-1", "template-flexible", "template-3"],
        release_manifest=release_manifest,
        release_evidence=release_evidence,
    )
    assert report["checks"]["packet2CadPassed"] is True
    assert report["cadPackets"][1]["externalPlacementProven"] is True
    assert report["cadPackets"][1]["externalPlacementEvidenceSource"] == (
        "immutable_release_two_pose_repeatability"
    )


def test_release_level_proof_cannot_mask_anchor_or_release_mismatch():
    job = _job()
    job["plan"]["relationReleaseBinding"].update(
        {
            "releaseDigest": "release-digest",
            "catalogDigest": "catalog-digest",
            "authorizedDrivingTemplateIds": ["template-flexible"],
        }
    )
    results = _results()
    tool = results[1]["toolResult"]
    tool["TargetFullyConstrained"] = False
    tool["TargetCaseAnchored"] = True
    report = _build(
        job=job,
        results=results,
        packet_template_ids=["template-1", "template-flexible", "template-3"],
        release_manifest={
            "releaseId": "release",
            "releaseDigest": "wrong-release-digest",
            "catalogDigest": "catalog-digest",
        },
        release_evidence={
            "outputCatalogDigest": "catalog-digest",
            "derivations": [
                {
                    "entry": {"legacyTemplateId": "flexible_v1"},
                    "result": {"derivedGlobalTemplateId": "template-flexible"},
                }
            ],
            "cadAssessments": {
                "flexible_v1": {
                    "portablePlacementProven": True,
                    "externalPlacementRepeatability": {"passed": True},
                }
            },
        },
    )
    assert report["checks"]["packet2CadPassed"] is False
    assert report["cadPackets"][1]["releasePlacementProofBound"] is False
    assert report["cadPackets"][1]["externalPlacementEvidenceSource"] == "missing"


def test_digest_is_deterministic():
    assert _build()["closureDigest"] == _build()["closureDigest"]

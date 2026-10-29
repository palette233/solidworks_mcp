"""Evidence regression for two compiled six-role, multi-base CAD chains.

The artifacts are deliberately compile-only.  This test proves authority selection,
stage ordering and immutable release bindings; it must not claim CAD execution.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from demo_backend.multi_release_cad_chain import validate_multi_release_cad_chain


REPO = Path(__file__).resolve().parents[3]
PACKAGE = (
    REPO
    / "demo/cross_project_substitution/"
    "multi-base-six-role-preflight-20261026-v1"
)


CASES = {
    "a600-cross-model-reordered-compiled": {
        "base": "cad/fl9a24d062a600-001-1/66606c07c8cf",
        "stages": [
            ("s01-bd00", "direct_installation"),
            ("s02-a800", "direct_installation"),
            ("s03-n000", "datum_placement_demo"),
            ("s04-p000", "datum_placement_demo"),
            ("s05-ai00", "datum_placement_demo"),
        ],
        "projects": {"project01", "project02", "project03", "project05"},
    },
    "a000-cross-model-reordered-compiled": {
        "base": "cad/fl9c254098a000-001/b98ba8912621",
        "stages": [
            ("s01-p000", "direct_installation"),
            ("s02-a180", "datum_placement_demo"),
            ("s03-d000", "direct_installation"),
            ("s04-g000", "direct_installation"),
            ("s05-ag00", "datum_placement_demo"),
        ],
        "projects": {"project02", "project03", "project05"},
    },
}


EXECUTED_CASES = {
    "a6": {
        "lastStage": "05ai",
        "order": ["BD00", "A800", "N000", "P000", "AI00"],
        "runSeconds": 798.3974483000347,
    },
    "a0": {
        "lastStage": "05ag",
        "order": ["P000", "A180", "D000", "G000", "AG00"],
        "runSeconds": 669.7066821999615,
    },
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_multi_base_six_role_requests_bind_released_authority_without_cad_claims():
    observed_orders = []
    for folder, expected in CASES.items():
        root = PACKAGE / folder
        compilation = _read(root / "compilation.json")
        chain = _read(root / "chain.json")
        request = compilation["request"]

        validate_multi_release_cad_chain(REPO, chain)
        assert compilation["status"] == "ready_not_started"
        assert compilation["cadStarted"] is False
        assert compilation["collisionOrBrep"] == "not_evaluated"
        assert compilation["actualFasteningMethod"] == "not_verified"
        assert chain["status"] == "ready_for_staged_execution"
        assert chain["stageCount"] == chain["packetCount"] == 5
        assert len(request["steps"]) == 5
        assert {request["baseSelection"]["projectId"], *(
            step["moduleSelection"]["projectId"] for step in request["steps"]
        )} == expected["projects"]

        actual = []
        for step, chain_stage in zip(request["steps"], chain["stages"], strict=True):
            stage_id = step["stageId"]
            authority = _read(root / stage_id / "interface-authority-decision.json")
            report = _read(root / stage_id / "natural-language-compilation.json")
            mode = authority["relationExecutionMode"]
            actual.append((stage_id, mode))
            assert authority["ready"] is True
            assert authority["source"] == "confirmed_module_and_slot_planner"
            assert authority["confirmedSlotDefinitionId"] == expected["base"]
            assert report["success"] is True
            assert report["status"] == "job_created_not_started"
            assert chain_stage["relationExecutionMode"] == mode
            assert chain_stage["releaseDigest"]
            if mode == "datum_placement_demo":
                assert step.get("allowDatumFallback") is True
            else:
                assert step.get("allowDatumFallback") is not True

        assert actual == expected["stages"]
        observed_orders.append([stage for stage, _mode in actual])

    assert observed_orders[0] != observed_orders[1]


def test_executed_multi_base_six_role_chains_have_real_closed_cad_evidence():
    observed_orders = []
    for folder, expected in EXECUTED_CASES.items():
        root = REPO / "demo/c6" / folder
        chain = _read(root / "chain.json")
        run = _read(sorted((root / "run-attempts").glob("*.json"))[-1])
        validate_multi_release_cad_chain(REPO, chain)
        assert run["success"] is True
        assert run["collisionOrBrep"] == "not_evaluated"
        assert run["actualFasteningMethod"] == "not_verified"
        assert run["durationSeconds"] == expected["runSeconds"]
        assert len(chain["stages"]) == len(run["stages"]) == 5

        previous_output = None
        tokens = []
        for stage in chain["stages"]:
            stage_id = stage["stageId"]
            closure = _read(root / stage_id / "stage-closure.json")
            job = _read(root / "jobs" / closure["jobId"] / "job.json")
            checkpoint = job["steps"][-1]["checkpoint"]
            cad_result = _read(Path(checkpoint["cadActionEvidencePaths"][2]))
            tool = cad_result["toolResult"]
            output = Path(closure["finalAssemblyPath"])

            assert closure["status"] == "passed"
            assert all(closure["checks"].values())
            assert job["status"] == "succeeded"
            assert checkpoint["validationEvidenceKind"] == "cad-packet-save-close-reopen-envelope"
            assert checkpoint["inputAssemblyPath"] == previous_output
            assert output.is_file()
            assert hashlib.sha256(output.read_bytes()).hexdigest() == closure["finalAssemblySha256"]
            assert cad_result["success"] is True
            assert cad_result["sourceAssemblyUnchanged"] is True
            assert cad_result["outputClosedAfterVerification"] is True
            assert cad_result["targetSourceSessionClean"] is True
            assert cad_result["documentBaselineCleanup"]["sessionRestored"] is True
            assert tool["IndependentComponentInserted"] is True
            assert tool["TargetCaseAnchored"] is False
            assert tool["RequestedTargetLeafPoseAnchorCount"] == 0
            assert tool["AppliedTargetLeafPoseAnchorCount"] == 0
            assert tool["RequestedMateCount"] == tool["CreatedMateCount"] > 0
            assert all(row["Success"] for row in tool["MateResults"])
            assert tool["Reopened"] is True
            assert tool["ReopenedMateParametersMatch"] is True
            assert tool["TargetConstraintStateAccepted"] is True
            assert tool["MateSolveClean"] is True
            assert tool["ComponentSemanticsMatch"] is True
            if tool["TargetFullyConstrained"] is not True:
                # G000 is a flexible subassembly.  Its immutable relation release
                # must prove the external root pose with two distinct initial seeds;
                # a single runtime flag may still reflect its internal mechanism.
                assert tool["TargetModuleToken"] == "G000"
                authority = _read(root / stage_id / "interface-authority-decision.json")
                release = _read(REPO / authority["releaseManifestPath"])
                evidence = _read(Path(release["derivationEvidencePath"]))
                assessments = list((evidence.get("cadAssessments") or {}).values())
                assert len(assessments) == 1
                assessment = assessments[0]
                observation = assessment["constraintStateObservation"]
                repeatability = assessment["externalPlacementRepeatability"]
                assert assessment["portablePlacementProven"] is True
                assert observation["acceptedFlexibleInternalState"] is True
                assert observation["residualDofScope"] == "internal_mechanism"
                assert repeatability["passed"] is True
                assert repeatability["checks"]["differentInitialPlacementVariant"] is True
                assert repeatability["checks"]["confirmationConvergedToWitness"] is True
            assert checkpoint["collisionStatus"] == "not_evaluated"
            previous_output = str(output)
            tokens.append(tool["TargetModuleToken"])

        assert tokens == expected["order"]
        assert run["lastCommittedClosurePath"] == str(root / expected["lastStage"] / "stage-closure.json")
        observed_orders.append(tokens)

    assert observed_orders[0] != observed_orders[1]

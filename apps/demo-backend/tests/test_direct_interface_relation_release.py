import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import pytest

from demo_backend.direct_interface_relation_release import (
    build_direct_interface_pair_release,
    derive_direct_interface_relation_release_id,
    ensure_direct_interface_relation_release,
    plan_direct_interface_cad_validation,
    publish_direct_interface_relation_release,
)
from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)
from demo_backend.global_interface_contract_planner import (
    _release_manifest_matches_pair_evidence,
)
from demo_backend.global_relation_catalog_release import (
    GlobalRelationCatalogReleaseError,
    load_relation_catalog_release,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / (
    "demo/cross_project_substitution/calibration-project01-to-project02-v1/"
    "bd00-a600-validation-v3"
)
BASE_CATALOG = ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _validation(tmp_path: Path) -> Path:
    validation = tmp_path / "validation"
    shutil.copytree(SOURCE, validation)
    for path in list(validation.iterdir()):
        if path.name in {
            "cad-result.json",
            "pair-release.json",
            "relation-release-binding.json",
        } or path.name.endswith(".SLDASM") or path.name.endswith(".progress.jsonl"):
            path.unlink()
    package_path = validation / "validation-package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    graph = validation / "effective-mate-graph.json"
    endpoints = validation / "selected-face-endpoint-catalog.json"
    package["artifacts"] = {
        "effectiveGraph": {"path": str(graph), "sha256": _sha(graph)},
        "selectedEndpointCatalog": {
            "path": str(endpoints),
            "sha256": _sha(endpoints),
        },
    }
    _write(package_path, package)
    output = validation / "bd00-a600-direct-validation.SLDASM"
    output.write_bytes(b"synthetic-test-assembly")
    mate_results = [{"Success": True} for _ in range(3)]
    verifications = [
        {
            "Found": True,
            "TypeMatches": True,
            "AlignmentMatches": True,
            "DistanceMatches": True,
            "AngleMatches": True,
            "AdvancedOptionsMatch": True,
        }
        for _ in range(3)
    ]
    result = {
        "schemaVersion": "checkpoint-selected-face-context-insert-run/v1",
        "success": True,
        "effectiveGraphSha256": _sha(graph),
        "sourceAssemblyUnchanged": True,
        "outputClosedAfterVerification": True,
        "targetSourceSessionClean": True,
        "durationSeconds": 1.0,
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": _sha(output),
        "toolResult": {
            "Success": True,
            "ExecutionMode": "context_incremental_insert",
            "OriginalComponentRemoved": True,
            "IndependentComponentInserted": True,
            "TargetCaseAnchored": False,
            "RequestedTargetLeafPoseAnchorCount": 0,
            "AppliedTargetLeafPoseAnchorCount": 0,
            "RequestedMateCount": 3,
            "CreatedMateCount": 3,
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "TargetConstraintStateAccepted": True,
            "TargetFullyConstrained": True,
            "MateSolveClean": True,
            "ComponentSemanticsMatch": True,
            "MateResults": mate_results,
            "MateVerifications": verifications,
        },
    }
    _write(validation / "cad-result.json", result)
    pair = build_direct_interface_pair_release(validation)
    _write(validation / "pair-release.json", pair)
    return validation


def _candidate(tmp_path: Path) -> Path:
    validation = tmp_path / "candidate"
    shutil.copytree(SOURCE, validation)
    for path in list(validation.iterdir()):
        if path.name in {
            "cad-result.json",
            "pair-release.json",
            "relation-release-binding.json",
        } or path.name.endswith(".SLDASM") or path.name.endswith(".progress.jsonl"):
            path.unlink()
    package_path = validation / "validation-package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    graph = validation / "effective-mate-graph.json"
    endpoints = validation / "selected-face-endpoint-catalog.json"
    package["artifacts"] = {
        "effectiveGraph": {"path": str(graph), "sha256": _sha(graph)},
        "selectedEndpointCatalog": {
            "path": str(endpoints),
            "sha256": _sha(endpoints),
        },
    }
    _write(package_path, package)
    return validation


def test_direct_pair_release_is_nonprototype_and_exact_pair_bound(tmp_path: Path):
    validation = _validation(tmp_path)
    pair = json.loads((validation / "pair-release.json").read_text(encoding="utf-8"))
    assert pair["moduleDefinitionId"] == "project01::BD00"
    assert pair["slotDefinitionId"] == "project02::A600"
    assert pair["directMechanicalInterfaceCompatible"] is True
    assert pair["nonPrototypeCadValidated"] is True
    assert pair["physicalFasteningVerified"] is False
    assert pair["collisionOrBrep"] == "not_evaluated"
    assert all(pair["checks"].values())


def test_direct_relation_release_registers_standard_execution_authority(tmp_path: Path):
    sandbox = Path(
        tempfile.mkdtemp(prefix=".tmp-direct-relation-release-", dir=ROOT / "demo")
    )
    validation = _validation(sandbox)
    release_root = sandbox / "releases"
    try:
        result = publish_direct_interface_relation_release(
            ROOT,
            validation,
            "relation-direct-bd00-a600-test",
            BASE_CATALOG,
            output_root=release_root,
        )
        assert result["relationExecutionMode"] == "direct_installation"
        assert result["moduleDefinitionId"] == "project01::BD00"
        assert result["slotDefinitionId"] == "project02::A600"
        manifest = (
            release_root
            / "relation-direct-bd00-a600-test/release-manifest.json"
        )
        assert manifest.is_file()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        binding = payload["releaseMetadata"]["directInterfacePairBinding"]
        assert binding["releaseDigest"] == json.loads(
            (validation / "pair-release.json").read_text(encoding="utf-8")
        )["releaseDigest"]
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def test_direct_relation_release_rechecks_bound_cad_artifacts(tmp_path: Path):
    sandbox = Path(
        tempfile.mkdtemp(prefix=".tmp-direct-release-tamper-", dir=ROOT / "demo")
    )
    validation = _validation(sandbox)
    release_root = sandbox / "releases"
    try:
        publish_direct_interface_relation_release(
            ROOT,
            validation,
            "relation-direct-bd00-a600-tamper-test",
            BASE_CATALOG,
            output_root=release_root,
        )
        output = Path(
            json.loads(
                (validation / "pair-release.json").read_text(encoding="utf-8")
            )["outputAssemblyPath"]
        )
        output.write_bytes(b"tampered-after-publication")
        with pytest.raises(
            GlobalRelationCatalogReleaseError, match="outputAssemblyPath"
        ):
            load_relation_catalog_release(
                release_root
                / "relation-direct-bd00-a600-tamper-test/release-manifest.json",
                workspace_root=ROOT,
            )
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def test_direct_pair_release_fails_closed_when_target_is_not_constrained(tmp_path: Path):
    validation = _validation(tmp_path)
    result_path = validation / "cad-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["toolResult"]["TargetFullyConstrained"] = False
    _write(result_path, result)
    with pytest.raises(MechanicalInterfaceContractError, match="targetFullyConstrained"):
        build_direct_interface_pair_release(validation)


def test_direct_cad_plan_is_zero_document_nonprototype_and_exact_pair_bound(
    tmp_path: Path,
):
    validation = _candidate(tmp_path)
    plan = plan_direct_interface_cad_validation(ROOT, validation)
    assert plan["moduleDefinitionId"] == "project01::BD00"
    assert plan["slotDefinitionId"] == "project02::A600"
    assert plan["command"][1].endswith("run_context_mate_graph_insert.py")
    assert plan["command"][plan["command"].index("--target") + 1] == "BD00"
    assert plan["preconditions"] == {
        "solidWorksOpenDocumentCountMustEqual": 0,
        "nonPrototypeInitialPoseRequired": True,
        "saveCloseReopenRequired": True,
        "stopQueueOnFailure": True,
    }
    assert not Path(plan["outputAssemblyPath"]).exists()
    assert not Path(plan["cadResultPath"]).exists()


def test_direct_relation_release_id_is_deterministic_and_pair_bound(tmp_path: Path):
    validation = _validation(tmp_path)
    pair = json.loads((validation / "pair-release.json").read_text(encoding="utf-8"))
    first = derive_direct_interface_relation_release_id(pair)
    second = derive_direct_interface_relation_release_id(pair)
    assert first == second
    assert first.startswith("relation-direct-project01-bd00-project02-a600-")


def test_released_authority_matcher_accepts_embedded_direct_pair_binding(tmp_path: Path):
    validation = _validation(tmp_path)
    pair = json.loads((validation / "pair-release.json").read_text(encoding="utf-8"))
    manifest = {
        "releaseId": "relation-wrapper",
        "releaseDigest": "0" * 64,
        "releaseMetadata": {"directInterfacePairBinding": pair},
    }
    assert _release_manifest_matches_pair_evidence(manifest, pair) is True


def test_direct_publication_recovery_is_idempotent_without_cad_rerun(tmp_path: Path):
    sandbox = Path(
        tempfile.mkdtemp(prefix=".tmp-direct-release-recovery-", dir=ROOT / "demo")
    )
    validation = _validation(sandbox)
    release_root = sandbox / "releases"
    try:
        first = ensure_direct_interface_relation_release(
            ROOT,
            validation,
            BASE_CATALOG,
            output_root=release_root,
        )
        second = ensure_direct_interface_relation_release(
            ROOT,
            validation,
            BASE_CATALOG,
            output_root=release_root,
        )
        assert first["pairReleaseCreated"] is False
        assert first["relationReleaseCreated"] is True
        assert first["cadRerun"] is False
        assert second["pairReleaseCreated"] is False
        assert second["relationReleaseCreated"] is False
        assert second["relationRelease"]["releaseId"] == first["relationRelease"][
            "releaseId"
        ]
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

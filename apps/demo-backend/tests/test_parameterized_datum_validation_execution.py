import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)
from demo_backend.parameterized_datum_validation_execution import (
    derive_parameterized_datum_relation_release_id,
    inspect_materialized_validation_queue,
    load_materialized_validation_queue,
    materialize_station_candidate_validation_queue,
    plan_next_parameterized_datum_validation,
)
from demo_backend.parameterized_datum_relation_release import (
    publish_parameterized_datum_relation_release,
)
from demo_backend.parameterized_datum_validation_queue import (
    build_parameterized_datum_validation_queue,
)


ROOT = Path(__file__).resolve().parents[3]
QUEUE = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "validation-queue-20261026-v12"
)
STALE_QUEUE = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "validation-queue-20261026-v7"
)
MIXED_QUEUE = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "validation-queue-20261026-v51"
)
STATION_CANDIDATE = ROOT / (
    "demo/station_gap_batch_20261028/p000-a600-functional-v1/planning/"
    "wastecup/validation-package.json"
)


def test_station_candidate_materializes_as_self_contained_one_item_queue(
    tmp_path: Path,
):
    output = tmp_path / "station-queue"

    result = materialize_station_candidate_validation_queue(
        ROOT, STATION_CANDIDATE, output
    )
    status = inspect_materialized_validation_queue(output)
    plan = plan_next_parameterized_datum_validation(ROOT, output)

    assert result["cadStarted"] is False
    assert status["runtimeStateCounts"] == {"pending_cad_validation": 1}
    assert plan["moduleDefinitionId"] == "project05::P000"
    assert plan["slotDefinitionId"] == "project02::A600"
    assert plan["preconditions"] == {
        "solidWorksOpenDocumentCountMustEqual": 0,
        "nonPrototypeInitialPoseRequired": True,
        "saveCloseReopenRequired": True,
        "stopQueueOnFailure": True,
        "targetStationPostcheckRequiredBeforePublication": True,
    }
    candidate = Path(result["candidateDirectory"])
    package = json.loads(
        (candidate / "validation-package.json").read_text(encoding="utf-8")
    )
    for binding in package["artifacts"].values():
        assert Path(binding["path"]).parent == candidate
    if (package.get("finiteSupportGate") or {}).get("required") is True:
        assert package["externalPlacementRepeatabilityRequired"] is True
        assert (
            package["externalPlacementRepeatabilityKind"]
            == "rigid_finite_support_pose"
        )
        assert "repeatEffectiveGraph" in package["artifacts"]
        assert plan["repeatabilityKind"] == "rigid_finite_support_pose"
        assert plan["repeatCommand"]
    assert (candidate / "station-plan.json").is_file()
    assert plan["requiresTargetStationPostcheckBeforePublication"] is True
    assert plan["stationPlanSha256"] == hashlib.sha256(
        (candidate / "station-plan.json").read_bytes()
    ).hexdigest()


def test_station_candidate_materialization_refuses_overwrite_and_tampered_graph(
    tmp_path: Path,
):
    output = tmp_path / "station-queue"
    materialize_station_candidate_validation_queue(ROOT, STATION_CANDIDATE, output)
    with pytest.raises(FileExistsError, match="overwrite"):
        materialize_station_candidate_validation_queue(
            ROOT, STATION_CANDIDATE, output
        )

    source = json.loads(STATION_CANDIDATE.read_text(encoding="utf-8"))
    graph = Path(source["artifacts"]["effectiveGraph"]["path"])
    tampered_graph = tmp_path / "tampered-graph.json"
    tampered_graph.write_bytes(graph.read_bytes() + b" ")
    source["artifacts"]["effectiveGraph"]["path"] = str(tampered_graph)
    tampered_package = tmp_path / "tampered-package.json"
    tampered_package.write_text(
        json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copy2(STATION_CANDIDATE.parent / "station-plan.json", tmp_path / "station-plan.json")
    with pytest.raises(
        MechanicalInterfaceContractError, match="artifact changed"
    ):
        materialize_station_candidate_validation_queue(
            ROOT, tampered_package, tmp_path / "tampered-queue"
        )


def test_station_candidate_cad_success_waits_for_target_station_postcheck(tmp_path: Path):
    output = tmp_path / "station-queue"
    result = materialize_station_candidate_validation_queue(
        ROOT, STATION_CANDIDATE, output
    )
    candidate = Path(result["candidateDirectory"])
    (candidate / "cad-result.json").write_text(
        json.dumps({"success": True}), encoding="utf-8"
    )
    status = inspect_materialized_validation_queue(output)
    assert status["runtimeStateCounts"] == {
        "cad_succeeded_pending_target_station_postcheck": 1
    }
    assert not (candidate / "pair-release.json").exists()
    (candidate / "station-postcheck-error.json").write_text(
        json.dumps({"stage": "target_station_postcheck"}), encoding="utf-8"
    )
    failed = inspect_materialized_validation_queue(output)
    assert failed["runtimeStateCounts"] == {
        "target_station_postcheck_failed_stop_queue": 1
    }


def test_materialized_queue_runtime_status_keeps_candidates_unreleased():
    status = inspect_materialized_validation_queue(QUEUE)
    assert status["runtimeStateCounts"] == {
        "pending_cad_validation": 6,
        "explicit_position_parameters_required": 23,
        "explicit_axis_selection_required": 3,
        "released": 15,
    }
    assert status["executionPolicy"]["cadConcurrency"] == 1


def test_historical_next_plan_fails_closed_after_catalog_publication_progress():
    with pytest.raises(MechanicalInterfaceContractError, match="stale datum catalog"):
        plan_next_parameterized_datum_validation(ROOT, QUEUE)


def test_queue_digest_change_is_rejected_before_candidate_selection(tmp_path: Path):
    queue = json.loads((QUEUE / "validation-queue.json").read_text(encoding="utf-8"))
    queue["summary"]["readyForCadValidationCount"] = 999
    target = tmp_path / "queue"
    target.mkdir()
    (target / "validation-queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with pytest.raises(MechanicalInterfaceContractError, match="digest mismatch"):
        load_materialized_validation_queue(target)


def test_queue_built_from_an_older_canonical_catalog_is_rejected():
    with pytest.raises(MechanicalInterfaceContractError, match="stale datum catalog"):
        plan_next_parameterized_datum_validation(ROOT, STALE_QUEUE)


def test_queue_planner_dispatches_materialized_direct_interface_package(tmp_path: Path):
    """A mixed datum queue must execute reviewed two-axis packages directly."""

    source_queue = json.loads(
        (MIXED_QUEUE / "validation-queue.json").read_text(encoding="utf-8")
    )
    source_row = next(
        row
        for row in source_queue["pairs"]
        if row.get("candidateKind") == "reviewed_support_plane_two_axis_slot"
    )
    source_candidate = MIXED_QUEUE / source_row["proposedValidationDirectory"]
    queue_dir = tmp_path / "mixed-queue"
    candidate = queue_dir / "validation-direct"
    candidate.mkdir(parents=True)
    shutil.copy2(
        source_candidate / "validation-package.json",
        candidate / "validation-package.json",
    )
    canonical = json.loads(
        (
            ROOT
            / "demo/cross_project_substitution/parameterized-datum-placement-v1/"
            "interface-contract-catalog.json"
        ).read_text(encoding="utf-8")
    )
    queue = {
        **source_queue,
        "sourceCatalogDigest": canonical["catalogDigest"],
        "pairs": [
            {
                **source_row,
                "proposedValidationDirectory": "validation-direct",
            }
        ],
    }
    queue.pop("queueDigest", None)
    queue["queueDigest"] = hashlib.sha256(
        json.dumps(
            queue,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    (queue_dir / "validation-queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    plan = plan_next_parameterized_datum_validation(ROOT, queue_dir)

    assert plan["packageKind"] == "direct_interface"
    assert plan["moduleDefinitionId"] == source_row["moduleDefinitionId"]
    assert plan["slotDefinitionId"] == source_row["slotDefinitionId"]
    assert plan["preconditions"]["nonPrototypeInitialPoseRequired"] is True
    assert plan["preconditions"]["saveCloseReopenRequired"] is True
    assert "run_context_mate_graph_insert.py" in " ".join(plan["command"])


def test_refresh_successor_cli_materializes_current_queue_with_lineage(tmp_path: Path):
    prior_payload = json.loads(
        (QUEUE / "validation-queue.json").read_text(encoding="utf-8")
    )
    prior_payload["sourceCatalogDigest"] = "0" * 64
    prior_payload.pop("queueDigest", None)
    prior_payload["queueDigest"] = hashlib.sha256(
        json.dumps(
            prior_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "validation-queue.json").write_text(
        json.dumps(prior_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    successor = tmp_path / "successor"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_parameterized_datum_validation_queue.py"),
            "refresh-successor",
            str(prior),
            "--successor-queue-dir",
            str(successor),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (successor / "validation-queue.json").read_text(encoding="utf-8")
    )
    assert payload["lineage"]["parentQueueDigest"] == prior_payload["queueDigest"]
    assert payload["lineage"]["parentSourceCatalogDigest"] == "0" * 64
    current = build_parameterized_datum_validation_queue(ROOT)
    expected_ready = current["summary"]["readyForCadValidationCount"]
    assert payload["summary"]["readyForCadValidationCount"] == expected_ready
    candidates = [path for path in successor.iterdir() if path.is_dir()]
    assert len(candidates) == expected_ready
    assert all((path / "validation-package.json").is_file() for path in candidates)


def test_relation_release_identity_is_deterministic_and_pair_bound():
    pair_release = json.loads(
        (
            ROOT
            / "demo/cross_project_substitution/parameterized-datum-placement-v1/"
            "validation-gn00-aa00-v1/pair-release.json"
        ).read_text(encoding="utf-8")
    )
    release_id = derive_parameterized_datum_relation_release_id(pair_release)
    assert release_id.startswith(
        "relation-datum-project01-gn00-project03-aa00-"
    )
    assert release_id.endswith(pair_release["releaseDigest"][:12])
    changed = dict(pair_release)
    changed["releaseDigest"] = "f" * 64
    assert derive_parameterized_datum_relation_release_id(changed) != release_id


def test_pair_release_can_publish_standard_relation_authority_in_isolated_root():
    validation = ROOT / (
        "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "validation-gn00-aa00-v1"
    )
    pair_release = json.loads(
        (validation / "pair-release.json").read_text(encoding="utf-8")
    )
    release_id = derive_parameterized_datum_relation_release_id(pair_release)
    base = ROOT / (
        "demo/cross_project_substitution/expanded-project03-v1/"
        "relation-v62-project03-expanded-cross-project-chain-driving-20261014."
        "catalog-preview.json"
    )
    isolated_root = Path(
        tempfile.mkdtemp(prefix=".tmp-datum-relation-release-", dir=ROOT / "demo")
    )
    try:
        result = publish_parameterized_datum_relation_release(
            ROOT,
            validation,
            release_id,
            base,
            output_root=isolated_root,
        )
        assert result["releaseId"] == release_id
        assert result["relationExecutionMode"] == "datum_placement_demo"
        assert result["physicalFasteningVerified"] is False
        manifest = isolated_root / release_id / "release-manifest.json"
        assert manifest.is_file()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        binding = payload["releaseMetadata"]["parameterizedDatumPairBinding"]
        assert binding["releaseDigest"] == pair_release["releaseDigest"]
    finally:
        shutil.rmtree(isolated_root, ignore_errors=True)

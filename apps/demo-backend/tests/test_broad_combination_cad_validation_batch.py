import copy
import json
from pathlib import Path

import pytest

from demo_backend.broad_combination_cad_validation_batch import (
    build_broad_combination_cad_validation_batch,
    validate_broad_combination_cad_validation_batch,
)
from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)


ROOT = Path(__file__).resolve().parents[3]
COVERAGE = ROOT / "demo/global_assembly_catalog/broad-combination-coverage-v1/coverage.json"
QUEUE = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "validation-queue-20261026-v15"
)
DIRECT = ROOT / (
    "demo/cross_project_substitution/calibration-project01-to-project02-v1/"
    "bd00-a600-validation-v2/validation-package.json"
)


def _batch() -> dict:
    return json.loads(
        (
            ROOT
            / "demo/cross_project_substitution/broad-combination-cad-validation-v1/"
            "batch-20261026-v3/batch-plan.json"
        ).read_text(encoding="utf-8-sig")
    )


def test_batch_contains_exactly_the_seven_cad_ready_pairs():
    batch = _batch()
    assert batch["summary"] == {
        "itemCount": 7,
        "directInterfaceItemCount": 1,
        "parameterizedDatumItemCount": 6,
        "releasedAtCompileTime": 0,
        "pendingCadValidationCount": 7,
    }
    assert batch["items"][-1]["moduleDefinitionId"] == "project01::BD00"
    assert batch["items"][-1]["baseDefinitionId"] == "project02::A600"
    assert batch["items"][-1]["adapter"] == "direct_interface"
    assert [row["adapter"] for row in batch["items"][:6]] == [
        "parameterized_datum_queue"
    ] * 6
    assert {
        (row["moduleDefinitionId"], row["baseDefinitionId"])
        for row in batch["items"]
    } == {
        ("project01::BD00", "project02::A600"),
        ("project01::GN00", "project05::A000"),
        ("project03::AG00", "project01::JJ00"),
        ("project03::AG00", "project05::A000"),
        ("project05::N000", "project01::JJ00"),
        ("project05::N000", "project03::AA00"),
        ("project01::SM00", "project03::AA00"),
    }


def test_batch_excludes_unconfirmed_decisions_and_alternate_strategy_pairs():
    batch = _batch()
    assert all(
        row["sourceCoverageState"]
        in {
            "direct_relation_cad_validation_required",
            "ready_for_nonprototype_cad_validation",
        }
        for row in batch["items"]
    )
    assert all("confirmed" not in row for row in batch["items"])


def test_batch_locks_zero_document_single_concurrency_stop_on_failure_policy():
    batch = _batch()
    assert batch["executionPolicy"] == {
        "cadConcurrency": 1,
        "solidWorksOpenDocumentCountMustEqual": 0,
        "continueAfterFailure": False,
        "checkpointAfterEachItem": True,
        "resumeSkipsAuthenticatedCompletedItems": True,
        "prototypeTopLevelPoseAllowed": False,
        "caseOrLeafPoseAnchorsAllowed": False,
        "collisionOrBrepRequired": False,
    }
    validate_broad_combination_cad_validation_batch(ROOT, batch)


def test_validation_rejects_relaxed_safety_policy():
    batch = _batch()
    modified = copy.deepcopy(batch)
    modified["executionPolicy"]["cadConcurrency"] = 2
    core = {key: value for key, value in modified.items() if key != "batchDigest"}
    import hashlib

    modified["batchDigest"] = hashlib.sha256(
        json.dumps(
            core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(MechanicalInterfaceContractError, match="safety policy"):
        validate_broad_combination_cad_validation_batch(ROOT, modified)


def test_validation_rejects_batch_digest_drift():
    batch = _batch()
    batch["summary"]["itemCount"] = 8
    with pytest.raises(MechanicalInterfaceContractError, match="batch digest mismatch"):
        validate_broad_combination_cad_validation_batch(ROOT, batch)

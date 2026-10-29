import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.candidate_reuse_safety_supersession import (
    load_candidate_reuse_safety_supersessions,
    publish_candidate_reuse_safety_supersession,
    revoked_datum_release_identifiers,
)
from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)
from demo_backend.parameterized_datum_placement import (
    _candidate_reuse_safety_blocks,
)


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    safety = {
        "schemaVersion": "parameterized-datum-release-safety-registry/v1",
        "revokedReleases": [
            {
                "releaseId": "old-pair-release",
                "globalRelationReleaseIds": ["old-relation-release"],
                "moduleDefinitionId": "project05::N000",
                "slotDefinitionId": "project02::A600",
                "blockCandidateReuse": True,
                "reasonCode": "TRANSPORT_OCCUPANCY_REGION_OVERLAP",
                "replacementPolicy": "bounded role station plus two-pose CAD",
            },
            {
                "releaseId": "other-old-pair",
                "globalRelationReleaseIds": ["other-old-relation"],
                "moduleDefinitionId": "project05::P000",
                "slotDefinitionId": "project02::A600",
                "blockCandidateReuse": True,
                "reasonCode": "OTHER_PAIR_BLOCK",
                "replacementPolicy": "independent review required",
            },
        ],
    }
    _write(
        workspace
        / "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "release-safety-registry.json",
        safety,
    )

    candidate = {
        "schemaVersion": "bounded-role-station-candidate/v1",
        "status": "ready_for_explicit_nonprototype_cad_validation",
        "sourceModuleDefinitionId": "project05::N000",
        "targetBaseDefinitionId": "project02::A600",
        "positionParametersMeters": {
            "longitudinal": 0.1,
            "lateral": 0.9,
            "supportGap": 0.0,
        },
        "distanceFlipDimensions": {
            "longitudinal": False,
            "lateral": True,
            "supportGap": False,
        },
        "nativeRoleStationContainment": {"passed": True},
        "finiteSupportGate": {"passed": True},
        "replacesSafetyReasonCode": "TRANSPORT_OCCUPANCY_REGION_OVERLAP",
        "cadLaunchAllowed": True,
        "normalReleasedExecutionAllowed": False,
    }
    candidate["candidateDigest"] = _digest(candidate)
    validation_dir = workspace / "candidate"
    _write(
        validation_dir / "validation-package.json",
        {"boundedRoleStationCandidate": candidate},
    )

    repeat = {"passed": True, "bothRunsSucceeded": True}
    _write(validation_dir / "external-placement-repeatability.json", repeat)
    repeat_sha = hashlib.sha256(
        (validation_dir / "external-placement-repeatability.json").read_bytes()
    ).hexdigest()
    pair = {
        "schemaVersion": "parameterized-datum-pair-release/v1",
        "releaseId": "new-pair-release",
        "moduleDefinitionId": "project05::N000",
        "slotDefinitionId": "project02::A600",
        "nonPrototypeCadValidated": True,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
        "cadResultSha256": "c" * 64,
        "finiteSupportGate": {
            "passed": True,
            "positionParametersMeters": candidate["positionParametersMeters"],
            "distanceFlipDimensions": candidate["distanceFlipDimensions"],
        },
        "externalPlacementRepeatability": {"sha256": repeat_sha},
        "checks": {
            "finiteSupportFootprintInside": True,
            "finiteSupportExternalPlacementRepeatable": True,
        },
    }
    pair["releaseDigest"] = _digest(pair)
    _write(validation_dir / "pair-release.json", pair)
    _write(
        validation_dir / "station-postcheck.json",
        {"targetStationValidated": True, "cadResultSha256": "c" * 64},
    )

    manifest = {
        "releaseId": "new-relation-release",
        "releaseDigest": "d" * 64,
        "releaseMetadata": {"parameterizedDatumPairBinding": pair},
        "scope": {"authorizedDrivingTemplateIds": ["template/exact/new"]},
    }
    manifest_path = workspace / "release/release-manifest.json"
    _write(manifest_path, manifest)
    return workspace, validation_dir, manifest_path


def test_exact_supersession_releases_only_matching_candidate_block(tmp_path):
    workspace, validation_dir, manifest_path = _workspace(tmp_path)

    published = publish_candidate_reuse_safety_supersession(
        workspace, validation_dir, manifest_path
    )
    assert published is not None
    assert published["moduleDefinitionId"] == "project05::N000"
    assert published["slotDefinitionId"] == "project02::A600"

    supersessions = load_candidate_reuse_safety_supersessions(workspace)
    assert set(supersessions) == {("project05::N000", "project02::A600")}
    blocks = _candidate_reuse_safety_blocks(workspace)
    # The old recipe remains blocked.  The separate witness authorizes only
    # the immutable new release through the authority resolver.
    assert blocks[("project05::N000", "project02::A600")][
        "reasonCode"
    ] == "TRANSPORT_OCCUPANCY_REGION_OVERLAP"
    assert blocks[("project05::P000", "project02::A600")][
        "reasonCode"
    ] == "OTHER_PAIR_BLOCK"

    pair_ids, relation_ids = revoked_datum_release_identifiers(workspace)
    assert pair_ids == {"old-pair-release", "other-old-pair"}
    assert relation_ids == {"old-relation-release", "other-old-relation"}


def test_supersession_fails_closed_after_bound_postcheck_changes(tmp_path):
    workspace, validation_dir, manifest_path = _workspace(tmp_path)
    publish_candidate_reuse_safety_supersession(
        workspace, validation_dir, manifest_path
    )
    _write(
        validation_dir / "station-postcheck.json",
        {"targetStationValidated": False, "cadResultSha256": "c" * 64},
    )

    with pytest.raises(
        MechanicalInterfaceContractError, match="station postcheck digest changed"
    ):
        load_candidate_reuse_safety_supersessions(workspace)


def test_invalid_supersession_is_not_written_to_formal_directory(tmp_path):
    workspace, validation_dir, manifest_path = _workspace(tmp_path)
    _write(
        validation_dir / "station-postcheck.json",
        {"targetStationValidated": False, "cadResultSha256": "c" * 64},
    )

    with pytest.raises(
        MechanicalInterfaceContractError, match="required CAD/station evidence"
    ):
        publish_candidate_reuse_safety_supersession(
            workspace, validation_dir, manifest_path
        )

    formal = (
        workspace
        / "demo/cross_project_substitution/datum-safety-supersessions-v1"
    )
    assert not formal.exists() or not list(formal.glob("*.json"))

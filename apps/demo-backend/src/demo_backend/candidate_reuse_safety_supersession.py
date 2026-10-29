"""Authenticate an exact-pair replacement for one datum candidate safety block.

The safety registry is append-only history: a revoked recipe is never deleted.
When a newly reviewed bounded-role candidate has stronger CAD evidence, this
module writes a separate immutable supersession witness.  Consumers may then
ignore only the matching ``blockCandidateReuse`` row; every other revocation
continues to fail closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError


SCHEMA = "candidate-reuse-safety-supersession/v1"
SAFETY_REGISTRY = (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "release-safety-registry.json"
)
SUPERSESSION_ROOT = (
    "demo/cross_project_substitution/datum-safety-supersessions-v1"
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(workspace: Path, value: str, label: str) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    try:
        path.relative_to(workspace.resolve())
    except ValueError as exc:
        raise MechanicalInterfaceContractError(
            f"{label} is outside the workspace"
        ) from exc
    if not path.is_file():
        raise MechanicalInterfaceContractError(f"{label} is missing: {path}")
    return path


def _reference(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _candidate_block_rows(workspace: Path) -> list[dict[str, Any]]:
    path = workspace / SAFETY_REGISTRY
    registry = _read(path)
    if registry.get("schemaVersion") != (
        "parameterized-datum-release-safety-registry/v1"
    ):
        raise MechanicalInterfaceContractError(
            "unsupported datum release safety registry"
        )
    return [
        row
        for row in registry.get("revokedReleases") or []
        if row.get("blockCandidateReuse") is True
    ]


def candidate_reuse_safety_blocks(
    workspace: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Return active exact-pair candidate blocks without applying replacements.

    A supersession authorizes one already validated immutable relation release;
    it deliberately does not re-enable compilation of the revoked recipe.
    """

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _candidate_block_rows(workspace):
        pair = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in result:
            raise MechanicalInterfaceContractError(
                f"invalid or duplicate candidate reuse safety block: {pair}"
            )
        result[pair] = row
    return result


def revoked_datum_release_identifiers(
    workspace: Path,
) -> tuple[set[str], set[str]]:
    """Return revoked pair-release ids and revoked global relation-release ids."""

    path = workspace / SAFETY_REGISTRY
    if not path.is_file():
        return set(), set()
    registry = _read(path)
    if registry.get("schemaVersion") != (
        "parameterized-datum-release-safety-registry/v1"
    ):
        raise MechanicalInterfaceContractError(
            "unsupported datum release safety registry"
        )
    pair_ids = {
        str(row.get("releaseId"))
        for row in registry.get("revokedReleases") or []
        if row.get("releaseId")
    }
    relation_ids = {
        str(release_id)
        for row in registry.get("revokedReleases") or []
        for release_id in row.get("globalRelationReleaseIds") or []
        if release_id
    }
    return pair_ids, relation_ids


def _assert_reference(
    workspace: Path, binding: dict[str, Any], label: str
) -> tuple[Path, dict[str, Any]]:
    path = _resolve(workspace, str(binding.get("path") or ""), label)
    if binding.get("sha256") != _sha(path):
        raise MechanicalInterfaceContractError(f"{label} digest changed")
    return path, _read(path)


def validate_candidate_reuse_safety_supersession(
    workspace: Path,
    witness: dict[str, Any],
    *,
    expected_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Authenticate a replacement witness and return its exact pair identity."""

    if witness.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported candidate reuse safety supersession"
        )
    expected_digest = witness.get("supersessionDigest")
    unsigned = {
        key: value for key, value in witness.items() if key != "supersessionDigest"
    }
    if not isinstance(expected_digest, str) or expected_digest != _digest(unsigned):
        raise MechanicalInterfaceContractError(
            "candidate reuse safety supersession digest mismatch"
        )

    module_id = str(witness.get("moduleDefinitionId") or "")
    slot_id = str(witness.get("slotDefinitionId") or "")
    reason_code = str(witness.get("replacesSafetyReasonCode") or "")
    if not module_id or not slot_id or not reason_code:
        raise MechanicalInterfaceContractError(
            "candidate reuse safety supersession has incomplete identity"
        )
    if expected_block is not None and (
        expected_block.get("moduleDefinitionId") != module_id
        or expected_block.get("slotDefinitionId") != slot_id
        or expected_block.get("reasonCode") != reason_code
        or expected_block.get("blockCandidateReuse") is not True
    ):
        raise MechanicalInterfaceContractError(
            "candidate reuse supersession does not match the active safety block"
        )

    package_path, package = _assert_reference(
        workspace, witness.get("validationPackage") or {}, "validation package"
    )
    pair_path, pair = _assert_reference(
        workspace, witness.get("pairRelease") or {}, "pair release"
    )
    postcheck_path, postcheck = _assert_reference(
        workspace, witness.get("stationPostcheck") or {}, "station postcheck"
    )
    repeat_path, repeatability = _assert_reference(
        workspace, witness.get("repeatability") or {}, "repeatability witness"
    )
    manifest_path, manifest = _assert_reference(
        workspace, witness.get("relationRelease") or {}, "relation release"
    )

    candidate = package.get("boundedRoleStationCandidate") or {}
    pair_identity = (pair.get("moduleDefinitionId"), pair.get("slotDefinitionId"))
    if pair_identity != (module_id, slot_id):
        raise MechanicalInterfaceContractError(
            "candidate reuse supersession pair release identity mismatch"
        )
    if (
        candidate.get("sourceModuleDefinitionId") != module_id
        or candidate.get("targetBaseDefinitionId") != slot_id
        or candidate.get("replacesSafetyReasonCode") != reason_code
        or candidate.get("candidateDigest")
        != (witness.get("validationPackage") or {}).get("candidateDigest")
        or candidate.get("candidateDigest")
        != _digest(
            {
                key: value
                for key, value in candidate.items()
                if key != "candidateDigest"
            }
        )
        or candidate.get("status")
        != "ready_for_explicit_nonprototype_cad_validation"
        or candidate.get("normalReleasedExecutionAllowed") is not False
        or (candidate.get("nativeRoleStationContainment") or {}).get("passed")
        is not True
        or (candidate.get("finiteSupportGate") or {}).get("passed") is not True
    ):
        raise MechanicalInterfaceContractError(
            "bounded role station evidence does not replace the safety block"
        )

    checks = pair.get("checks") or {}
    if (
        pair.get("releaseDigest")
        != _digest(
            {key: value for key, value in pair.items() if key != "releaseDigest"}
        )
        or
        pair.get("nonPrototypeCadValidated") is not True
        or pair.get("prototypeTopLevelTargetPoseUsed") is not False
        or pair.get("caseAnchorUsed") is not False
        or pair.get("targetLeafPoseAnchorsUsed") is not False
        or (pair.get("finiteSupportGate") or {}).get("passed") is not True
        or checks.get("finiteSupportFootprintInside") is not True
        or checks.get("finiteSupportExternalPlacementRepeatable") is not True
        or postcheck.get("targetStationValidated") is not True
        or repeatability.get("passed") is not True
        or repeatability.get("bothRunsSucceeded") is not True
    ):
        raise MechanicalInterfaceContractError(
            "candidate reuse supersession lacks required CAD/station evidence"
        )
    if (
        candidate.get("positionParametersMeters")
        != (pair.get("finiteSupportGate") or {}).get("positionParametersMeters")
        or candidate.get("distanceFlipDimensions")
        != (pair.get("finiteSupportGate") or {}).get("distanceFlipDimensions")
        or postcheck.get("cadResultSha256") != pair.get("cadResultSha256")
        or (pair.get("externalPlacementRepeatability") or {}).get("sha256")
        != _sha(repeat_path)
    ):
        raise MechanicalInterfaceContractError(
            "candidate reuse supersession evidence does not describe one recipe"
        )

    metadata = manifest.get("releaseMetadata") or {}
    if (
        metadata.get("parameterizedDatumPairBinding") != pair
        or manifest.get("releaseId")
        != (witness.get("relationRelease") or {}).get("releaseId")
        or manifest.get("releaseDigest")
        != (witness.get("relationRelease") or {}).get("releaseDigest")
        or not ((manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or [])
    ):
        raise MechanicalInterfaceContractError(
            "candidate reuse supersession relation authority mismatch"
        )

    return {
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "replacesSafetyReasonCode": reason_code,
        "pairReleaseId": str(pair.get("releaseId") or ""),
        "pairReleaseDigest": str(pair.get("releaseDigest") or ""),
        "relationReleaseId": str(manifest.get("releaseId") or ""),
        "supersessionDigest": str(expected_digest),
        "paths": {
            "validationPackage": str(package_path),
            "pairRelease": str(pair_path),
            "stationPostcheck": str(postcheck_path),
            "repeatability": str(repeat_path),
            "relationRelease": str(manifest_path),
        },
    }


def load_candidate_reuse_safety_supersessions(
    workspace: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    root = workspace / SUPERSESSION_ROOT
    if not root.is_dir():
        return {}
    blocks = {
        (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        ): row
        for row in _candidate_block_rows(workspace)
    }
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        witness = _read(path)
        pair = (
            str(witness.get("moduleDefinitionId") or ""),
            str(witness.get("slotDefinitionId") or ""),
        )
        block = blocks.get(pair)
        if block is None:
            raise MechanicalInterfaceContractError(
                "candidate reuse supersession has no active exact-pair block"
            )
        validated = validate_candidate_reuse_safety_supersession(
            workspace, witness, expected_block=block
        )
        if pair in result:
            raise MechanicalInterfaceContractError(
                f"duplicate candidate reuse safety supersession: {pair}"
            )
        result[pair] = validated
    return result


def publish_candidate_reuse_safety_supersession(
    workspace: Path,
    validation_dir: Path,
    relation_manifest_path: Path,
) -> dict[str, Any] | None:
    """Write one immutable witness after all replacement gates have passed."""

    package_path = validation_dir / "validation-package.json"
    package = _read(package_path)
    candidate = package.get("boundedRoleStationCandidate") or {}
    if not candidate:
        return None
    pair_path = validation_dir / "pair-release.json"
    postcheck_path = validation_dir / "station-postcheck.json"
    repeat_path = validation_dir / "external-placement-repeatability.json"
    pair = _read(pair_path)
    module_id = str(pair.get("moduleDefinitionId") or "")
    slot_id = str(pair.get("slotDefinitionId") or "")
    reason_code = str(candidate.get("replacesSafetyReasonCode") or "")
    matches = [
        row
        for row in _candidate_block_rows(workspace)
        if row.get("moduleDefinitionId") == module_id
        and row.get("slotDefinitionId") == slot_id
        and row.get("reasonCode") == reason_code
    ]
    if len(matches) != 1:
        raise MechanicalInterfaceContractError(
            "bounded role station replacement does not identify one safety block"
        )
    manifest = _read(relation_manifest_path)
    core = {
        "schemaVersion": SCHEMA,
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "replacesSafetyReasonCode": reason_code,
        "validationPackage": {
            "path": _reference(workspace, package_path),
            "sha256": _sha(package_path),
            "candidateDigest": candidate.get("candidateDigest"),
        },
        "pairRelease": {
            "path": _reference(workspace, pair_path),
            "sha256": _sha(pair_path),
            "releaseId": pair.get("releaseId"),
            "releaseDigest": pair.get("releaseDigest"),
        },
        "stationPostcheck": {
            "path": _reference(workspace, postcheck_path),
            "sha256": _sha(postcheck_path),
        },
        "repeatability": {
            "path": _reference(workspace, repeat_path),
            "sha256": _sha(repeat_path),
        },
        "relationRelease": {
            "path": _reference(workspace, relation_manifest_path),
            "sha256": _sha(relation_manifest_path),
            "releaseId": manifest.get("releaseId"),
            "releaseDigest": manifest.get("releaseDigest"),
        },
        "claimBoundary": (
            "This immutable witness supersedes only the exact-pair candidate-reuse "
            "block named above. Historical revocations remain recorded. Collision/B-rep, "
            "physical fastening, functional process performance and production approval "
            "remain outside the release."
        ),
    }
    core["supersessionDigest"] = _digest(core)
    # Keep the immutable filename short enough for Windows test workspaces;
    # the exact pair identity remains inside the authenticated document.
    output = workspace / SUPERSESSION_ROOT / (
        f"supersession-{core['supersessionDigest'][:20]}.json"
    )
    # Authenticate the complete in-memory witness before it becomes discoverable
    # in the formal directory.  A failed validation must not leave a poisoned
    # file that blocks every later authority-resolution scan.
    validated = validate_candidate_reuse_safety_supersession(
        workspace, core, expected_block=matches[0]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if _read(output) != core:
            raise MechanicalInterfaceContractError(
                "candidate reuse safety supersession path contains different evidence"
            )
    else:
        output.write_text(
            json.dumps(core, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {"path": _reference(workspace, output), **validated}

"""Compile the exact CAD-ready broad-combination pairs into one safe batch.

The broad coverage matrix intentionally mixes two candidate families:

* an unpublished direct mechanical-interface pair; and
* materialized parameterized-datum validation packages.

This module only authenticates and schedules those existing artifacts.  It does
not connect to SolidWorks and it never upgrades a candidate to a released
combination.  A separate runner must enforce the zero-document preflight,
execute one item at a time, stop on the first failure, and publish the exact
pair before marking an item complete.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_validation_execution import (
    load_materialized_validation_queue,
)


BATCH_SCHEMA = "broad-combination-cad-validation-batch/v1"
COVERAGE_SCHEMA = "broad-cross-project-combination-coverage/v1"
DIRECT_PACKAGE_SCHEMA = "direct-interface-cad-validation-package/v1"
PARAMETERIZED_PACKAGE_SCHEMA = "parameterized-datum-validation-package/v1"

DIRECT_STATE = "direct_relation_cad_validation_required"
PARAMETERIZED_STATE = "ready_for_nonprototype_cad_validation"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_embedded_digest(
    payload: dict[str, Any], *, field: str, description: str
) -> None:
    expected = _digest({key: value for key, value in payload.items() if key != field})
    if payload.get(field) != expected:
        raise MechanicalInterfaceContractError(f"{description} digest mismatch")


def _relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _pair_id(module_definition_id: str, base_definition_id: str) -> str:
    return (
        module_definition_id.replace("::", "-").lower()
        + "--"
        + base_definition_id.replace("::", "-").lower()
    )


def _load_coverage(path: Path) -> dict[str, Any]:
    coverage = _read(path)
    if coverage.get("schemaVersion") != COVERAGE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported broad coverage schema")
    _validate_embedded_digest(
        coverage, field="coverageDigest", description="broad coverage"
    )
    summary = coverage.get("summary") or {}
    expected_ready = int(summary.get("cadValidationReadyCount") or 0)
    actual_ready = sum(
        row.get("state") in {DIRECT_STATE, PARAMETERIZED_STATE}
        for row in coverage.get("pairs") or []
    )
    if expected_ready != actual_ready:
        raise MechanicalInterfaceContractError(
            "broad coverage ready count differs from its pair rows"
        )
    return coverage


def _load_direct_package(path: Path) -> dict[str, Any]:
    package = _read(path)
    if package.get("schemaVersion") != DIRECT_PACKAGE_SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported direct-interface validation package schema"
        )
    if package.get("artifacts"):
        artifacts = package["artifacts"]
        graph_binding = artifacts.get("effectiveGraph") or {}
        endpoint_binding = artifacts.get("selectedEndpointCatalog") or {}
        graph_path = Path(str(graph_binding.get("path") or ""))
        endpoint_path = Path(str(endpoint_binding.get("path") or ""))
        if (
            not graph_path.is_file()
            or _sha256(graph_path) != graph_binding.get("sha256")
            or not endpoint_path.is_file()
            or _sha256(endpoint_path) != endpoint_binding.get("sha256")
        ):
            raise MechanicalInterfaceContractError(
                "direct-interface materialized artifacts changed"
            )
        hydrated = {
            key: value
            for key, value in package.items()
            if key not in {"packageDigest", "artifacts"}
        }
        hydrated["effectiveMateGraph"] = _read(graph_path)
        hydrated["selectedEndpointCatalog"] = _read(endpoint_path)
        if package.get("packageDigest") != _digest(hydrated):
            raise MechanicalInterfaceContractError(
                "direct-interface package digest mismatch"
            )
        package = {
            **package,
            "effectiveMateGraph": hydrated["effectiveMateGraph"],
            "selectedEndpointCatalog": hydrated["selectedEndpointCatalog"],
        }
    else:
        _validate_embedded_digest(
            package, field="packageDigest", description="direct-interface package"
        )
    if package.get("status") != "ready_for_nonprototype_cad_validation":
        raise MechanicalInterfaceContractError(
            "direct-interface package is not ready for CAD validation"
        )
    graph = package.get("effectiveMateGraph") or {}
    if package.get("effectiveMateGraphDigest") != _digest(graph):
        raise MechanicalInterfaceContractError(
            "direct-interface effective graph digest mismatch"
        )
    return package


def _parameterized_items(
    workspace: Path,
    queue_dir: Path,
    queue: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for queue_index, row in enumerate(queue.get("pairs") or []):
        if row.get("state") != PARAMETERIZED_STATE:
            continue
        candidate = queue_dir / str(row.get("proposedValidationDirectory") or "")
        package_path = candidate / "validation-package.json"
        if not package_path.is_file():
            raise FileNotFoundError(package_path)
        package = _read(package_path)
        if package.get("schemaVersion") != PARAMETERIZED_PACKAGE_SCHEMA:
            raise MechanicalInterfaceContractError(
                "unsupported parameterized validation package schema"
            )
        # Queue materialization deliberately moves the large graph and endpoint
        # catalog out of the original package while preserving the digest of the
        # pre-materialized payload.  Rehydrate that payload before authenticating
        # it; hashing the small manifest alone would incorrectly reject every
        # valid materialized package.
        artifacts = package.get("artifacts") or {}
        graph_binding = artifacts.get("effectiveGraph") or {}
        graph_path = Path(str(graph_binding.get("path") or ""))
        if (
            not graph_path.is_file()
            or _sha256(graph_path) != graph_binding.get("sha256")
        ):
            raise MechanicalInterfaceContractError(
                "parameterized effective graph artifact changed"
            )
        original = {
            key: value
            for key, value in package.items()
            if key not in {"packageDigest", "artifacts"}
        }
        original["effectiveGraph"] = _read(graph_path)
        endpoint_binding = artifacts.get("selectedEndpointCatalog") or {}
        if endpoint_binding:
            endpoint_path = Path(str(endpoint_binding.get("path") or ""))
            if (
                not endpoint_path.is_file()
                or _sha256(endpoint_path) != endpoint_binding.get("sha256")
            ):
                raise MechanicalInterfaceContractError(
                    "parameterized endpoint artifact changed"
                )
            original["selectedEndpointCatalog"] = _read(endpoint_path)
        if package.get("packageDigest") != _digest(original):
            raise MechanicalInterfaceContractError(
                "parameterized package digest mismatch"
            )
        if row.get("validationPackageDigest") != package.get("packageDigest"):
            raise MechanicalInterfaceContractError(
                "parameterized queue row package digest mismatch"
            )
        for key in ("moduleDefinitionId", "slotDefinitionId"):
            if row.get(key) != package.get(key):
                raise MechanicalInterfaceContractError(
                    f"parameterized queue/package identity mismatch: {key}"
                )
        module = str(row["moduleDefinitionId"])
        base = str(row["slotDefinitionId"])
        items.append(
            {
                "itemId": _pair_id(module, base),
                "sequence": len(items) + 2,
                "adapter": "parameterized_datum_queue",
                "moduleRole": row.get("moduleRole"),
                "moduleDefinitionId": module,
                "baseDefinitionId": base,
                "sourceCoverageState": PARAMETERIZED_STATE,
                "sourceQueueIndex": queue_index,
                "sourceQueueDigest": queue["queueDigest"],
                "candidateDirectory": _relative(workspace, candidate),
                "validationPackagePath": _relative(workspace, package_path),
                "validationPackageDigest": package["packageDigest"],
                "requiredCompletionEvidence": [
                    "cad-result.json success",
                    "moving module fully constrained",
                    "save-close-reopen verification",
                    "pair-release.json",
                    "relation-release-binding.json",
                ],
            }
        )
    return items


def build_broad_combination_cad_validation_batch(
    workspace: Path,
    *,
    coverage_path: Path,
    parameterized_queue_dir: Path,
    direct_package_path: Path,
) -> dict[str, Any]:
    """Build one immutable plan for every currently CAD-ready exact pair."""

    workspace = workspace.resolve()
    coverage_path = coverage_path.resolve()
    queue_dir = parameterized_queue_dir.resolve()
    direct_package_path = direct_package_path.resolve()
    coverage = _load_coverage(coverage_path)
    queue = load_materialized_validation_queue(queue_dir)
    direct = _load_direct_package(direct_package_path)

    ready_rows = {
        (str(row.get("moduleDefinitionId")), str(row.get("baseDefinitionId"))): row
        for row in coverage.get("pairs") or []
        if row.get("state") in {DIRECT_STATE, PARAMETERIZED_STATE}
    }
    direct_pair = (
        str(direct.get("moduleDefinitionId")),
        str(direct.get("slotDefinitionId")),
    )
    direct_row = ready_rows.get(direct_pair)
    if not direct_row or direct_row.get("state") != DIRECT_STATE:
        raise MechanicalInterfaceContractError(
            "direct package does not match the coverage direct candidate"
        )

    direct_item = {
        "itemId": _pair_id(*direct_pair),
        "sequence": 0,
        "adapter": "direct_interface",
        "moduleRole": direct_row.get("role"),
        "moduleDefinitionId": direct_pair[0],
        "baseDefinitionId": direct_pair[1],
        "sourceCoverageState": DIRECT_STATE,
        "validationPackagePath": _relative(workspace, direct_package_path),
        "validationPackageDigest": direct["packageDigest"],
        "effectiveMateGraphDigest": direct["effectiveMateGraphDigest"],
        "requiredCompletionEvidence": [
            "cad-result.json success",
            "moving module fully constrained",
            "save-close-reopen verification",
            "immutable direct relation release",
        ],
    }
    parameterized = _parameterized_items(workspace, queue_dir, queue)
    # Parameterized items already have a complete CAD -> pair release -> global
    # relation release -> successor queue adapter.  Run them first so the one
    # direct candidate cannot hold six independently executable pairs hostage
    # while its direct publication bridge is being completed.
    for sequence, row in enumerate(parameterized, start=1):
        row["sequence"] = sequence
    direct_item["sequence"] = len(parameterized) + 1
    items = [*parameterized, direct_item]

    planned_pairs = {
        (row["moduleDefinitionId"], row["baseDefinitionId"]) for row in items
    }
    if planned_pairs != set(ready_rows):
        missing = sorted(set(ready_rows) - planned_pairs)
        extra = sorted(planned_pairs - set(ready_rows))
        raise MechanicalInterfaceContractError(
            f"batch/coverage ready-pair mismatch; missing={missing}, extra={extra}"
        )
    if len(planned_pairs) != len(items):
        raise MechanicalInterfaceContractError("batch contains duplicate exact pairs")

    core = {
        "schemaVersion": BATCH_SCHEMA,
        "status": "compiled_pending_clean_solidworks_session",
        "sourceBindings": {
            "coveragePath": _relative(workspace, coverage_path),
            "coverageDigest": coverage["coverageDigest"],
            "parameterizedQueueDirectory": _relative(workspace, queue_dir),
            "parameterizedQueueDigest": queue["queueDigest"],
            "directPackagePath": _relative(workspace, direct_package_path),
            "directPackageSha256": _sha256(direct_package_path),
        },
        "summary": {
            "itemCount": len(items),
            "directInterfaceItemCount": 1,
            "parameterizedDatumItemCount": len(parameterized),
            "releasedAtCompileTime": 0,
            "pendingCadValidationCount": len(items),
        },
        "executionPolicy": {
            "cadConcurrency": 1,
            "solidWorksOpenDocumentCountMustEqual": 0,
            "continueAfterFailure": False,
            "checkpointAfterEachItem": True,
            "resumeSkipsAuthenticatedCompletedItems": True,
            "prototypeTopLevelPoseAllowed": False,
            "caseOrLeafPoseAnchorsAllowed": False,
            "collisionOrBrepRequired": False,
        },
        "items": items,
        "claimBoundary": (
            "This batch only schedules the exact pairs already classified as CAD-ready. "
            "An item remains unavailable to normal cumulative assembly until its real "
            "non-prototype CAD validation and immutable exact-pair release both succeed. "
            "Collision, B-rep, physical fastening and production approval remain separate."
        ),
    }
    return {**core, "batchDigest": _digest(core)}


def validate_broad_combination_cad_validation_batch(
    workspace: Path, batch: dict[str, Any]
) -> None:
    """Re-authenticate an already materialized plan without starting CAD."""

    workspace = workspace.resolve()
    if batch.get("schemaVersion") != BATCH_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported broad CAD batch schema")
    _validate_embedded_digest(batch, field="batchDigest", description="broad CAD batch")
    bindings = batch.get("sourceBindings") or {}
    coverage_path = workspace / str(bindings.get("coveragePath") or "")
    # Coverage is a live derived report and legitimately advances after each
    # exact-pair publication.  The immutable batch digest already binds every
    # scheduled item's pair identity and source state, so require the source
    # report to remain readable but retain its compile-time digest only as
    # lineage instead of treating normal publication progress as tampering.
    _load_coverage(coverage_path)
    queue_dir = workspace / str(bindings.get("parameterizedQueueDirectory") or "")
    queue = load_materialized_validation_queue(queue_dir)
    if queue.get("queueDigest") != bindings.get("parameterizedQueueDigest"):
        raise MechanicalInterfaceContractError("broad CAD batch queue binding changed")
    direct_path = workspace / str(bindings.get("directPackagePath") or "")
    if (
        not direct_path.is_file()
        or _sha256(direct_path) != bindings.get("directPackageSha256")
    ):
        raise MechanicalInterfaceContractError("broad CAD batch direct package changed")

    item_ids = [str(row.get("itemId") or "") for row in batch.get("items") or []]
    if not item_ids or len(item_ids) != len(set(item_ids)):
        raise MechanicalInterfaceContractError("broad CAD batch item ids are invalid")
    if int((batch.get("summary") or {}).get("itemCount") or 0) != len(item_ids):
        raise MechanicalInterfaceContractError("broad CAD batch item count mismatch")
    policy = batch.get("executionPolicy") or {}
    if (
        policy.get("cadConcurrency") != 1
        or policy.get("solidWorksOpenDocumentCountMustEqual") != 0
        or policy.get("continueAfterFailure") is not False
    ):
        raise MechanicalInterfaceContractError("broad CAD batch safety policy was relaxed")

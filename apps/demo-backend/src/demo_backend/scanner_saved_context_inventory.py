"""Inventory exact scanner/transport/base triples in saved CAD states.

This module is deliberately read-only.  It turns the repository's existing
save/reopen evidence into a small index that answers one question for each
scanner review candidate: does a successful saved cumulative context already
contain exactly one instance of the requested scanner, transport and base?

The inventory is not CAD authority and it never treats a prototype pose as an
execution fallback.  A missing triple means a new cumulative context must be
built before current-pose optical geometry can be evaluated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


SCHEMA = "scanner-saved-context-inventory/v1"
STATE_FILENAMES = frozenset(
    {
        "read-only-chain-verification.json",
        "reopened-state.json",
    }
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_digest(payload: dict) -> str:
    body = dict(payload)
    body.pop("inventoryDigest", None)
    return hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _normalise_path(value: str) -> str:
    return str(Path(value)).replace("/", "\\").casefold()


def discover_saved_state_paths(search_root: Path) -> list[Path]:
    """Return deterministic saved-state candidates below *search_root*."""

    return sorted(
        (
            path.resolve()
            for path in search_root.rglob("*.json")
            if path.name in STATE_FILENAMES
        ),
        key=lambda path: str(path).casefold(),
    )


def _definition_source_paths(catalog: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for module in catalog.get("moduleDefinitions") or []:
        paths = {
            _normalise_path(str(item["path"]))
            for item in module.get("cadSources") or []
            if item.get("path")
        }
        for alias in module.get("projectAliases") or []:
            project_id = alias.get("projectId")
            token = alias.get("moduleToken")
            if project_id and token:
                result.setdefault(f"{project_id}::{token}", set()).update(paths)
    return result


def _state_components(payload: dict) -> list[dict]:
    observed = payload.get("observed") or {}
    components = observed.get("components") or []
    return [row for row in components if isinstance(row, dict)]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def build_scanner_saved_context_inventory(
    *,
    workspace_root: Path,
    review_queue_path: Path,
    module_catalog_path: Path,
    state_paths: Iterable[Path],
) -> dict:
    """Build an immutable-evidence index for scanner review candidates."""

    workspace_root = workspace_root.resolve()
    review_queue_path = review_queue_path.resolve()
    module_catalog_path = module_catalog_path.resolve()
    queue = _read(review_queue_path)
    catalog = _read(module_catalog_path)
    if queue.get("schemaVersion") != "scanner-transport-binding-review-queue/v1":
        raise ValueError("unsupported scanner review queue")

    definition_paths = _definition_source_paths(catalog)
    candidates = queue.get("candidates") or []
    required_definitions = {
        str(value)
        for candidate in candidates
        for value in (
            candidate.get("sourceModuleDefinitionId"),
            candidate.get("transportModuleDefinitionId"),
            candidate.get("targetBaseDefinitionId"),
        )
        if value
    }
    missing_definitions = sorted(
        definition_id
        for definition_id in required_definitions
        if not definition_paths.get(definition_id)
    )
    if missing_definitions:
        raise ValueError(
            "module catalog does not resolve scanner candidate definitions: "
            + ", ".join(missing_definitions)
        )

    inspected_states: list[dict] = []
    for raw_path in sorted(
        {Path(path).resolve() for path in state_paths},
        key=lambda path: str(path).casefold(),
    ):
        if not raw_path.is_file():
            continue
        try:
            payload = _read(raw_path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        components = _state_components(payload)
        if payload.get("success") is not True or not components:
            continue
        component_rows = []
        for component in components:
            source_path = component.get("sourcePath")
            if not source_path:
                continue
            component_rows.append(
                {
                    "instanceId": component.get("name"),
                    "sourcePath": str(source_path),
                    "normalisedSourcePath": _normalise_path(str(source_path)),
                    "configuration": component.get("configuration"),
                    "isFixed": component.get("isFixed"),
                    "constrainedStatus": component.get("constrainedStatus"),
                    "transform": component.get("transform"),
                }
            )
        if not component_rows:
            continue
        inspected_states.append(
            {
                "path": _relative(raw_path, workspace_root),
                "sha256": _sha256(raw_path),
                "assemblyPath": payload.get("assemblyPath"),
                "assemblySha256": payload.get("assemblySha256"),
                "schemaVersion": payload.get("schemaVersion"),
                "components": component_rows,
            }
        )

    rows = []
    for candidate in candidates:
        scanner_id = str(candidate["sourceModuleDefinitionId"])
        transport_id = str(candidate["transportModuleDefinitionId"])
        base_id = str(candidate["targetBaseDefinitionId"])
        matches = []
        for state in inspected_states:
            selected: dict[str, list[dict]] = {}
            for role, definition_id in (
                ("scanner", scanner_id),
                ("transport", transport_id),
                ("base", base_id),
            ):
                expected = definition_paths[definition_id]
                selected[role] = [
                    component
                    for component in state["components"]
                    if component["normalisedSourcePath"] in expected
                ]
            if not all(len(selected[role]) == 1 for role in selected):
                continue
            if selected["base"][0].get("isFixed") is not True:
                continue
            matches.append(
                {
                    "statePath": state["path"],
                    "stateSha256": state["sha256"],
                    "assemblyPath": state["assemblyPath"],
                    "assemblySha256": state["assemblySha256"],
                    "scannerInstance": selected["scanner"][0],
                    "transportInstance": selected["transport"][0],
                    "targetBaseInstance": selected["base"][0],
                }
            )
        status = (
            "exact_saved_context_available"
            if matches
            else "new_cumulative_chain_context_required"
        )
        rows.append(
            {
                "sourceModuleDefinitionId": scanner_id,
                "transportModuleDefinitionId": transport_id,
                "targetBaseDefinitionId": base_id,
                "priorCandidateStatus": candidate.get("status"),
                "status": status,
                "exactSavedContextCount": len(matches),
                "savedContexts": matches,
            }
        )

    payload = {
        "schemaVersion": SCHEMA,
        "reviewQueue": {
            "path": _relative(review_queue_path, workspace_root),
            "sha256": _sha256(review_queue_path),
            "queueDigest": queue.get("queueDigest"),
        },
        "moduleCatalog": {
            "path": _relative(module_catalog_path, workspace_root),
            "sha256": _sha256(module_catalog_path),
        },
        "searchPolicy": {
            "acceptedFilenames": sorted(STATE_FILENAMES),
            "requireSuccess": True,
            "requireUniqueScannerTransportBaseInstances": True,
            "requireFixedTargetBase": True,
            "prototypePoseAsExecutionAuthorityAllowed": False,
        },
        "summary": {
            "candidateCount": len(rows),
            "inspectedSuccessfulSavedStateCount": len(inspected_states),
            "exactSavedContextAvailableCount": sum(
                row["status"] == "exact_saved_context_available" for row in rows
            ),
            "newCumulativeChainContextRequiredCount": sum(
                row["status"] == "new_cumulative_chain_context_required"
                for row in rows
            ),
        },
        "candidates": rows,
        "claimBoundary": (
            "Read-only repository inventory only. An exact saved triple permits "
            "current-pose scanner geometry evaluation; it is not CAD authority, "
            "new mechanical validation, process success, collision clearance, "
            "fastening or production approval. A missing triple requires a new "
            "cumulative context and must not be filled with a prototype pose."
        ),
    }
    payload["inventoryDigest"] = _stable_digest(payload)
    return payload

"""Plan and cache exact interference closure for context-incremental assembly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class SemanticAssemblyClosureError(ValueError):
    pass


PROJECT02_PAIR_POLICIES = (
    {
        "tokens": ("A500", "A700"),
        "policy": "noNewInterferenceOverAcceptedBaseline",
        "baseline": "demo/interference_project02_prototype_baseline/FL9A24D062A000.001_leaf_details_A500_A700.json",
    },
    {"tokens": ("A500", "A600"), "policy": "zeroInterference"},
    {
        "tokens": ("A600", "A700"),
        "policy": "noNewInterferenceOverAcceptedBaseline",
        "baseline": "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A600_A700.json",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _value(payload: dict[str, Any], pascal: str, camel: str, default: Any = None) -> Any:
    return payload.get(pascal, payload.get(camel, default))


def _raw_reconstruction(reconstruction: dict[str, Any]) -> dict[str, Any]:
    raw = reconstruction.get("toolResult")
    return raw if isinstance(raw, dict) else reconstruction


def resolve_context_incremental_instances(
    reconstruction: dict[str, Any], effective_graph: dict[str, Any]
) -> dict[str, str]:
    """Resolve graph module tokens to actual reopened top-level instance names."""

    raw = _raw_reconstruction(reconstruction)
    if _value(raw, "Success", "success") is not True:
        raise SemanticAssemblyClosureError("CAD reconstruction has not passed.")
    mode = str(_value(raw, "ExecutionMode", "executionMode", ""))
    if mode != "context_incremental_insert":
        raise SemanticAssemblyClosureError(
            f"Expected context_incremental_insert reconstruction, got '{mode}'."
        )
    target_token = str(_value(raw, "TargetModuleToken", "targetModuleToken", ""))
    inserted_name = str(
        _value(raw, "InsertedComponentName", "insertedComponentName", "")
    )
    if not target_token or not inserted_name:
        raise SemanticAssemblyClosureError(
            "Reconstruction result has no target token or inserted component name."
        )

    modules = _value(effective_graph, "Modules", "modules", []) or []
    result: dict[str, str] = {}
    for module in modules:
        token = str(_value(module, "ModuleToken", "moduleToken", ""))
        hierarchy = str(
            _value(module, "HierarchyPath", "hierarchyPath", "")
            or _value(module, "Name", "name", "")
        )
        if token:
            result[token] = inserted_name if token == target_token else hierarchy
    if target_token not in result:
        raise SemanticAssemblyClosureError(
            f"Target module '{target_token}' is absent from effective graph."
        )
    if len(set(result.values())) != len(result):
        raise SemanticAssemblyClosureError("Resolved instance names are not unique.")
    return result


def build_context_incremental_brep_plan(
    workspace: Path,
    reconstruction: dict[str, Any],
    effective_graph: dict[str, Any],
    pair_policies: tuple[dict[str, Any], ...] = PROJECT02_PAIR_POLICIES,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    instances = resolve_context_incremental_instances(reconstruction, effective_graph)
    raw = _raw_reconstruction(reconstruction)
    assembly = Path(
        str(_value(raw, "OutputAssemblyPath", "outputAssemblyPath", ""))
    ).resolve()
    if not assembly.is_file():
        raise SemanticAssemblyClosureError(f"Output assembly was not found: {assembly}")

    pairs: list[dict[str, Any]] = []
    for item in pair_policies:
        first_token, second_token = item["tokens"]
        if first_token not in instances or second_token not in instances:
            raise SemanticAssemblyClosureError(
                f"Pair policy references unknown module: {first_token}/{second_token}."
            )
        baseline = item.get("baseline")
        baseline_path = (workspace / baseline).resolve() if baseline else None
        if baseline_path is not None and not baseline_path.is_file():
            raise SemanticAssemblyClosureError(
                f"Accepted baseline was not found: {baseline_path}"
            )
        pairs.append(
            {
                "tokens": [first_token, second_token],
                "hierarchyPaths": [instances[first_token], instances[second_token]],
                "policy": item["policy"],
                "baselinePath": str(baseline_path) if baseline_path else None,
            }
        )

    modules = _value(effective_graph, "Modules", "modules", []) or []
    module_sources: dict[str, dict[str, str]] = {}
    for module in modules:
        token = str(_value(module, "ModuleToken", "moduleToken", ""))
        source = Path(str(_value(module, "Path", "path", ""))).resolve()
        if not source.is_file():
            raise SemanticAssemblyClosureError(f"Module source was not found: {source}")
        module_sources[token] = {"path": str(source), "sha256": sha256_file(source)}

    fingerprint_payload = {
        "assemblySha256": sha256_file(assembly),
        "effectiveGraphSha256": hashlib.sha256(
            json.dumps(
                effective_graph,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "moduleSources": module_sources,
        "pairs": pairs,
    }
    evidence_key = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": "semantic-context-incremental-brep-plan/v1",
        "assemblyPath": str(assembly),
        "instancesByModuleToken": instances,
        "pairs": pairs,
        "fingerprint": fingerprint_payload,
        "evidenceKey": evidence_key,
    }


def validate_cached_brep_evidence(
    plan: dict[str, Any], manifest: dict[str, Any], batch: dict[str, Any]
) -> dict[str, Any]:
    reasons: list[str] = []
    if manifest.get("schemaVersion") != "semantic-context-incremental-brep-cache/v1":
        reasons.append("cache schema mismatch")
    if manifest.get("evidenceKey") != plan.get("evidenceKey"):
        reasons.append("assembly, graph, module source or pair fingerprint changed")
    if Path(str(batch.get("assemblyPath") or "")).resolve() != Path(
        str(plan.get("assemblyPath") or "")
    ).resolve():
        reasons.append("batch assembly path mismatch")
    expected_pairs = {tuple(item["hierarchyPaths"]) for item in plan.get("pairs") or []}
    observed_pairs = {tuple(item.get("pair") or []) for item in batch.get("pairs") or []}
    if expected_pairs != observed_pairs:
        reasons.append("exact pair set mismatch")
    if int(batch.get("completedPairCount") or 0) != len(expected_pairs):
        reasons.append("exact checks are incomplete")
    if int(batch.get("hardFailureCount") or 0) != 0:
        reasons.append("cached batch contains a hard failure")
    for item in batch.get("pairs") or []:
        if item.get("exactCheckComplete") is not True:
            reasons.append(f"pair {item.get('pair')} is incomplete")
        if (item.get("acceptance") or {}).get("accepted") is not True:
            reasons.append(f"pair {item.get('pair')} was not accepted")
    return {
        "cacheReusable": not reasons,
        "evidenceKey": plan.get("evidenceKey"),
        "reasons": reasons,
    }

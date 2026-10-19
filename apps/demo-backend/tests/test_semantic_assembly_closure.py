from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_backend.semantic_assembly_closure import (
    SemanticAssemblyClosureError,
    build_context_incremental_brep_plan,
    resolve_context_incremental_instances,
    validate_cached_brep_evidence,
)


def reconstruction(output: Path, *, inserted="A500-file-2", success=True):
    return {
        "success": success,
        "toolResult": {
            "Success": success,
            "ExecutionMode": "context_incremental_insert",
            "OutputAssemblyPath": str(output),
            "TargetModuleToken": "A500",
            "InsertedComponentName": inserted,
        },
    }


def graph(root: Path):
    modules = []
    for token in ("A500", "A600", "A700"):
        path = root / f"{token}.SLDASM"
        path.write_text(token, encoding="utf-8")
        modules.append(
            {
                "ModuleToken": token,
                "HierarchyPath": f"{token}-1",
                "Path": str(path),
            }
        )
    return {"Modules": modules}


def policies(root: Path):
    baseline = root / "baseline.json"
    baseline.write_text("{}", encoding="utf-8")
    return (
        {
            "tokens": ("A500", "A700"),
            "policy": "noNewInterferenceOverAcceptedBaseline",
            "baseline": "baseline.json",
        },
        {"tokens": ("A500", "A600"), "policy": "zeroInterference"},
    )


def test_instance_resolution_uses_actual_inserted_suffix(tmp_path: Path):
    output = tmp_path / "result.SLDASM"
    output.write_bytes(b"assembly")
    result = resolve_context_incremental_instances(reconstruction(output), graph(tmp_path))
    assert result == {"A500": "A500-file-2", "A600": "A600-1", "A700": "A700-1"}


def test_failed_reconstruction_is_rejected_before_brep(tmp_path: Path):
    output = tmp_path / "result.SLDASM"
    output.write_bytes(b"assembly")
    with pytest.raises(SemanticAssemblyClosureError, match="has not passed"):
        resolve_context_incremental_instances(
            reconstruction(output, success=False), graph(tmp_path)
        )


def test_plan_fingerprint_and_cache_reuse_are_deterministic(tmp_path: Path):
    output = tmp_path / "result.SLDASM"
    output.write_bytes(b"assembly")
    effective = graph(tmp_path)
    plan = build_context_incremental_brep_plan(
        tmp_path, reconstruction(output), effective, policies(tmp_path)
    )
    repeated = build_context_incremental_brep_plan(
        tmp_path, reconstruction(output), effective, policies(tmp_path)
    )
    assert plan["evidenceKey"] == repeated["evidenceKey"]
    batch = {
        "assemblyPath": str(output),
        "completedPairCount": 2,
        "hardFailureCount": 0,
        "pairs": [
            {
                "pair": item["hierarchyPaths"],
                "exactCheckComplete": True,
                "acceptance": {"accepted": True},
            }
            for item in plan["pairs"]
        ],
    }
    manifest = {
        "schemaVersion": "semantic-context-incremental-brep-cache/v1",
        "evidenceKey": plan["evidenceKey"],
    }
    assert validate_cached_brep_evidence(plan, manifest, batch)["cacheReusable"]


def test_changed_assembly_invalidates_cached_evidence(tmp_path: Path):
    output = tmp_path / "result.SLDASM"
    output.write_bytes(b"assembly-v1")
    effective = graph(tmp_path)
    pair_policy = policies(tmp_path)
    old = build_context_incremental_brep_plan(
        tmp_path, reconstruction(output), effective, pair_policy
    )
    output.write_bytes(b"assembly-v2")
    current = build_context_incremental_brep_plan(
        tmp_path, reconstruction(output), effective, pair_policy
    )
    batch = {
        "assemblyPath": str(output),
        "completedPairCount": len(current["pairs"]),
        "hardFailureCount": 0,
        "pairs": [
            {
                "pair": item["hierarchyPaths"],
                "exactCheckComplete": True,
                "acceptance": {"accepted": True},
            }
            for item in current["pairs"]
        ],
    }
    check = validate_cached_brep_evidence(
        current,
        {
            "schemaVersion": "semantic-context-incremental-brep-cache/v1",
            "evidenceKey": old["evidenceKey"],
        },
        batch,
    )
    assert check["cacheReusable"] is False
    assert "fingerprint changed" in check["reasons"][0]


def test_rejected_pair_cannot_be_reused(tmp_path: Path):
    output = tmp_path / "result.SLDASM"
    output.write_bytes(b"assembly")
    plan = build_context_incremental_brep_plan(
        tmp_path, reconstruction(output), graph(tmp_path), policies(tmp_path)
    )
    batch = {
        "assemblyPath": str(output),
        "completedPairCount": len(plan["pairs"]),
        "hardFailureCount": 1,
        "pairs": [
            {
                "pair": item["hierarchyPaths"],
                "exactCheckComplete": True,
                "acceptance": {"accepted": index != 0},
            }
            for index, item in enumerate(plan["pairs"])
        ],
    }
    check = validate_cached_brep_evidence(
        plan,
        {
            "schemaVersion": "semantic-context-incremental-brep-cache/v1",
            "evidenceKey": plan["evidenceKey"],
        },
        batch,
    )
    assert check["cacheReusable"] is False
    assert any("hard failure" in reason for reason in check["reasons"])

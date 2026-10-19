#!/usr/bin/env python3
"""Run/reuse Project 02 context-incremental B-Rep checks and build release gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.pipeline_timing import PipelineTiming
from demo_backend.semantic_assembly_closure import (
    build_context_incremental_brep_plan,
    validate_cached_brep_evidence,
)
from demo_backend.semantic_assembly_safety import build_semantic_assembly_release_gate

DEFAULT_EXE = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconstruction", required=True, type=Path)
    parser.add_argument("--effective", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--existing-batch", type=Path)
    parser.add_argument(
        "--adopt-existing-batch",
        action="store_true",
        help="Bind an already completed/accepted batch to the current exact fingerprint once.",
    )
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()

    timing = PipelineTiming("project02.context-incremental-release-closure")
    reconstruction_path = args.reconstruction.resolve()
    effective_path = args.effective.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "context_incremental_brep_plan.json"
    cache_path = output_dir / "context_incremental_brep_cache.json"
    gate_path = output_dir / "semantic_assembly_release_gate.json"
    summary_path = output_dir / "context_incremental_release_closure.json"

    with timing.stage("build-instance-and-fingerprint-plan"):
        reconstruction = read_json(reconstruction_path)
        effective = read_json(effective_path)
        plan = build_context_incremental_brep_plan(ROOT, reconstruction, effective)
        write_json(plan_path, plan)

    cached_manifest = read_json(cache_path) if cache_path.is_file() else None
    cached_batch_path = (
        Path(str(cached_manifest.get("batchPath"))).resolve()
        if cached_manifest and cached_manifest.get("batchPath")
        else None
    )
    batch_path = (
        args.existing_batch.resolve()
        if args.existing_batch
        else cached_batch_path
        or output_dir / f"{Path(plan['assemblyPath']).stem}_leaf_details_batch.json"
    )
    cache_check = {"cacheReusable": False, "reasons": ["no cache manifest"]}
    cache_reused = False

    if cached_manifest is not None and batch_path.is_file():
        with timing.stage("validate-cached-exact-evidence"):
            cache_check = validate_cached_brep_evidence(
                plan, cached_manifest, read_json(batch_path)
            )
            cache_reused = cache_check["cacheReusable"]

    if not cache_reused and args.adopt_existing_batch and batch_path.is_file():
        with timing.stage("adopt-existing-exact-evidence"):
            batch = read_json(batch_path)
            candidate_manifest = {
                "schemaVersion": "semantic-context-incremental-brep-cache/v1",
                "evidenceKey": plan["evidenceKey"],
                "createdAtUtc": datetime.now(timezone.utc).isoformat(),
                "adoptedExistingBatch": True,
                "batchPath": str(batch_path),
            }
            cache_check = validate_cached_brep_evidence(
                plan, candidate_manifest, batch
            )
            if not cache_check["cacheReusable"]:
                raise SystemExit(
                    "Existing batch cannot be adopted: "
                    + "; ".join(cache_check["reasons"])
                )
            write_json(cache_path, candidate_manifest)
            cache_reused = True

    if not cache_reused:
        command = [
            sys.executable,
            str(ROOT / "scripts/capture_leaf_interference_details.py"),
            "--exe",
            str(args.exe.resolve()),
            "--assembly",
            str(plan["assemblyPath"]),
            "--output-dir",
            str(output_dir),
            "--timeout",
            str(args.timeout),
            "--direct-stdio",
        ]
        for item in plan["pairs"]:
            first, second = item["hierarchyPaths"]
            command.extend(("--pair", first, second))
            if item.get("baselinePath"):
                command.extend(
                    ("--accepted-baseline", first, second, item["baselinePath"])
                )
        with timing.stage("run-conditional-leaf-brep", pairCount=len(plan["pairs"])):
            completed = subprocess.run(command, cwd=ROOT, check=False)
        generated = output_dir / f"{Path(plan['assemblyPath']).stem}_leaf_details_batch.json"
        if completed.returncode not in {0, 2} or not generated.is_file():
            raise SystemExit(
                f"B-Rep command failed with exit={completed.returncode}; batch={generated}"
            )
        batch_path = generated
        batch = read_json(batch_path)
        manifest = {
            "schemaVersion": "semantic-context-incremental-brep-cache/v1",
            "evidenceKey": plan["evidenceKey"],
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            "adoptedExistingBatch": False,
            "batchPath": str(batch_path),
        }
        cache_check = validate_cached_brep_evidence(plan, manifest, batch)
        if cache_check["cacheReusable"]:
            write_json(cache_path, manifest)

    with timing.stage("build-release-gate"):
        batch = read_json(batch_path)
        gate = build_semantic_assembly_release_gate(reconstruction, batch)
        gate["artifacts"] = {
            "reconstructionResultPath": str(reconstruction_path),
            "effectiveGraphPath": str(effective_path),
            "brepPlanPath": str(plan_path),
            "brepBatchPath": str(batch_path),
            "brepCachePath": str(cache_path),
        }
        write_json(gate_path, gate)

    summary = {
        "schemaVersion": "semantic-context-incremental-release-closure/v1",
        "success": gate["releaseAllowed"],
        "status": gate["status"],
        "cacheReused": cache_reused,
        "cacheValidation": cache_check,
        "instancesByModuleToken": plan["instancesByModuleToken"],
        "evidenceKey": plan["evidenceKey"],
        "releaseGate": gate,
        "timing": timing.finish(
            status="completed" if gate["releaseAllowed"] else "rejected"
        ),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if gate["releaseAllowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

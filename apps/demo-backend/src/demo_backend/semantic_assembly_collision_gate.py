"""Pair-local AABB/cache collision gate for live semantic assembly steps."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .brep_evidence_cache import (
    build_cache_entry,
    build_pair_fingerprint,
    validate_cache_entry,
)
from .semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore


def module_token(name: str) -> str | None:
    upper = name.upper()
    if upper.startswith("T401"):
        return "T401"
    for token in (
        "A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800",
        "A000", "B000", "D000", "E000", "F000", "G000", "K000", "M000", "N000", "P000", "Z000",
        "JJ00", "SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00", "ZZ00",
        "AA00", "AB00", "AC00", "AD00", "AE00", "AF00", "AG00", "AH00", "AI00", "AJ00",
    ):
        if token in upper:
            return token
    return None


def canonical_pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second), key=str.casefold))


def _baseline_for_pair(
    baselines: dict[tuple[str, str], Path], first_name: str, second_name: str
) -> Path | None:
    exact = baselines.get(canonical_pair(first_name, second_name))
    if exact is not None:
        return exact
    first_token = module_token(first_name)
    second_token = module_token(second_name)
    if first_token and second_token:
        return baselines.get(canonical_pair(first_token, second_token))
    return None


def strict_aabb_separated(first: list[float], second: list[float]) -> bool:
    if len(first) != 6 or len(second) != 6:
        return False
    return any(
        first[axis + 3] < second[axis] or second[axis + 3] < first[axis]
        for axis in range(3)
    )


def evaluate_pair_local_collision_gate(
    pose_payload: dict[str, Any],
    inserted_module_token: str,
    *,
    cache_manifest: dict[str, Any] | None = None,
    accepted_baselines: dict[tuple[str, str], Path] | None = None,
    inserted_module_tokens: set[str] | None = None,
    accepted_contact_token_pairs: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    components = pose_payload.get("components") or []
    inserted_tokens = {
        str(value).upper()
        for value in (inserted_module_tokens or {inserted_module_token})
    }
    inserted = [
        row
        for row in components
        if module_token(str(row.get("Name") or row.get("name") or ""))
        in inserted_tokens
    ]
    if not inserted:
        raise ValueError(
            f"Pose catalog contains no inserted module from {sorted(inserted_tokens)}"
        )
    baselines = accepted_baselines or {}
    accepted_contacts = {
        tuple(sorted((str(first).upper(), str(second).upper())))
        for first, second in (accepted_contact_token_pairs or set())
    }
    cache_entries = {
        str(row.get("cacheKey")): row for row in (cache_manifest or {}).get("entries") or []
    }
    rows = []
    seen: set[tuple[str, str]] = set()
    for first in inserted:
        first_name = str(first.get("Name") or first.get("name"))
        for second in components:
            second_name = str(second.get("Name") or second.get("name"))
            if first_name == second_name:
                continue
            pair = canonical_pair(first_name, second_name)
            if pair in seen:
                continue
            seen.add(pair)
            token_pair = tuple(
                sorted(
                    (
                        str(module_token(first_name) or ""),
                        str(module_token(second_name) or ""),
                    )
                )
            )
            if token_pair in accepted_contacts:
                rows.append(
                    {
                        "pair": list(pair),
                        "moduleTokenPair": list(token_pair),
                        "accepted": True,
                        "method": "declared-installation-contact",
                    }
                )
                continue
            first_box = first.get("BoundingBoxWorld") or first.get("boundingBoxWorld") or []
            second_box = second.get("BoundingBoxWorld") or second.get("boundingBoxWorld") or []
            if strict_aabb_separated(first_box, second_box):
                rows.append({"pair": list(pair), "accepted": True, "method": "strict-aabb-separated"})
                continue
            baseline = _baseline_for_pair(baselines, first_name, second_name)
            policy = "noNewInterferenceOverAcceptedBaseline" if baseline else "zeroInterference"
            fingerprint = build_pair_fingerprint(
                first,
                second,
                policy=policy,
                baseline_path=baseline,
            )
            entry = cache_entries.get(fingerprint["cacheKey"])
            reusable = False
            reasons = ["no matching cache entry"]
            if entry:
                evidence_path = Path(str(entry.get("evidencePath") or ""))
                evidence = (
                    json.loads(evidence_path.read_text(encoding="utf-8"))
                    if evidence_path.is_file()
                    else {}
                )
                validation = validate_cache_entry(entry, fingerprint, evidence)
                reusable = validation["cacheReusable"] is True
                reasons = validation["reasons"]
            rows.append(
                {
                    "pair": list(pair),
                    "accepted": reusable,
                    "method": "pair-brep-cache" if reusable else "exact-brep-required",
                    "cacheKey": fingerprint["cacheKey"],
                    "policy": policy,
                    "baselinePath": str(baseline.resolve()) if baseline else None,
                    "reasons": reasons,
                }
            )
    unresolved = [row for row in rows if row["accepted"] is not True]
    return {
        "schemaVersion": "semantic-assembly-pair-local-collision-gate/v1",
        "insertedModuleToken": inserted_module_token,
        "insertedModuleTokens": sorted(inserted_tokens),
        "pairCount": len(rows),
        "strictAabbAcceptedCount": sum(1 for row in rows if row["method"] == "strict-aabb-separated"),
        "cacheAcceptedCount": sum(1 for row in rows if row["method"] == "pair-brep-cache"),
        "installationContactAcceptedCount": sum(
            1 for row in rows if row["method"] == "declared-installation-contact"
        ),
        "unresolvedExactPairCount": len(unresolved),
        "accepted": not unresolved,
        "pairs": rows,
        "unresolvedPairs": unresolved,
    }


def live_pair_local_collision_hard_gate(
    *,
    store: DurableAssemblyJobStore,
    workspace: Path,
    executable: Path,
    cache_manifest_path: Path,
    accepted_baselines: dict[tuple[str, str], Path] | None = None,
    timeout_seconds: float = 1800.0,
    command_runner: Callable[[list[str], float], Any] | None = None,
    step_member_tokens: dict[str, set[str]] | None = None,
    accepted_contact_token_pairs: set[tuple[str, str]] | None = None,
):
    """Capture poses, reuse safe pair evidence, and compute only cache misses."""

    def default_runner(command: list[str], timeout: float):
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )

    run_command = command_runner or default_runner
    workspace = workspace.resolve()
    executable = executable.resolve()
    pose_script = workspace / "scripts/capture_top_level_component_poses.py"
    brep_script = workspace / "scripts/capture_leaf_interference_details.py"
    baselines = accepted_baselines or {}

    def load_manifest() -> dict[str, Any]:
        if cache_manifest_path.is_file():
            return json.loads(cache_manifest_path.read_text(encoding="utf-8"))
        return {
            "schemaVersion": "pair-brep-cache-manifest/v2",
            "entries": [],
        }

    def save_manifest(payload: dict[str, Any]) -> None:
        payload["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload["entryCount"] = len(payload.get("entries") or [])
        cache_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_manifest_path.with_suffix(cache_manifest_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(cache_manifest_path)

    def gate(job: dict[str, Any], step: dict[str, Any], output: Path, previous: Path | None):
        gate_started = perf_counter()
        gate_dir = store.root / str(job["jobId"]) / "collision-gates" / str(step["stepId"])
        gate_dir.mkdir(parents=True, exist_ok=True)
        pose_path = gate_dir / f"attempt{step['attemptCount']}-poses.json"
        pose_command = [
            sys.executable,
            str(pose_script),
            "--exe",
            str(executable),
            "--assembly",
            str(output),
            "--output",
            str(pose_path),
            "--timeout",
            str(timeout_seconds),
            "--direct-stdio",
        ]
        pose_started = perf_counter()
        completed = run_command(pose_command, timeout_seconds + 60.0)
        pose_duration = perf_counter() - pose_started
        if int(getattr(completed, "returncode", 1)) != 0 or not pose_path.is_file():
            return {
                "accepted": False,
                "message": f"{step['moduleToken']}顶层位姿/AABB捕获失败。",
                "evidencePath": str(gate_dir),
            }
        poses = json.loads(pose_path.read_text(encoding="utf-8"))
        manifest = load_manifest()
        first_pass_started = perf_counter()
        first_pass = evaluate_pair_local_collision_gate(
            poses,
            str(step["moduleToken"]),
            cache_manifest=manifest,
            accepted_baselines=baselines,
            inserted_module_tokens=(step_member_tokens or {}).get(
                str(step["moduleToken"])
            ),
            accepted_contact_token_pairs=accepted_contact_token_pairs,
        )
        first_pass_duration = perf_counter() - first_pass_started
        if first_pass["accepted"] is True:
            first_pass["timingSeconds"] = {
                "poseCapture": round(pose_duration, 6),
                "broadPhaseAndCache": round(first_pass_duration, 6),
                "conditionalBrep": 0.0,
                "total": round(perf_counter() - gate_started, 6),
            }
            evidence_path = gate_dir / f"attempt{step['attemptCount']}-gate.json"
            evidence_path.write_text(json.dumps(first_pass, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return {"accepted": True, "evidencePath": str(evidence_path)}

        exact_dir = gate_dir / f"attempt{step['attemptCount']}-exact"
        exact_command = [
            sys.executable,
            str(brep_script),
            "--exe",
            str(executable),
            "--assembly",
            str(output),
            "--output-dir",
            str(exact_dir),
            "--timeout",
            str(timeout_seconds),
            "--direct-stdio",
        ]
        for row in first_pass["unresolvedPairs"]:
            first_name, second_name = row["pair"]
            exact_command.extend(("--pair", first_name, second_name))
            baseline = _baseline_for_pair(baselines, first_name, second_name)
            if baseline:
                exact_command.extend(("--accepted-baseline", first_name, second_name, str(baseline)))
        exact_started = perf_counter()
        completed = run_command(exact_command, timeout_seconds + 60.0)
        exact_duration = perf_counter() - exact_started
        batch_files = list(exact_dir.glob("*_leaf_details_batch.json"))
        exact_return_code = int(getattr(completed, "returncode", 1))
        # The capture script deliberately exits non-zero when an exact check
        # completes and finds a hard interference.  That is a valid negative
        # gate result, not missing evidence.  Prefer the durable batch whenever
        # it is unique; only fail as "missing evidence" when the batch itself
        # is absent or ambiguous.
        if len(batch_files) != 1:
            return {
                "accepted": False,
                "message": "条件B-rep未形成唯一完整批次证据。",
                "evidencePath": str(exact_dir),
                "exactCommandReturnCode": exact_return_code,
            }

        final_started = perf_counter()
        pose_by_name = {str(row.get("Name") or row.get("name")): row for row in poses.get("components") or []}
        batch = json.loads(batch_files[0].read_text(encoding="utf-8"))
        entries_by_key = {str(row.get("cacheKey")): row for row in manifest.get("entries") or []}
        normalized_dir = cache_manifest_path.parent / "normalized_pair_evidence"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        for row in batch.get("pairs") or []:
            acceptance = row.get("acceptance") or {}
            pair = [str(value) for value in row.get("pair") or []]
            if len(pair) != 2 or acceptance.get("accepted") is not True:
                continue
            detail_path = Path(str(row.get("outputPath") or ""))
            if not detail_path.is_file():
                continue
            detail = json.loads(detail_path.read_text(encoding="utf-8"))
            detail["Acceptance"] = {"Accepted": True, "Policy": acceptance.get("policy")}
            normalized = normalized_dir / ("__".join(sorted(pair, key=str.casefold)) + ".json")
            normalized.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            baseline = _baseline_for_pair(baselines, pair[0], pair[1])
            fingerprint = build_pair_fingerprint(
                pose_by_name[pair[0]],
                pose_by_name[pair[1]],
                policy=str(acceptance.get("policy") or "zeroInterference"),
                baseline_path=baseline,
            )
            entries_by_key[fingerprint["cacheKey"]] = {
                "pair": pair,
                **build_cache_entry(fingerprint, normalized, detail),
            }
        manifest["entries"] = list(entries_by_key.values())
        save_manifest(manifest)
        final = evaluate_pair_local_collision_gate(
            poses,
            str(step["moduleToken"]),
            cache_manifest=manifest,
            accepted_baselines=baselines,
            inserted_module_tokens=(step_member_tokens or {}).get(
                str(step["moduleToken"])
            ),
            accepted_contact_token_pairs=accepted_contact_token_pairs,
        )
        final_duration = perf_counter() - final_started
        final["exactBatchEvidencePath"] = str(batch_files[0])
        final["exactCommandReturnCode"] = exact_return_code
        final["timingSeconds"] = {
            "poseCapture": round(pose_duration, 6),
            "broadPhaseAndCache": round(first_pass_duration, 6),
            "conditionalBrep": round(exact_duration, 6),
            "cacheUpdateAndFinalEvaluation": round(final_duration, 6),
            "total": round(perf_counter() - gate_started, 6),
        }
        evidence_path = gate_dir / f"attempt{step['attemptCount']}-gate.json"
        evidence_path.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "accepted": final["accepted"] is True,
            "evidencePath": str(evidence_path),
            "message": None if final["accepted"] else "仍有未接受的精确干涉对象对。",
        }

    return gate

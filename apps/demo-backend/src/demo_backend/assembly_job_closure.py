from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "assembly-job-static-closure/v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pair(values: list[str]) -> tuple[str, str]:
    if len(values) != 2:
        raise ValueError(f"Collision pair must contain two components: {values}")
    return tuple(sorted((str(values[0]), str(values[1]))))


def build_assembly_job_static_closure(
    job_directory: Path,
    *,
    expected_top_level_object_count: int,
    expected_cad_action_count: int | None = None,
) -> dict[str, Any]:
    directory = job_directory.resolve()
    job = _load(directory / "job.json")
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    duplicates: list[list[str]] = []
    missing: list[str] = []
    rejected: list[dict[str, Any]] = []
    action_count = 0

    for step in job.get("steps") or []:
        checkpoint = step.get("checkpoint") or {}
        gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        if not gate_path.is_file():
            missing.append(f"{step.get('stepId')}:gate")
            continue
        gate = _load(gate_path)
        if gate.get("accepted") is not True:
            rejected.append({"stepId": step.get("stepId"), "gatePath": str(gate_path)})
        for row in gate.get("pairs") or []:
            key = _pair(list(row.get("pair") or []))
            if key in pairs:
                duplicates.append(list(key))
            pairs[key] = {
                "pair": list(key),
                "accepted": row.get("accepted") is True,
                "method": row.get("method"),
                "policy": row.get("policy"),
                "gatePath": str(gate_path),
            }
            if row.get("accepted") is not True:
                rejected.append({"stepId": step.get("stepId"), "pair": list(key)})
        action_paths = checkpoint.get("cadActionEvidencePaths") or []
        action_count += len(action_paths)
        for index, value in enumerate(action_paths, start=1):
            path = Path(str(value)).resolve()
            if not path.is_file():
                missing.append(f"{step.get('stepId')}:cad-action-{index}")
                continue
            if _load(path).get("success") is not True:
                rejected.append({"stepId": step.get("stepId"), "cadActionPath": str(path)})

    components = sorted({value for key in pairs for value in key})
    expected_pair_count = (
        expected_top_level_object_count * (expected_top_level_object_count - 1) // 2
    )
    final_checkpoint = job.get("lastCommittedCheckpoint") or {}
    final_assembly = Path(str(final_checkpoint.get("assemblyPath") or "")).resolve()
    accepted_pair_count = sum(1 for row in pairs.values() if row["accepted"])
    passed = all(
        (
            job.get("status") == "succeeded",
            final_assembly.is_file(),
            not missing,
            not rejected,
            len(components) == expected_top_level_object_count,
            len(pairs) == expected_pair_count,
            accepted_pair_count == expected_pair_count,
            expected_cad_action_count is None or action_count == expected_cad_action_count,
        )
    )
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job.get("jobId"),
        "jobStatus": job.get("status"),
        "expectedTopLevelObjectCount": expected_top_level_object_count,
        "observedTopLevelObjectCountFromPairEvidence": len(components),
        "topLevelComponentsFromPairEvidence": components,
        "expectedPairCount": expected_pair_count,
        "evaluatedUniquePairCount": len(pairs),
        "acceptedPairCount": accepted_pair_count,
        "duplicatePairEvidence": duplicates,
        "cadActionEvidenceCount": action_count,
        "expectedCadActionEvidenceCount": expected_cad_action_count,
        "finalAssemblyPath": str(final_assembly),
        "finalAssemblyExists": final_assembly.is_file(),
        "missingEvidence": missing,
        "rejectedEvidence": rejected,
        "staticFullChainAccepted": passed,
        "productionDynamicReleaseAllowed": False,
        "releaseReason": (
            "完整现场CAD作业、最终实体与全部顶层对象对静态证据通过。"
            if passed
            else "完整现场CAD作业尚未形成实体与对象对全覆盖静态闭包。"
        ),
        "pairs": [pairs[key] for key in sorted(pairs)],
    }


def write_assembly_job_static_closure(
    job_directory: Path,
    *,
    expected_top_level_object_count: int,
    expected_cad_action_count: int | None = None,
) -> Path:
    directory = job_directory.resolve()
    payload = build_assembly_job_static_closure(
        directory,
        expected_top_level_object_count=expected_top_level_object_count,
        expected_cad_action_count=expected_cad_action_count,
    )
    target = directory / "static-closure.json"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target

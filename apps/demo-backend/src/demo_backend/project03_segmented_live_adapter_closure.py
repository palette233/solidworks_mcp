from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "project03-segmented-full-live-adapter-closure/v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _tail_checks(summary_path: Path, token: str, expected_action_count: int) -> dict[str, Any]:
    summary = _load(summary_path)
    job_path = Path(str(summary.get("jobPath") or "")).resolve()
    manifest_path = Path(str(summary.get("evidenceManifestPath") or "")).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    steps = job.get("steps") or []
    step = steps[0] if len(steps) == 1 else {}
    checkpoint = step.get("checkpoint") or {}
    seed = job.get("initialCommittedCheckpoint") or {}
    assembly = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
    gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
    gate = _load(gate_path) if gate_path.is_file() else {}
    action_paths = [Path(str(value)).resolve() for value in checkpoint.get("cadActionEvidencePaths") or []]
    actions = [_load(path) for path in action_paths if path.is_file()]
    checks = {
        "summarySucceeded": summary.get("status") == "succeeded",
        "jobSucceeded": job.get("status") == "succeeded",
        "singleExpectedStep": len(steps) == 1 and step.get("moduleToken") == token,
        "singleAttempt": int(step.get("attemptCount") or 0) == 1,
        "externalVerifiedSeedDeclared": seed.get("externalVerifiedSeed") is True,
        "inputEqualsSeedAssembly": str(checkpoint.get("inputAssemblyPath") or "")
        == str(seed.get("assemblyPath") or ""),
        "expectedCadActionCount": len(action_paths) == expected_action_count
        and len(actions) == expected_action_count,
        "everyCadActionSucceeded": bool(actions)
        and all(action.get("success") is True for action in actions),
        "collisionGateAccepted": gate.get("accepted") is True,
        "unresolvedPairCountIsZero": int(gate.get("unresolvedExactPairCount") or 0) == 0,
        "assemblyExists": assembly.is_file(),
        "manifestEvidenceComplete": manifest.get("evidenceComplete") is True,
        "manifestStaticAccepted": manifest.get("staticExecutionAccepted") is True,
        "noRollback": job.get("rollback") is None,
    }
    return {
        "moduleToken": token,
        "success": all(checks.values()),
        "checks": checks,
        "seed": seed,
        "assemblyPath": str(assembly),
        "gateEvidencePath": str(gate_path),
        "cadActionEvidencePaths": [str(path) for path in action_paths],
        "jobPath": str(job_path),
        "timingReportPath": str(job_path.parent / "timing-report.json"),
        "executionDurationSeconds": float(job.get("executionDurationSeconds") or 0.0),
    }


def build_project03_segmented_full_live_adapter_closure(
    *,
    four_step_closure_path: Path,
    ah00_summary_path: Path,
    aj00_summary_path: Path,
    ab00_summary_path: Path,
) -> dict[str, Any]:
    prefix = _load(four_step_closure_path)
    tails = [
        _tail_checks(ah00_summary_path, "AH00", 1),
        _tail_checks(aj00_summary_path, "AJ00", 1),
        _tail_checks(ab00_summary_path, "AB00", 2),
    ]
    expected_seed_tokens = ["AG00", "AH00", "AJ00"]
    expected_seed_assemblies = [
        str(prefix.get("assemblyPath") or ""),
        tails[0]["assemblyPath"],
        tails[1]["assemblyPath"],
    ]
    continuity = all(
        str(tail.get("seed", {}).get("moduleToken") or "") == seed_token
        and str(tail.get("seed", {}).get("assemblyPath") or "") == seed_assembly
        for tail, seed_token, seed_assembly in zip(
            tails, expected_seed_tokens, expected_seed_assemblies
        )
    )
    checks = {
        "fourStepUninterruptedPrefixClosed": prefix.get("success") is True
        and prefix.get("singleUninterruptedJob") is True,
        "allTailActionsClosed": all(tail["success"] for tail in tails),
        "crossJobCheckpointContinuity": continuity,
        "finalAssemblyExists": Path(tails[-1]["assemblyPath"]).is_file(),
    }
    success = all(checks.values())
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project03",
        "status": (
            "PROJECT03_SEGMENTED_FULL_STATIC_ACTION_CHAIN_CLOSED"
            if success
            else "PROJECT03_SEGMENTED_FULL_STATIC_ACTION_CHAIN_INCOMPLETE"
        ),
        "success": success,
        "sequence": ["AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"],
        "allActionsLiveCadValidated": success,
        "singleUninterruptedJob": False,
        "liveCadApiMayStartForTokens": ["AE00", "AD00", "AI00", "AG00"],
        "fullProjectLiveCadReady": False,
        "productionReady": False,
        "checks": checks,
        "fourStepPrefixClosurePath": str(four_step_closure_path.resolve()),
        "tails": tails,
        "assemblyPath": tails[-1]["assemblyPath"],
        "limitations": [
            "AH00、AJ00和AB00由外部已验证检查点接续，不是一次七步不间断作业。",
            "AG00与AB00使用显式原型残差姿态锚点。",
            "AC00为完整静态几何混合快照，不保留原始内部配合图、层级和运动语义。",
            "AD00动态翻转、龙门权威行程、扫描/校准光学及供胶软管仍未生产验收。",
        ],
    }


def write_project03_segmented_full_live_adapter_closure(
    output_path: Path, **paths: Path
) -> Path:
    payload = build_project03_segmented_full_live_adapter_closure(**paths)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target

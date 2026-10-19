#!/usr/bin/env python3
"""Run an independent 45/45 pair gate on the final Project03 live assembly."""

from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
if str(WORKSPACE / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE / "scripts"))

from demo_backend.semantic_assembly_collision_gate import (  # noqa: E402
    live_pair_local_collision_hard_gate,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore  # noqa: E402
from run_project03_live_adapter_full import baseline_map  # noqa: E402


def main() -> int:
    root = WORKSPACE / "demo/semantic_ports"
    live_root = root / "project03_live_adapter_full_jobs"
    summary = json.loads(
        (live_root / "latest_uninterrupted.json").read_text(encoding="utf-8-sig")
    )
    assembly = Path(
        str((summary.get("lastCommittedCheckpoint") or {}).get("assemblyPath") or "")
    ).resolve()
    if not assembly.is_file():
        raise FileNotFoundError(assembly)
    cache = (
        root
        / "project03_live_adapter_four_step_jobs/pair_brep_cache_manifest_v3.json"
    )
    audit_root = live_root / "independent_collision_audit"
    store = DurableAssemblyJobStore(audit_root / "gate-work")
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=WORKSPACE,
        executable=WORKSPACE
        / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe",
        cache_manifest_path=cache,
        accepted_baselines=baseline_map(cache),
        step_member_tokens={
            "FULL": {
                "AA00",
                "AF00",
                "AE00",
                "AD00",
                "AI00",
                "AG00",
                "AH00",
                "AJ00",
                "AB00",
                "AC00",
            }
        },
        timeout_seconds=3600.0,
    )
    result = gate(
        {"jobId": "project03-final-independent-audit"},
        {
            "stepId": "final-10-object-45-pair-audit",
            "moduleToken": "FULL",
            "attemptCount": 1,
        },
        assembly,
        None,
    )
    evidence_path = Path(str(result.get("evidencePath") or "")).resolve()
    evidence = (
        json.loads(evidence_path.read_text(encoding="utf-8-sig"))
        if evidence_path.is_file()
        else {}
    )
    success = (
        result.get("accepted") is True
        and evidence.get("accepted") is True
        and int(evidence.get("pairCount") or 0) == 45
        and int(evidence.get("unresolvedExactPairCount") or 0) == 0
    )
    payload = {
        "schemaVersion": "project03-final-independent-collision-audit/v1",
        "success": success,
        "status": (
            "PASSED_FINAL_10_OBJECT_45_PAIR_INDEPENDENT_GATE"
            if success
            else "FAILED_OR_INCOMPLETE_FINAL_INDEPENDENT_GATE"
        ),
        "assemblyPath": str(assembly),
        "pairCount": int(evidence.get("pairCount") or 0),
        "strictAabbAcceptedCount": int(
            evidence.get("strictAabbAcceptedCount") or 0
        ),
        "cacheAcceptedCount": int(evidence.get("cacheAcceptedCount") or 0),
        "conditionalBrepSeconds": float(
            (evidence.get("timingSeconds") or {}).get("conditionalBrep") or 0.0
        ),
        "unresolvedExactPairCount": int(
            evidence.get("unresolvedExactPairCount") or 0
        ),
        "gateEvidencePath": str(evidence_path),
        "poseEvidencePath": str(
            evidence_path.with_name("attempt1-poses.json")
        ),
        "cacheManifestPath": str(cache),
        "scopeBoundary": {
            "finalStaticGeometryIndependentlyChecked": success,
            "dynamicMotionValidated": False,
            "productionReleased": False,
        },
    }
    output = audit_root / "project03_final_independent_collision_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())

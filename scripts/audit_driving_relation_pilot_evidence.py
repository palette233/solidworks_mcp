from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mate_transaction_preflight import (  # noqa: E402
    preflight_direct_mate_transaction,
)


DEFAULT_ROOT = ROOT / (
    "demo/semantic_ports/project05_resolved_pair_jobs/"
    "project05-job-2fd5dca2ddd7/attempt-01"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-audit a prior real-CAD driving transaction with the strict gate."
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    evidence_root = args.evidence_root.resolve()
    result_path = evidence_root / "resolved-session.result.json"
    graph_path = evidence_root / "transaction/effective-graph.json"
    output = (
        args.output.resolve()
        if args.output
        else evidence_root / "driving-pilot-audit-v1.json"
    )
    prior = json.loads(result_path.read_text(encoding="utf-8-sig"))
    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    current_preflight = preflight_direct_mate_transaction(
        graph,
        str(prior.get("targetModuleToken") or ""),
        require_closed_dof=True,
        require_multiple_operations=True,
        reject_redundant_mutations=True,
    )
    cad = prior.get("toolResult") or {}
    output_assembly = Path(str(prior.get("outputAssemblyPath") or ""))
    checks = {
        "priorCadTransactionSucceeded": prior.get("success") is True,
        "priorOutputPublished": prior.get("published") is True,
        "sourceAssemblyUnchanged": prior.get("sourceAssemblyUnchanged") is True,
        "outputAssemblyExists": output_assembly.is_file(),
        "outputAssemblyDigestMatches": (
            output_assembly.is_file()
            and _sha256(output_assembly) == prior.get("outputAssemblySha256")
        ),
        "saveCloseReopenPassed": cad.get("Reopened") is True,
        "reopenedMateParametersMatch": cad.get("ReopenedMateParametersMatch") is True,
        "targetFullyConstrained": cad.get("TargetFullyConstrained") is True,
        "requestedAndCreatedMateCountsMatch": (
            int(cad.get("RequestedMateCount") or -1)
            == int(cad.get("CreatedMateCount") or -2)
            and int(cad.get("RequestedMateCount") or 0) > 0
        ),
        "allMateOperationsSucceeded": bool(cad.get("MateResults"))
        and all(row.get("Success") is True for row in cad.get("MateResults") or []),
        "strictCurrentPreflightPassed": current_preflight.get("publishAllowed") is True,
        "strictCurrentDofClosed": (
            current_preflight.get("rigidBodyDofAnalysis") or {}
        ).get("closed")
        is True,
        "strictCurrentNoRedundantMutations": not bool(
            current_preflight.get("redundantMutatingMateNames")
        ),
    }
    passed = all(checks.values())
    report = {
        "schemaVersion": "driving-relation-pilot-evidence-audit/v1",
        "status": "candidate_for_scoped_driving_release" if passed else "blocked",
        "auditedAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "projectId": "project05",
            "targetModuleToken": prior.get("targetModuleToken"),
            "contextModuleToken": prior.get("contextModuleToken"),
            "mateNames": [row.get("MateName") for row in cad.get("MateResults") or []],
            "standaloneRelation": False,
            "compoundPlacementBundle": True,
        },
        "checks": checks,
        "currentStrictPreflight": current_preflight,
        "priorEvidence": {
            "resultPath": str(result_path),
            "effectiveGraphPath": str(graph_path),
            "outputAssemblyPath": str(output_assembly),
            "outputAssemblySha256": prior.get("outputAssemblySha256"),
            "sourceAssemblySha256": prior.get("sourceAssemblySha256Before"),
            "cadDurationSeconds": (prior.get("phaseDurationsSeconds") or {}).get(
                "same-session-cad-execution"
            ),
            "totalDurationSeconds": (prior.get("phaseDurationsSeconds") or {}).get(
                "total"
            ),
        },
        "releaseBoundary": {
            "published": False,
            "reason": (
                "该证据证明一个三配合定位束可进入限定驱动候选；它不证明任意单一"
                "重合、距离或宽度关系均可独立驱动。"
            ),
            "nextAction": (
                "把A000-D000三配合束登记为独立、限定作用域的驱动模板，"
                "再执行一次当前版本CAD事务后才能发布。"
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "checksPassed": sum(value is True for value in checks.values()),
                "checkCount": len(checks),
                "constraintRank": current_preflight["rigidBodyDofAnalysis"][
                    "constraintRank"
                ],
                "residualDof": current_preflight["rigidBodyDofAnalysis"]["residualDof"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

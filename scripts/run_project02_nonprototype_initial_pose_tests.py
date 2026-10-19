from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project02_prototype_dependency_experiment import (  # noqa: E402
    recommended_dependency_replacement,
    summarize_initial_pose_result,
)
from demo_backend.resolved_pair_transaction_jobs import sha256_file  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audit",
        default=(
            "demo/semantic_ports/project02_nonprototype_initial_pose_v1/"
            "prototype_dependency_audit.json"
        ),
    )
    parser.add_argument(
        "--chain-audit",
        default=(
            "demo/semantic_ports/project02_resolved_pair_jobs/"
            "project02-full-static-chain-audit-v1.json"
        ),
    )
    parser.add_argument(
        "--output-directory",
        default=(
            "demo/semantic_ports/project02_nonprototype_initial_pose_v1/cad-runs"
        ),
    )
    args = parser.parse_args()
    audit_path = (WORKSPACE / args.audit).resolve()
    chain_path = (WORKSPACE / args.chain_audit).resolve()
    output = (WORKSPACE / args.output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    audit = load(audit_path)
    chain = load(chain_path)
    if len(audit["steps"]) != len(chain["jobs"]):
        raise ValueError("Dependency audit and durable chain lengths differ.")

    started_at = utc_now()
    started = time.perf_counter()
    results = []
    for row, chain_row in zip(audit["steps"], chain["jobs"], strict=True):
        if row["targetModuleToken"] != chain_row["moduleToken"]:
            raise ValueError("Dependency audit and durable chain order differ.")
        existing_evidence_path = Path(chain_row["evidencePath"])
        existing_evidence = load(existing_evidence_path)
        if not row["topLevelPlacementDependsOnPrototypeCaseAnchor"]:
            summary = summarize_initial_pose_result(row, existing_evidence)
            summary["recommendedNextAction"] = recommended_dependency_replacement(
                row["targetModuleToken"],
                row["contextModuleToken"],
                summary["nonprototypeInitialPoseGatePassed"],
            )
            summary.update(
                {
                    "evidenceMode": "reused_equivalent_no_case_anchor",
                    "evidencePath": str(existing_evidence_path),
                    "ablatedGraphPath": row["ablatedGraphPath"],
                    "note": (
                        "The accepted durable job already used deterministic placement "
                        "with no case anchor, so no duplicate CAD run was required."
                    ),
                }
            )
            results.append(summary)
            continue

        source = Path(existing_evidence["sourceAssemblyPath"]).resolve()
        graph = Path(row["ablatedGraphPath"]).resolve()
        slug = f"{row['order']:02d}-{row['targetModuleToken'].lower()}-to-{row['contextModuleToken'].lower()}"
        assembly = output / f"{slug}-nonprototype-initial-pose.SLDASM"
        evidence_path = output / f"{slug}-nonprototype-initial-pose.result.json"
        stdout_path = output / f"{slug}.stdout.log"
        stderr_path = output / f"{slug}.stderr.log"
        if evidence_path.is_file():
            evidence = load(evidence_path)
            summary = summarize_initial_pose_result(row, evidence)
            summary.update(
                {
                    "evidenceMode": "fresh_top_level_case_anchor_ablation",
                    "evidenceReusedForReport": True,
                    "evidencePath": str(evidence_path),
                    "ablatedGraphPath": str(graph),
                    "processExitCode": 0 if evidence.get("success") else 2,
                    "stdoutPath": str(stdout_path),
                    "stderrPath": str(stderr_path),
                    "recommendedNextAction": recommended_dependency_replacement(
                        row["targetModuleToken"],
                        row["contextModuleToken"],
                        summary["nonprototypeInitialPoseGatePassed"],
                    ),
                }
            )
            results.append(summary)
            continue
        if assembly.exists():
            raise FileExistsError(
                f"Assembly exists without reusable evidence: {assembly}"
            )
        command = [
            sys.executable,
            str(WORKSPACE / "scripts/run_context_mate_graph_insert.py"),
            "--source",
            str(source),
            "--effective",
            str(graph),
            "--target",
            row["targetModuleToken"],
            "--output",
            str(assembly),
            "--expected-source-sha256",
            sha256_file(source),
            "--expected-effective-sha256",
            sha256_file(graph),
            "--result",
            str(evidence_path),
            "--direct-stdio",
            "--timeout",
            "1800",
        ]
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2100,
            check=False,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if not evidence_path.is_file():
            raise RuntimeError(
                f"CAD experiment {slug} produced no evidence; exit={completed.returncode}."
            )
        evidence = load(evidence_path)
        summary = summarize_initial_pose_result(row, evidence)
        summary.update(
            {
                "evidenceMode": "fresh_top_level_case_anchor_ablation",
                "evidencePath": str(evidence_path),
                "ablatedGraphPath": str(graph),
                "processExitCode": completed.returncode,
                "stdoutPath": str(stdout_path),
                "stderrPath": str(stderr_path),
                "recommendedNextAction": recommended_dependency_replacement(
                    row["targetModuleToken"],
                    row["contextModuleToken"],
                    summary["nonprototypeInitialPoseGatePassed"],
                ),
            }
        )
        results.append(summary)

    passed = [row for row in results if row["nonprototypeInitialPoseGatePassed"]]
    failed = [row for row in results if not row["nonprototypeInitialPoseGatePassed"]]
    report = {
        "schemaVersion": "project02-nonprototype-initial-pose-cad-test/v1",
        "startedAt": started_at,
        "finishedAt": utc_now(),
        "durationSeconds": time.perf_counter() - started,
        "projectId": "project02",
        "prototypeDependencyAuditPath": str(audit_path),
        "sourceDurableChainAuditPath": str(chain_path),
        "testedStepCount": len(results),
        "freshCadExperimentCount": sum(
            row["evidenceMode"] == "fresh_top_level_case_anchor_ablation"
            for row in results
        ),
        "reusedAlreadyIndependentCount": sum(
            row["evidenceMode"] == "reused_equivalent_no_case_anchor"
            for row in results
        ),
        "freshCadMeasuredDurationSeconds": sum(
            float(row.get("durationSeconds") or 0.0)
            for row in results
            if row["evidenceMode"] == "fresh_top_level_case_anchor_ablation"
        ),
        "passedStepCount": len(passed),
        "failedStepCount": len(failed),
        "allTopLevelInitialPoseIndependent": not failed,
        "results": results,
        "interpretation": {
            "passedTokens": [
                f"{row['targetModuleToken']}@{row['contextModuleToken']}"
                for row in passed
            ],
            "failedTokens": [
                f"{row['targetModuleToken']}@{row['contextModuleToken']}"
                for row in failed
            ],
            "boundary": (
                "Each step is tested independently against its attested upstream "
                "checkpoint. Failed experimental outputs are diagnostic artifacts "
                "and are never promoted into the durable cumulative chain."
            ),
            "collisionGate": "not_evaluated",
        },
    }
    report_path = output.parent / "nonprototype_initial_pose_cad_test.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

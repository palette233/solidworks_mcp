#!/usr/bin/env python3
"""Bind a separately released P000/AA00 Demo packet to a five-module checkpoint.

Only the cumulative input is rebased.  Direct-installation authority and the
explicit support-position Demo authority remain separate immutable stages.
This command prepares a plan; it never starts SolidWorks or claims CAD passed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_packet_executor import build_global_cad_packet_execution_plan
from demo_backend.multi_release_cad_chain import (
    build_multi_release_cad_chain,
    rebase_single_packet_manifest_for_external_checkpoint,
    validate_multi_release_cad_chain,
)


OUTPUT_ROOT = ROOT / "demo/cross_project_substitution/six-role-project03-base-v1"
ORDERS = {
    "standard": ["AA00", "SS00", "AI00", "BD00", "AG00"],
    "reordered": ["AA00", "AG00", "BD00", "SS00", "AI00"],
}


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"预期JSON对象：{path}")
    return value


def _write_new_or_equal(path: Path, value: dict) -> None:
    if path.exists():
        if _read(path) != value:
            raise ValueError(f"已有文件内容不同，拒绝覆盖：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_demo_identity(manifest: dict) -> None:
    packets = manifest.get("packets") or []
    if len(packets) != 1 or manifest.get("packetCount") != 1:
        raise ValueError("排胶杯追加发布必须恰有一个包。")
    packet = packets[0]
    aliases = packet.get("targetProjectAliases") or []
    if len(aliases) != 1 or aliases[0].get("projectId") != "project05" or aliases[0].get("moduleToken") != "P000":
        raise ValueError("追加目标必须是Project05 P000。")
    cumulative = packet.get("cumulativeInput") or {}
    if cumulative.get("kind") != "base_module_source" or "aa00" not in str(cumulative.get("instanceId") or "").lower():
        raise ValueError("原始Demo必须绑定AA00单基座来源，不得复用A600端口。")


def validate_stage_modes(chain: dict, plan: dict) -> dict:
    stages = chain.get("stages") or []
    policy = (plan.get("releaseAuthority", {}).get("binding", {}).get("releaseMetadata") or {}).get("supportPositionDemoPolicy") or {}
    checks = {
        "twoIndependentReleaseStages": len(stages) == 2,
        "directStageStillDirect": len(stages) == 2 and stages[0].get("relationExecutionMode") == "direct_installation",
        "appendStageExplicitDemo": len(stages) == 2 and stages[1].get("relationExecutionMode") == "datum_placement_demo",
        "exactFourPlusOnePackets": len(stages) == 2 and stages[0].get("packetCount") == 4 and stages[1].get("packetCount") == 1 and chain.get("packetCount") == 5,
        "targetIsP000": plan.get("targetModuleToken") == "P000",
        "authorityVerified": plan.get("releaseAuthority", {}).get("status") == "verified",
        "threeDrivingMates": plan.get("requestedMateCount") == 3 and plan.get("requestedDrivingMateCount") == 3,
        "exactEffectiveGraphCoverage": plan.get("effectiveGraphMateCoverage", {}).get("status") == "exact",
        "supportPositionPolicyRetained": policy.get("mode") == "support_position_demo",
        "holeMatchNotRequired": policy.get("holePatternMatchRequired") is False,
        "actualFixationUnverified": policy.get("actualFixationMethod") == "not_verified",
        "noMechanicalCompatibilityClaim": policy.get("directMechanicalCompatibilityClaim") is False,
    }
    if not all(checks.values()):
        raise ValueError("分阶段追加计划检查失败：" + ", ".join(key for key, value in checks.items() if not value))
    return checks


def build(order_name: str, demo_manifest_path: Path, output_root: Path) -> dict:
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    output_root = output_root.resolve()
    output_root.relative_to(ROOT)
    prepared = _read(output_root / "direct-stage-preparation.json")
    cases = [row for row in prepared.get("cases") or [] if row.get("orderName") == order_name]
    if len(cases) != 1 or cases[0].get("moduleSequence") != ORDERS[order_name]:
        raise ValueError("前置编译报告缺少本次顺序的唯一五模组stage。")
    case = cases[0]
    direct_manifest_path = Path(case["manifestPath"])
    direct_closure_path = output_root / order_name / "direct-stage-closure.json"
    demo = _read(demo_manifest_path.resolve())
    validate_demo_identity(demo)
    append = rebase_single_packet_manifest_for_external_checkpoint(demo, source_stage_id="direct-installation-stage")
    case_root = output_root / order_name
    append_path = case_root / "wastecup-append.cad-transaction-manifest.json"
    _write_new_or_equal(append_path, append)
    chain = build_multi_release_cad_chain(
        ROOT, direct_manifest_path=direct_manifest_path,
        direct_closure_path=direct_closure_path, append_manifest_path=append_path,
        chain_id=f"six-role-project03-base-{order_name}-with-project05-p000",
    )
    validate_multi_release_cad_chain(ROOT, chain)
    chain_path = case_root / "multi-release-chain.json"
    checkpoint = Path(chain["checkpointBinding"]["assemblyPath"])
    output = case_root / f"six-role-{order_name}.SLDASM"
    plan = build_global_cad_packet_execution_plan(
        ROOT, append, "packet-001", output_path=output, input_checkpoint=checkpoint,
    )
    checks = validate_stage_modes(chain, plan)
    plan_path = case_root / "wastecup-append.execution-plan.json"
    _write_new_or_equal(chain_path, chain)
    _write_new_or_equal(plan_path, plan)
    # A rebuild can verify immutable plan files; do not replace its first timing record.
    report_path = case_root / "wastecup-append-preparation.json"
    report = {
        "schemaVersion": "six-role-support-append-preparation/v1",
        "status": "ready_not_started", "success": True,
        "startedAtUtc": started_at, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "orderName": order_name,
        "moduleSequence": [*ORDERS[order_name], "P000"],
        "plannedTopLevelModuleCount": 6,
        "directStageManifestPath": str(direct_manifest_path),
        "directStageClosurePath": str(direct_closure_path),
        "chainPath": str(chain_path), "appendManifestPath": str(append_path),
        "executionPlanPath": str(plan_path),
        "inputCheckpoint": str(checkpoint), "plannedOutputAssemblyPath": str(output),
        "checks": checks, "cadStarted": False,
        "actualFixationMethod": "not_verified", "holePatternMatchRequired": False,
        "collisionOrBrep": "not_evaluated", "completedSixRoleChain": False,
        "totalSeconds": round(perf_counter() - started, 6),
        "runCommand": f'python scripts/run_global_cad_transaction_packet.py "{append_path}" packet-001 --input-checkpoint "{checkpoint}" --output "{output}" --run-dir "{case_root / "live-run"}"',
    }
    if report_path.exists():
        old = _read(report_path)
        stable_fields = ("orderName", "moduleSequence", "chainPath", "appendManifestPath", "executionPlanPath", "checks", "plannedOutputAssemblyPath")
        if any(old.get(field) != report.get(field) for field in stable_fields):
            raise ValueError("既有追加报告与本次执行计划不一致。")
        return old
    _write_new_or_equal(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order", choices=ORDERS, required=True)
    parser.add_argument("--demo-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.order, args.demo_manifest, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

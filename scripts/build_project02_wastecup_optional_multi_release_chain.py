#!/usr/bin/env python3
"""Append the released WasteCup datum demo to a passed Project02 direct chain."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_packet_executor import (  # noqa: E402
    build_global_cad_packet_execution_plan,
)
from demo_backend.multi_release_cad_chain import (  # noqa: E402
    build_multi_release_cad_chain,
    rebase_single_packet_manifest_for_external_checkpoint,
    validate_multi_release_cad_chain,
)


DIRECT_MANIFEST = ROOT / (
    "demo/global_assembly_contexts/"
    "project02-release-a800-a180-a500-v3.cad-transaction-manifest.json"
)
DIRECT_CLOSURE = ROOT / (
    "demo/global_assembly_contexts/"
    "project02-release-a800-a180-a500-v3/closure-report.json"
)
DEMO_MANIFEST = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v64-project02-project05-wastecup-executable-demo-20261015/"
    "explicit-demo.cad-transaction-manifest.json"
)
OUTPUT = ROOT / (
    "demo/cross_project_substitution/wastecup-project05-to-project02-v1/"
    "extended-chain-v2"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_or_verify(path: Path, value: dict) -> None:
    if path.exists():
        if _read(path) != value:
            raise RuntimeError(f"已有证据与本次生成结果不一致：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    append_manifest = rebase_single_packet_manifest_for_external_checkpoint(
        _read(DEMO_MANIFEST), source_stage_id="direct-installation-stage"
    )
    append_path = OUTPUT / "wastecup-append.cad-transaction-manifest.json"
    _write_or_verify(append_path, append_manifest)

    chain = build_multi_release_cad_chain(
        ROOT,
        direct_manifest_path=DIRECT_MANIFEST,
        direct_closure_path=DIRECT_CLOSURE,
        append_manifest_path=append_path,
        chain_id="project02-direct-plus-project05-wastecup-demo-v2",
    )
    validate_multi_release_cad_chain(ROOT, chain)
    chain_path = OUTPUT / "multi-release-chain.json"
    _write_or_verify(chain_path, chain)

    checkpoint = Path(chain["checkpointBinding"]["assemblyPath"])
    planned_output = OUTPUT / "project02-four-native-plus-project05-p000-demo.SLDASM"
    plan = build_global_cad_packet_execution_plan(
        ROOT,
        append_manifest,
        "packet-001",
        output_path=planned_output,
        input_checkpoint=checkpoint,
    )
    plan_path = OUTPUT / "wastecup-append.execution-plan.json"
    _write_or_verify(plan_path, plan)
    plan_ready = bool(
        plan.get("schemaVersion") == "global-cad-packet-execution-plan/v1"
        and (plan.get("releaseAuthority") or {}).get("status") == "verified"
        and int(plan.get("requestedMateCount") or 0) == 3
        and (plan.get("effectiveGraphMateCoverage") or {}).get("status") == "exact"
    )

    summary = {
        "schemaVersion": "multi-release-wastecup-append-offline-closure/v1",
        "status": "passed",
        "chainPath": chain_path.relative_to(ROOT).as_posix(),
        "directStage": {
            "releaseId": chain["stages"][0]["releaseId"],
            "packetCount": chain["stages"][0]["packetCount"],
            "relationExecutionMode": chain["stages"][0]["relationExecutionMode"],
            "realCadClosureReused": True,
            "checkpointAssemblyPath": str(checkpoint),
        },
        "optionalWasteCupStage": {
            "releaseId": chain["stages"][1]["releaseId"],
            "packetCount": chain["stages"][1]["packetCount"],
            "relationExecutionMode": chain["stages"][1]["relationExecutionMode"],
            "executionPlanPath": plan_path.relative_to(ROOT).as_posix(),
            "executionPlanStatus": (
                "ready_for_adapter_execution" if plan_ready else "blocked"
            ),
            "inputAssemblyPath": plan.get("sourceAssemblyPath"),
            "plannedOutputPath": plan.get("outputAssemblyPath"),
        },
        "totalTopLevelModuleCount": 5,
        "totalPacketCount": chain["packetCount"],
        "cadStartedInThisBuild": False,
        "collisionOrBrep": "not_evaluated",
        "checks": {
            "directStageClosurePassed": True,
            "directStageCheckpointDigestMatched": True,
            "releaseAuthoritiesIndependentlyVerified": True,
            "datumDemoNotMixedIntoDirectRelease": True,
            "appendPacketUsesPreviousStageCheckpoint": True,
            "appendPacketExecutablePlanBuilt": plan_ready,
        },
        "statement": (
            "Project02 A600+A800+A180+A500直接安装链与Project05 P000"
            "基准定位Demo以两个独立发布阶段组合；本轮只构建并"
            "验证离线执行计划，未再次启动SolidWorks。"
        ),
    }
    if not all(summary["checks"].values()):
        raise RuntimeError("多发布累计链离线闭合未通过。")
    _write_or_verify(OUTPUT / "offline-closure.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

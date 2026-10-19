#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.natural_language_complete_demo_chain import (  # noqa: E402
    build_complete_demo_chain_closure,
)


DEFAULT_JOB_ID = "project-global-job-163f19364c24"
DEFAULT_OUTPUT_DIR = ROOT / "demo/cross_project_substitution/cumulative-project03-v2"
DEFAULT_RELEASE_ID = (
    "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a reusable evidence closure for a completed NL CAD chain."
    )
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument(
        "--expected-order", nargs="+", default=["SS00", "AI00", "BD00"]
    )
    parser.add_argument("--base-module-token", default="AA00")
    parser.add_argument("--scanner-process-status")
    parser.add_argument("--scanner-module-token", default="AI00")
    parser.add_argument("--transport-module-token", default="SS00")
    args = parser.parse_args()

    job_dir = (
        ROOT / "demo/global_assembly_contexts/manifest_jobs" / args.job_id
    ).resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = (ROOT / output_dir).resolve()
    job = _read(job_dir / "job.json")
    manifest_path = Path(str((job.get("plan") or {}).get("manifestPath") or ""))
    if not manifest_path.is_absolute():
        manifest_path = (ROOT / manifest_path).resolve()
    manifest = _read(manifest_path)
    packet_template_ids = []
    for packet in manifest.get("packets") or []:
        connections = packet.get("connections") or []
        packet_template_ids.append(
            str(connections[0].get("globalTemplateId") or "")
            if len(connections) == 1
            else ""
        )
    release_binding = (job.get("plan") or {}).get("relationReleaseBinding") or {}
    release_manifest_path = Path(str(release_binding.get("releaseManifestPath") or ""))
    if not release_manifest_path.is_absolute():
        release_manifest_path = (ROOT / release_manifest_path).resolve()
    release_manifest = _read(release_manifest_path)
    release_evidence_path = Path(
        str(release_manifest.get("derivationEvidencePath") or "")
    )
    if not release_evidence_path.is_absolute():
        release_evidence_path = (ROOT / release_evidence_path).resolve()
    release_evidence = _read(release_evidence_path)
    cad_results = [
        _read(
            job_dir
            / f"packet-runs/packet-{index:03d}-attempt-01/cad-result.json"
        )
        for index in range(1, len(args.expected_order) + 1)
    ]
    scanner_status = args.scanner_process_status
    scanner_validation = output_dir / "scanner-transport-process-validation.json"
    if not scanner_status:
        scanner_status = (
            _read(scanner_validation).get("status")
            if scanner_validation.is_file()
            else "pending_cross_project_target_validation"
        )
    report = build_complete_demo_chain_closure(
        job,
        cad_results,
        expected_release_id=args.release_id,
        expected_order=args.expected_order,
        base_module_token=args.base_module_token,
        scanner_process_status=scanner_status,
        scanner_module_token=args.scanner_module_token,
        transport_module_token=args.transport_module_token,
        packet_template_ids=packet_template_ids,
        release_manifest=release_manifest,
        release_evidence=release_evidence,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "complete-demo-chain-closure.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 自然语言完整演示链闭合报告",
        "",
        f"- 状态：`{report['status']}`",
        f"- 模组顺序：`{' → '.join(report['moduleSequence'])}`",
        f"- 机械累计装配：`{report['mechanicalDemoChainPassed']}`",
        f"- 扫描工艺验证：`{report['scannerProcessValidation']['status']}`",
        f"- 碰撞/B-rep：`{report['collisionStatus']}`",
        f"- 总执行时间：`{report['executionDurationSeconds']}` 秒",
        f"- 最终装配体：`{report['finalAssemblyPath']}`",
        "",
        report["scannerProcessValidation"]["statement"],
        "",
        "## 逐包机械证据",
        "",
        "| 数据包 | 模组 | 配合 | 外部位姿证据 | 结果 | 耗时（秒） |",
        "|---|---|---:|---|---|---:|",
    ]
    for packet in report["cadPackets"]:
        lines.append(
            "| {packet} | {module} | {created}/{requested} | {placement} | {passed} | {duration} |".format(
                packet=packet.get("packetId"),
                module=packet.get("moduleToken"),
                created=packet.get("createdMateCount"),
                requested=packet.get("requestedMateCount"),
                placement=(
                    f"{packet.get('externalPlacementProven')} "
                    f"({packet.get('externalPlacementEvidenceSource')})"
                ),
                passed=packet.get("passed"),
                duration=packet.get("durationSeconds"),
            )
        )
    failed_packets = [
        str(packet.get("packetId"))
        for packet in report["cadPackets"]
        if packet.get("passed") is not True
    ]
    if failed_packets:
        lines.extend(
            [
                "",
                "严格闭环未通过的数据包：`{}`。CAD命令成功或配合特征存在，不等于外部安装位姿已经由配合独立证明。".format(
                    "、".join(failed_packets)
                ),
            ]
        )
    (output_dir / "complete-demo-chain-closure.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["mechanicalDemoChainPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

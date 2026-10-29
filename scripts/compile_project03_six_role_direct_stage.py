#!/usr/bin/env python3
"""Prepare two direct-installation stages for the six-role cross-project demo.

This is a thin reuse layer, not a new executor.  It narrows the existing Case02
release to SS00/AI00/BD00/AG00, compiles two explicit natural-language orders,
and leaves P000 to a separately authorized support-position Demo stage.  No
SolidWorks process is started by this script.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "apps/demo-backend/src", ROOT / "scripts"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from demo_backend.driving_relation_release_publisher import publish_driving_relation_release
from demo_backend.evidence_backed_long_chain import build_evidence_backed_long_chain_plan
from demo_backend.global_natural_language_manifest import compile_natural_language_manifest_job
from demo_backend.global_relation_catalog_release import load_relation_catalog_release
from demo_backend.released_long_chain_evidence import write_released_long_chain_closure
from publish_project03_expanded_cross_project_chain import TEMPLATES, build_candidate_catalog


RELEASE_ID = "relation-project03-six-role-direct-stage-20261023-v1"
OUTPUT_ROOT = ROOT / "demo/cross_project_substitution/six-role-project03-base-v1"
CONTEXT_PREFIX = "six-role-project03-direct-20261023-v1"
ORDERS = {
    "standard": ("SS00", "AI00", "BD00", "AG00"),
    "reordered": ("AG00", "BD00", "SS00", "AI00"),
}
MODULE_PROJECTS = {"SS00": "project01", "AI00": "project03", "BD00": "project01", "AG00": "project03"}
TEMPLATE_BY_TOKEN = {
    "SS00": "cross_project_project01_SS00_to_project03_AE00_slot",
    "AI00": "AI00_to_AA00_five_mate_installation",
    "BD00": "cross_project_project01_BD00_to_project03_AH00_slot",
    "AG00": "AG00_to_AA00_three_datum_installation_v1",
}
REQUIREMENT_BY_TOKEN = {
    "SS00": "在当前基座上安装项目01 SS00产品传输模组。",
    "AI00": "增加项目03 AI00条码扫描模组，安装到当前基座的已登记扫描安装位。",
    "BD00": "在当前基座上安装项目01 BD00喷嘴校准模组。",
    "AG00": "在当前基座上安装项目03 AG00清洁称重模组。",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_new_or_equal(path: Path, value: dict) -> None:
    if path.exists():
        if _read(path) != value:
            raise ValueError(f"已有本轮文件内容不同，拒绝覆盖：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def selected_template_entries() -> list[dict]:
    """Authorize exactly the four direct relations; old partial AG00 is excluded."""
    selected = []
    for token in ORDERS["standard"]:
        matches = [row for row in TEMPLATES if row.get("legacyTemplateId") == TEMPLATE_BY_TOKEN[token]]
        if len(matches) != 1:
            raise ValueError(f"{token}需要唯一的已验证模板证据。")
        selected.append(copy.deepcopy(matches[0]))
    return selected


def build_compile_payload(order_name: str, context_id: str, release_path: str) -> dict:
    order = ORDERS[order_name]
    return {
        "contextId": context_id,
        "displayName": f"六类跨项目链之前五模组：{order_name}",
        "requirements": ["先建立项目03 AA00设备箱体与固定安装环境。", *[REQUIREMENT_BY_TOKEN[token] for token in order]],
        "releaseManifestPath": release_path,
        "relationExecutionMode": "direct_installation",
        # Sorting by role would erase the intended permutation test.
        "autoOrderByReleasedDependencies": False,
        "overwrite": False,
        "idempotencyKey": context_id,
    }


def validate_direct_manifest(manifest: dict, expected_order: tuple[str, ...]) -> dict:
    packets = manifest.get("packets") or []
    actual = []
    for packet in packets:
        aliases = packet.get("targetProjectAliases") or []
        matches = [row for row in aliases if row.get("moduleToken") in MODULE_PROJECTS
                   and row.get("projectId") == MODULE_PROJECTS.get(row.get("moduleToken"))]
        if len(matches) != 1:
            raise ValueError("每个累计包必须有唯一且项目正确的目标模组。")
        actual.append(matches[0]["moduleToken"])
    checks = {
        "manifestReady": manifest.get("status") == "ready_for_generic_executor_implementation",
        "exactFourPackets": len(packets) == manifest.get("packetCount") == 4,
        "requestedOrderPreserved": actual == list(expected_order),
        "startsFromRegisteredBase": bool(packets) and packets[0].get("cumulativeInput", {}).get("kind") == "base_module_source",
        "baseIsAA00": bool(packets) and "aa00" in str(packets[0].get("cumulativeInput", {}).get("instanceId", "")).lower(),
        "remainingPacketsConsumePreviousCheckpoint": all(
            packet.get("cumulativeInput", {}).get("kind") == "previous_transaction_checkpoint"
            and packet.get("cumulativeInput", {}).get("packetId") == packets[index - 1].get("packetId")
            for index, packet in enumerate(packets) if index > 0
        ),
        "noWasteCupMixedIntoDirectStage": "P000" not in actual,
    }
    if not all(checks.values()):
        raise ValueError("Direct stage检查失败：" + ", ".join(key for key, value in checks.items() if not value))
    return checks


def prepare(output_root: Path, release_id: str, context_prefix: str, order_names: list[str]) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    phases = {}
    output_root = output_root.resolve()
    output_root.relative_to(ROOT)
    report_path = output_root / "direct-stage-preparation.json"
    if report_path.exists():
        raise ValueError(f"本轮准备报告已存在，请使用新的output-root/context-prefix：{report_path}")
    phase = perf_counter()
    catalog_path = output_root / "direct-stage.catalog-preview.json"
    catalog = build_candidate_catalog()
    _write_new_or_equal(catalog_path, catalog)
    entries = selected_template_entries()
    spec = {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": release_id,
        "projectId": "project-global",
        "drivingScope": "project03_AA00_with_project01_SS00_BD00_and_project03_AI00_AG00",
        "catalogPath": catalog_path.relative_to(ROOT).as_posix(),
        "templates": entries,
    }
    _write_new_or_equal(output_root / "direct-stage.release-spec.json", spec)
    manifest_path = ROOT / "demo/global_assembly_catalog/releases" / release_id / "release-manifest.json"
    if not manifest_path.exists():
        publish_driving_relation_release(ROOT, spec)
    released_catalog, release = load_relation_catalog_release(manifest_path, workspace_root=ROOT)
    authorized = set(release.get("scope", {}).get("authorizedDrivingTemplateIds") or [])
    if authorized != {row["globalTemplateId"] for row in entries}:
        raise ValueError("已有不可变发布的授权集合不是本轮四个direct模板。")
    phases["prepareAndValidateReleaseSeconds"] = round(perf_counter() - phase, 6)
    cases = []
    relative_release = manifest_path.relative_to(ROOT).as_posix()
    for order_name in order_names:
        phase = perf_counter()
        order = ORDERS[order_name]
        plan = build_evidence_backed_long_chain_plan(
            released_catalog, release, base_module="project03:AA00",
            ordered_modules=[f"{MODULE_PROJECTS[token]}:{token}" for token in order],
        )
        if plan.get("status") != "ready_for_natural_language_job_compilation":
            raise ValueError(json.dumps(plan.get("blockers"), ensure_ascii=False))
        _write_new_or_equal(output_root / order_name / "direct-stage-plan.json", plan)
        payload = build_compile_payload(order_name, f"{context_prefix}-{order_name}", relative_release)
        _write_new_or_equal(output_root / order_name / "natural-language-request.json", payload)
        compilation = compile_natural_language_manifest_job(ROOT, payload)
        _write_new_or_equal(output_root / order_name / "natural-language-compilation.json", compilation)
        if compilation.get("success") is not True:
            raise ValueError(json.dumps(compilation, ensure_ascii=False))
        checks = validate_direct_manifest(_read(Path(compilation["manifestPath"])), order)
        case = {
            "orderName": order_name,
            "moduleSequence": ["AA00", *order],
            "status": "ready_not_started",
            "jobId": compilation["jobId"],
            "contextId": payload["contextId"],
            "manifestPath": compilation["manifestPath"],
            "compilationReportPath": compilation["reportPath"],
            "checks": checks,
            "runCommand": f"python scripts/run_global_cad_manifest_job.py run {compilation['jobId']}",
            "closeCommand": f"python scripts/compile_project03_six_role_direct_stage.py close --order {order_name} --job-id {compilation['jobId']} --release-id {release_id} --output-root \"{output_root}\"",
            "preparationSeconds": round(perf_counter() - phase, 6),
            "naturalLanguageTimingSeconds": compilation.get("timingSeconds"),
        }
        cases.append(case)
    report = {
        "schemaVersion": "project03-six-role-direct-stage-preparation/v1",
        "status": "ready_not_started",
        "success": True,
        "startedAtUtc": started_at,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "releaseId": release_id,
        "releaseManifestPath": str(manifest_path),
        "releaseDigest": release["releaseDigest"],
        "cases": cases,
        "cadStarted": False,
        "completedSixRoleChain": False,
        "pendingAppendModule": "project05:P000",
        "pendingAppendExecutionMode": "datum_placement_demo",
        "collisionOrBrep": "not_evaluated",
        "actualWasteCupFixation": "not_verified",
        "timingSeconds": {**phases, "totalSeconds": round(perf_counter() - started, 6)},
    }
    _write_new_or_equal(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preparation = sub.add_parser("prepare")
    preparation.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    preparation.add_argument("--release-id", default=RELEASE_ID)
    preparation.add_argument("--context-prefix", default=CONTEXT_PREFIX)
    preparation.add_argument("--order", choices=[*ORDERS, "both"], default="both")
    closure = sub.add_parser("close")
    closure.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    closure.add_argument("--release-id", default=RELEASE_ID)
    closure.add_argument("--order", choices=ORDERS, required=True)
    closure.add_argument("--job-id", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        report = prepare(args.output_root, args.release_id, args.context_prefix,
                         list(ORDERS) if args.order == "both" else [args.order])
    else:
        output = args.output_root.resolve() / args.order / "direct-stage-closure.json"
        if output.exists():
            raise ValueError(f"闭环报告已存在，拒绝覆盖：{output}")
        write_released_long_chain_closure(
            ROOT / "demo/global_assembly_contexts/manifest_jobs" / args.job_id,
            output, expected_order=ORDERS[args.order], expected_release_id=args.release_id,
        )
        report = _read(output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in {"ready_not_started", "passed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

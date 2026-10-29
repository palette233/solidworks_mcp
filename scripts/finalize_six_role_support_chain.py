"""Close one real six-role chain; order is proved by its manifest and CAD evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
sys.path.insert(0, str(ROOT / "scripts"))
from demo_backend.cross_project_wastecup_datum_closure import close_project05_p000_to_project02_a600_datum_demo
from demo_backend.multi_release_cad_chain import validate_multi_release_cad_chain
from verify_p000_aa00_support_geometry import verify_geometry

CONTEXT = ("AA00", "SS00", "AI00", "BD00", "AG00")
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
TARGET_MATES = {f"MCP_GRAPH_P000_AA00_DATUM_{suffix}" for suffix in ("DISTANCE_1", "DISTANCE_2", "SUPPORT")}


def read(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _require(checks: dict[str, bool], label: str) -> None:
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise ValueError(label + "：" + ", ".join(failed))


def _finite(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _index(rows: list[dict]) -> dict:
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get("name") for row in rows):
        return {}
    result = {row["name"]: row for row in rows}
    return result if len(result) == len(rows) else {}


def validate_cumulative_state(state: dict) -> dict[str, bool]:
    """Prove five-to-six accumulation without trusting a reported component count."""
    before, after = state.get("sourceObserved") or {}, state.get("observed") or {}
    old = _index(before.get("components") or [])
    new = _index(after.get("components") or [])
    old_mates = _index(before.get("allTopLevelMates") or [])
    new_mates = _index(after.get("allTopLevelMates") or [])
    target_mates = _index(after.get("mates") or [])
    source_expected = len(old) == 5 and all(sum(f"{token}.001-" in name for name in old) == 1 for token in CONTEXT)
    target = [row for name, row in new.items() if "P000.001-" in name]

    def unchanged(name: str) -> bool:
        a, b = old[name], new.get(name, {})
        x, y = a.get("transform") or [], b.get("transform") or []
        return (len(x) == len(y) == 16
                and all(_finite(v) and _finite(w) and abs(v - w) <= 1e-7 for v, w in zip(x, y))
                and all(a.get(key) == b.get(key) for key in ("sourcePath", "isFixed", "constrainedStatus", "configuration", "solvingState")))

    checks = {
        "fiveModuleSourceObserved": source_expected,
        "sixModulesReopened": len(new) == 6 and set(old) < set(new) and len(target) == 1,
        "upstreamComponentsUnchanged": source_expected and all(unchanged(name) for name in old),
        "upstreamMatesUnchanged": bool(old_mates) and all(new_mates.get(name) == row for name, row in old_mates.items()),
        "upstreamMatesActiveAndClean": bool(old_mates) and all(row.get("isSuppressed") is False and row.get("errorCode") == 0 for row in old_mates.values()),
        "onlyThreeTargetMatesAdded": set(target_mates) == TARGET_MATES and set(new_mates) - set(old_mates) == TARGET_MATES,
        "threeActiveTargetMates": set(target_mates) == TARGET_MATES
        and all(row.get("isSuppressed") is False and row.get("errorCode") == 0 and new_mates.get(name) == row for name, row in target_mates.items()),
        "onlyBaseFixed": len(new) == 6 and all(row.get("isFixed") is ("AA00.001-" in name) for name, row in new.items()),
        "targetNotFixedAndFullyConstrained": len(target) == 1 and target[0].get("isFixed") is False and target[0].get("constrainedStatus") == 3,
    }
    _require(checks, "六类累计装配只读复核未通过")
    return checks


def derive_module_sequence(manifest: dict, closure: dict, requested_order: list[str] | None = None) -> list[str]:
    """No display-only order: both the manifest and executed closure must agree."""
    packets = manifest.get("packets") or []
    if len(packets) != 4 or manifest.get("packetCount") != 4 or [p.get("order") for p in packets] != [1, 2, 3, 4]:
        raise ValueError("前置清单必须按真实执行顺序包含四个有序包。")
    order = []
    for packet in packets:
        tokens = {alias.get("moduleToken") for alias in packet.get("targetProjectAliases") or []}
        if len(tokens) != 1:
            raise ValueError("前置清单目标模组编号不唯一。")
        order.append(tokens.pop())
    if len(set(order)) != 4 or set(order) != set(CONTEXT) - {"AA00"}:
        raise ValueError("前置清单不是SS00/AI00/BD00/AG00四模组。")
    if closure.get("actualOrder") != order or [row.get("moduleToken") for row in closure.get("steps") or []] != order:
        raise ValueError("前置CAD闭环顺序与清单不一致。")
    sequence = ["AA00", *order, "P000"]
    if requested_order is not None and requested_order != sequence:
        raise ValueError("--order必须与清单及真实CAD顺序一致，不能改写实际顺序。")
    return sequence


def _direct_timing_and_evidence(closure: dict) -> dict:
    rows = []
    for step in closure.get("steps") or []:
        path = _path(step["cadEvidencePath"])
        cad = read(path)
        tool = cad.get("toolResult") or {}
        duration = cad.get("durationSeconds")
        checks = {
            "stepPassed": step.get("status") == "passed" and bool(step.get("checks")) and all(value is True for value in step["checks"].values()),
            "cadSucceeded": cad.get("success") is True and tool.get("Success") is True,
            "nonPrototypeInsertion": any("deterministic non-source pose" in str(row).lower() for row in tool.get("Diagnostics") or []),
            "noPoseAnchors": tool.get("TargetCaseAnchored") is False and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0 and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
            "savedReopened": tool.get("Reopened") is True and tool.get("ReopenedMateParametersMatch") is True,
            "outputBound": sha(_path(step["assemblyPath"])) == step.get("assemblySha256") == cad.get("outputAssemblySha256"),
            "durationRecorded": _finite(duration) and duration >= 0 and _finite(step.get("durationSeconds")) and step["durationSeconds"] >= 0,
        }
        _require(checks, f"前置包{step.get('stepId')}证据未通过")
        rows.append({"packetId": step["stepId"], "moduleToken": step["moduleToken"],
                     "durationSeconds": step["durationSeconds"], "cadDurationSeconds": duration,
                     "startedAtUtc": cad.get("startedAtUtc"),
                     "finishedAtUtc": cad.get("finishedAtUtc"), "cadEvidencePath": str(path),
                     "cadEvidenceSha256": sha(path), "phases": tool.get("PhaseDurationsSeconds") or {}})
    total = closure.get("executionDurationSeconds")
    if len(rows) != 4 or not _finite(total) or total < 0:
        raise ValueError("前置四包缺少有效耗时证据。")
    return {"directStageExecution": total, "directPacketExecutionSum": sum(row["durationSeconds"] for row in rows),
            "directCadPacketSum": sum(row["cadDurationSeconds"] for row in rows), "directPackets": rows}


def verify_signed_support_state(state: dict, audit: dict, output: Path) -> dict:
    """Check the actual appended leaf frame, not a prior two-module witness.

    Distance mates can admit a reflected sign branch.  Use the new read-only
    snapshot and its current file hash; never trust a detached success report.
    """
    geometry = verify_geometry(state, audit, current_assembly_sha256=sha(output))
    _require({"signedSupportPositionMatches": geometry.get("success") is True},
             "最终累计链排胶杯有符号支承定位未通过")
    return geometry


def finalize(root: Path, candidate_root: Path, requested_order: list[str] | None = None) -> dict:
    chain = read(root / "multi-release-chain.json")
    validate_multi_release_cad_chain(ROOT, chain)
    direct_stage, append_stage = chain["stages"]
    binding = chain["checkpointBinding"]
    direct_closure = read(_path(binding["closureEvidencePath"]))
    direct_manifest = read(_path(direct_stage["manifestPath"]))
    append_manifest = read(_path(append_stage["manifestPath"]))
    sequence = derive_module_sequence(direct_manifest, direct_closure, requested_order)
    timing = _direct_timing_and_evidence(direct_closure)
    run = root / "live-run"
    envelope, cad, plan = (read(run / name) for name in ("execution-envelope.json", "cad-result.json", "execution-plan.json"))
    graph_path = _path(envelope["executionEffectiveMateGraphPath"])
    graph = read(graph_path)
    state = read(root / "read-only-chain-verification.json")
    output = _path(envelope["outputAssemblyPath"])
    audit_path = candidate_root / "candidate_audit.json"
    audit = read(audit_path)
    geometry = verify_signed_support_state(state, audit, output)
    datum = close_project05_p000_to_project02_a600_datum_demo(
        candidate_audit=audit, cad_result=cad, effective_graph_path=graph_path,
        output_assembly_path=output, read_only_state=state,
        expected_context_module_tokens=CONTEXT, target_base_token="AA00", target_project_id="project03",
    )
    edit, policy = graph.get("EditPolicy") or {}, graph.get("SupportPositionDemoPolicy") or {}
    targets = [row for row in graph.get("Modules") or [] if row.get("ModuleToken") == "P000"]
    append_packets = append_manifest.get("packets") or []
    append_packet = append_packets[0] if len(append_packets) == 1 else {}
    release = envelope.get("relationReleaseBinding") or {}
    checks = {
        **datum["checks"], **validate_cumulative_state(state),
        "genericExecutorSucceeded": envelope.get("success") is True,
        "signedSupportPositionMatches": geometry.get("success") is True,
        "fourDirectPacketsAndOneAppend": direct_stage.get("packetCount") == 4 and append_stage.get("packetCount") == 1 and chain.get("packetCount") == 5,
        "actualOrderBound": sequence == ["AA00", *direct_closure["actualOrder"], "P000"],
        "newReleaseBound": release.get("releaseDigest") == append_stage["releaseDigest"] and release.get("releaseId") == append_stage["releaseId"]
        and (plan.get("relationReleaseBinding") or {}).get("releaseDigest") == append_stage["releaseDigest"],
        "appendManifestPacketBound": plan.get("manifestDigest") == append_manifest.get("manifestDigest")
        and plan.get("packetId") == envelope.get("packetId") == append_packet.get("packetId")
        and plan.get("packetDigest") == envelope.get("packetDigest") == append_packet.get("packetDigest")
        and plan.get("targetModuleToken") == "P000",
        "executionGraphBound": sha(graph_path) == envelope["executionEffectiveMateGraphSha256"] == cad["effectiveGraphSha256"]
        and sha(_path(envelope["authoritativeEffectiveMateGraphPath"])) == envelope["authoritativeEffectiveMateGraphSha256"] == plan["effectiveMateGraphSha256"]
        and graph == plan["effectiveMateGraphExecutionView"],
        "sourceCheckpointUnchanged": state.get("sourceCheckpointSha256Before") == state.get("sourceCheckpointSha256After") == binding["assemblySha256"] == cad["sourceAssemblySha256Before"] == sha(_path(binding["assemblyPath"]))
        and _path(state["sourceCheckpointPath"]).resolve() == _path(plan["sourceAssemblyPath"]).resolve() == _path(binding["assemblyPath"]).resolve(),
        "outputEnvelopeBound": envelope.get("outputAssemblySha256") == sha(output)
        and _path(plan["outputAssemblyPath"]).resolve() == output.resolve(),
        "noPoseAnchors": edit.get("initialPlacementMode") == "deterministic" and edit.get("initialPlacementVariant") == 1
        and edit.get("fixedModuleTokens") == ["AA00"] and not edit.get("caseAnchoredModuleTokens")
        and not edit.get("targetLeafPoseAnchors") and not graph.get("CaseAnchor") and not graph.get("TargetLeafPoseAnchors")
        and len(targets) == 1 and targets[0].get("SourceTransform") == IDENTITY,
        "supportPolicyPreserved": policy.get("mode") == "support_position_demo" and policy.get("actualFixationMethod") == "not_verified"
        and policy.get("holePatternMatchRequired") is False and policy.get("directMechanicalCompatibilityClaim") is False
        and policy.get("positionParametersMeters") == audit.get("positionParametersMeters"),
    }
    _require(checks, "六类累计链验收未通过")
    append_time, read_time = cad.get("durationSeconds"), state.get("durationSeconds")
    if not all(_finite(value) and value >= 0 for value in (append_time, read_time)):
        raise ValueError("追加或只读复核耗时无效。")
    timing.update({"newCadPacket": append_time, "readOnlyChainVerification": read_time,
                   "signedSupportGeometryVerification": geometry["durationSeconds"],
                   "appendCadPhases": datum["timingSeconds"]["phases"],
                   "totalMeasuredExecution": timing["directStageExecution"] + append_time + read_time + geometry["durationSeconds"]})
    return {
        "schemaVersion": "six-role-support-position-chain-closure/v1",
        "status": "PASSED_SIX_ROLE_SUPPORT_POSITION_CHAIN_DEMO", "success": True,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "chainId": chain["chainId"],
        "moduleSequence": sequence, "topLevelModuleCount": 6, "executedPacketCount": 5,
        "contextModuleTokens": list(CONTEXT), "crossProjectIds": ["project01", "project03", "project05"],
        "roleCoverage": ["Base", "Transport", "Scanner", "Calibration", "CleaningWeighing", "WasteCup"],
        "mode": "support_position_demo", "actualFixationMethod": "not_verified", "holePatternMatchRequired": False,
        "directMechanicalCompatibilityClaim": False, "collisionOrBrep": "not_evaluated",
        "outputAssemblyPath": str(output), "outputAssemblySha256": sha(output),
        "sourceCheckpointPath": binding["assemblyPath"], "sourceCheckpointSha256": binding["assemblySha256"],
        "directClosurePath": str(_path(binding["closureEvidencePath"])), "directClosureSha256": sha(_path(binding["closureEvidencePath"])),
        "candidateAuditPath": str(audit_path), "candidateAuditSha256": sha(audit_path),
        "releaseId": append_stage["releaseId"], "releaseDigest": append_stage["releaseDigest"],
        "checks": checks, "positionParametersMeters": audit["positionParametersMeters"],
        "signedSupportGeometryVerification": geometry,
        "cadResultPath": str(run / "cad-result.json"), "readOnlyVerificationPath": str(root / "read-only-chain-verification.json"),
        "timingSeconds": timing, "startedAtUtc": timing["directPackets"][0]["startedAtUtc"], "finishedAtUtc": state.get("finishedAtUtc"),
        "limitations": ["排胶杯实际固定方式暂未验证；孔位匹配不是本定位Demo的硬条件。",
                        "六类齐全不等于完整整机，也不证明六类模组在所有项目之间任意互换。",
                        "位置参数是显式Demo设计参数；碰撞、B-rep、动态工艺和生产放行未评估。",
                        "本文件只证明所记录的真实顺序；其他顺序需要单独执行及闭环证据。"],
    }


def write_closure(root: Path, value: dict) -> None:
    paths = [root / name for name in ("chain-closure.json", "chain-closure-CN.md")]
    if any(path.exists() for path in paths):
        raise FileExistsError("拒绝覆盖已有六类累计链闭环证据。")
    timing = value["timingSeconds"]
    lines = ["# 六类跨项目累计装配闭环", "", f"状态：`{value['status']}`", "",
             "真实累计顺序：" + " → ".join(value["moduleSequence"]), "",
             "- 前置四个真实CAD包形成五模组检查点，再执行P000支承定位追加包。",
             "- 六模组重开清点通过；原五模组位姿与配合不变；新增三条配合激活，P000未固定且完全约束。",
             "- 排胶杯孔位匹配及实际固定方式不是本Demo验收条件，实际固定方式暂未验证。", "",
             f"输出：`{value['outputAssemblyPath']}`", "", "## 各环节耗时", ""]
    lines += [f"- {row['packetId']} {row['moduleToken']}：{row['durationSeconds']:.3f}秒。" for row in timing["directPackets"]]
    lines += [f"- 前置四包执行阶段：{timing['directStageExecution']:.3f}秒。",
              f"- 排胶杯追加包 CAD adapter（不含全部外层命令开销）：{timing['newCadPacket']:.3f}秒。",
              f"- 最终只读复核：{timing['readOnlyChainVerification']:.3f}秒。",
              f"- 有符号支承位置纯计算复核：{timing['signedSupportGeometryVerification']:.6f}秒。",
              f"- 部分口径合计：{timing['totalMeasuredExecution']:.3f}秒（前四包外层＋追加adapter＋只读及几何复核；不是完整外层总耗时）。",
              "- 完整外层时间须结合 outer-execution-timing.json，由 summarize_six_role_chain_timings.py 另行汇总；内部时间不得重复相加。",
              "", "## 能力边界", "", *[f"- {item}" for item in value["limitations"]], ""]
    paths[0].write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths[1].write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--order", help="Optional exact six-token order, including AA00 and P000.")
    args = parser.parse_args()
    requested = [token.strip() for token in args.order.split(",")] if args.order else None
    value = finalize(args.root.resolve(), args.candidate_root.resolve(), requested)
    write_closure(args.root.resolve(), value)
    print(json.dumps({key: value[key] for key in ("status", "moduleSequence", "outputAssemblyPath", "timingSeconds")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

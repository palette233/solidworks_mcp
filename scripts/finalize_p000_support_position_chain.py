"""Close a support-position append using real CAD and read-only chain evidence."""
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
from demo_backend.cross_project_wastecup_datum_closure import close_project05_p000_to_project02_a600_datum_demo
from demo_backend.multi_release_cad_chain import validate_multi_release_cad_chain

DEFAULT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-chain-v3"
CONTEXT = ("A600", "A800", "A180", "A500")
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_cumulative_state(state: dict) -> dict:
    """Check the actual upstream components/mates, not just the new target."""
    before, after = state.get("sourceObserved") or {}, state.get("observed") or {}
    old = {row["name"]: row for row in before.get("components") or []}
    new = {row["name"]: row for row in after.get("components") or []}
    expected_before = len(old) == 4 and all(sum(f"{token}.001-" in name for name in old) == 1 for token in CONTEXT)
    def same_component(name):
        a, b = old[name], new.get(name, {})
        x, y = a.get("transform") or [], b.get("transform") or []
        return (len(x) == len(y) == 16
                and all(math.isfinite(v) and math.isfinite(w) and abs(v-w) <= 1e-7 for v, w in zip(x, y))
                and all(a.get(k) == b.get(k) for k in ("sourcePath", "isFixed", "constrainedStatus", "configuration", "solvingState")))
    old_mates = {row["name"]: row for row in before.get("allTopLevelMates") or []}
    new_mates = {row["name"]: row for row in after.get("allTopLevelMates") or []}
    target_names = {row["name"] for row in after.get("mates") or []}
    checks = {
        "fourModuleSourceObserved": expected_before,
        "fiveModulesReopened": len(new) == 5 and set(old) < set(new)
        and sum("P000.001-" in name for name in new) == 1,
        "upstreamComponentsUnchanged": expected_before and all(same_component(name) for name in old),
        "upstreamMatesUnchanged": bool(old_mates) and all(new_mates.get(name) == row for name, row in old_mates.items()),
        "onlyThreeTargetMatesAdded": len(target_names) == 3 and set(new_mates)-set(old_mates) == target_names,
        "upstreamMatesActiveAndClean": bool(old_mates) and all(row.get("isSuppressed") is False and row.get("errorCode") == 0 for row in old_mates.values()),
    }
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise ValueError("累计装配只读复核未通过：" + ", ".join(failed))
    return checks


def finalize(root: Path) -> dict:
    chain = read(root / "multi-release-chain.json")
    validate_multi_release_cad_chain(ROOT, chain)
    run = root / "live-run"
    envelope = read(run / "execution-envelope.json")
    cad = read(run / "cad-result.json")
    plan = read(run / "execution-plan.json")
    graph_path = Path(envelope["executionEffectiveMateGraphPath"])
    graph = read(graph_path)
    state = read(root / "read-only-chain-verification.json")
    output = Path(envelope["outputAssemblyPath"])
    audit = read(root.parent / "support-position-demo-v2/candidate_audit.json")
    datum = close_project05_p000_to_project02_a600_datum_demo(
        candidate_audit=audit, cad_result=cad, effective_graph_path=graph_path,
        output_assembly_path=output, read_only_state=state,
        expected_context_module_tokens=CONTEXT,
    )
    policy = graph.get("SupportPositionDemoPolicy") or {}
    edit = graph.get("EditPolicy") or {}
    target = [row for row in graph["Modules"] if row["ModuleToken"] == "P000"]
    binding = chain["checkpointBinding"]
    checks = {
        **datum["checks"], **validate_cumulative_state(state),
        "genericExecutorSucceeded": envelope.get("success") is True,
        "newReleaseBound": (envelope.get("relationReleaseBinding") or {}).get("releaseDigest") == chain["stages"][1]["releaseDigest"],
        "executionGraphBound": sha(graph_path) == envelope["executionEffectiveMateGraphSha256"] == cad["effectiveGraphSha256"]
        and sha(envelope["authoritativeEffectiveMateGraphPath"]) == envelope["authoritativeEffectiveMateGraphSha256"]
        and graph == plan["effectiveMateGraphExecutionView"],
        "sourceCheckpointUnchanged": state.get("sourceCheckpointSha256Before") == state.get("sourceCheckpointSha256After") == binding["assemblySha256"] == cad["sourceAssemblySha256Before"] == sha(binding["assemblyPath"]),
        "noPoseAnchors": edit.get("initialPlacementMode") == "deterministic"
        and edit.get("initialPlacementVariant") == 1 and edit.get("fixedModuleTokens") == ["A600"]
        and not edit.get("caseAnchoredModuleTokens") and not edit.get("targetLeafPoseAnchors")
        and not graph.get("CaseAnchor") and not graph.get("TargetLeafPoseAnchors")
        and len(target) == 1 and target[0].get("SourceTransform") == IDENTITY,
        "supportPolicyPreserved": policy.get("mode") == "support_position_demo"
        and policy.get("actualFixationMethod") == "not_verified"
        and policy.get("holePatternMatchRequired") is False
        and policy.get("positionParametersMeters") == audit["positionParametersMeters"],
        "threeActiveTargetMates": datum["checks"]["threeNamedMatesActiveAfterReopen"],
        "targetNotFixed": datum["checks"]["onlyBaseFixedTargetLocatedByMates"],
    }
    if not all(value is True for value in checks.values()):
        raise ValueError("累计链验收未通过：" + ", ".join(k for k, v in checks.items() if v is not True))
    return {
        "schemaVersion": "p000-support-position-chain-closure/v1",
        "status": "PASSED_SUPPORT_POSITION_CHAIN_DEMO", "success": True,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "mode": "support_position_demo", "actualFixationMethod": "not_verified",
        "holePatternMatchRequired": False, "directMechanicalCompatibilityClaim": False,
        "moduleSequence": [*CONTEXT, "P000"], "topLevelModuleCount": 5,
        "sourceStageReused": True, "reexecutedPacketCount": 1,
        "outputAssemblyPath": str(output), "outputAssemblySha256": sha(output),
        "sourceCheckpointPath": binding["assemblyPath"], "sourceCheckpointSha256": binding["assemblySha256"],
        "releaseId": chain["stages"][1]["releaseId"], "releaseDigest": chain["stages"][1]["releaseDigest"],
        "checks": checks, "positionParametersMeters": audit["positionParametersMeters"],
        "cadResultPath": str(run / "cad-result.json"),
        "readOnlyVerificationPath": str(root / "read-only-chain-verification.json"),
        "timingSeconds": {"newCadPacket": cad["durationSeconds"],
                          "readOnlyChainVerification": state["durationSeconds"],
                          "cadPhases": datum["timingSeconds"]["phases"]},
        "startedAtUtc": cad["startedAtUtc"], "finishedAtUtc": state["finishedAtUtc"],
        "collisionOrBrep": "not_evaluated",
        "legacyExternalPlacementWitness": datum.get("legacyExternalPlacementWitness"),
        "limitations": ["实际固定方式暂未验证。", "复用已通过的前置四模组检查点，本轮仅执行P000追加，未从零重跑全链。",
                        "五模组链不含清洁/称重，不等于六类全覆盖或完整整机。",
                        "位置参数是显式Demo设计参数，不是孔距或厂商安装尺寸；碰撞、B-rep、动态工艺未评估。"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT)
    args = parser.parse_args()
    root = args.root.resolve()
    value = finalize(root)
    for name in ("chain-closure.json", "chain-closure-CN.md"):
        if (root / name).exists():
            raise FileExistsError("拒绝覆盖已有闭环证据：" + name)
    (root / "chain-closure.json").write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    text = ["# 排胶杯支承定位累计装配闭环", "", f"状态：`{value['status']}`", "",
            "累计顺序：A600箱体 → A800传输 → A180扫描 → A500校准 → Project05 P000排胶杯。", "",
            "- 前置四模组复用已验证检查点，本轮只实际追加P000。",
            "- P000从非原型位姿插入，以支承重合＋80 mm、390 mm距离配合定位。",
            "- 五模组重开清点通过；原四模组的位姿和既有配合保持不变；新增三条配合激活，P000未固定且完全约束。",
            "- 孔位匹配不是本Demo硬条件；实际固定方式暂未验证。碰撞/B-rep/动态工艺未评估。", "",
            f"输出：`{value['outputAssemblyPath']}`", "", "## 时间记录", "",
            f"- 新CAD包：{value['timingSeconds']['newCadPacket']:.3f}秒。",
            f"- 只读累计复核：{value['timingSeconds']['readOnlyChainVerification']:.3f}秒。", "",
            "## 能力边界", "", *[f"- {item}" for item in value["limitations"]], ""]
    (root / "chain-closure-CN.md").write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({k: v for k, v in value.items() if k not in {"checks", "legacyExternalPlacementWitness"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

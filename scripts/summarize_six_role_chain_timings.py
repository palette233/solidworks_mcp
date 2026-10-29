"""Summarize existing timing evidence only; never run CAD or rewrite closures."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("计时必须是有限非负数。")
    return value


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("时间戳必须包含时区。")
    return result


def summarize_case(closure, outer, job, preparation):
    if closure.get("success") is not True or job.get("status") != "succeeded" or outer.get("exitCode") != 0:
        raise ValueError("仅汇总已完成的累计链、持久任务和外层命令。")
    timing = closure["timingSeconds"]
    direct, append, inspection = [seconds(value) for value in (timing["directStageExecution"], outer["wallSeconds"], timing["readOnlyChainVerification"])]
    adapter = seconds(timing["newCadPacket"])
    if abs(direct - seconds(job["executionDurationSeconds"])) > 1e-6 or append < adapter:
        raise ValueError("外层计时与持久任务或内部adapter不一致。")
    attempts, failed, successful = [], 0.0, 0.0
    for step in job["steps"]:
        if step.get("status") != "succeeded" or not step.get("attempts"):
            raise ValueError("前置包缺少成功尝试记录。")
        for index, attempt in enumerate(step["attempts"]):
            duration = seconds(attempt["durationSeconds"])
            passed = index == len(step["attempts"]) - 1
            successful += duration if passed else 0
            failed += 0 if passed else duration
            attempts.append({"packetId": step["stepId"], "moduleToken": step["moduleToken"], **attempt,
                             "outcome": "successful" if passed else "superseded_failed_attempt"})
    if len(job["steps"]) != 4 or direct + 0.1 < successful + failed:
        raise ValueError("四包尝试计时不能超出已累计的直接阶段计时。")
    starts = [job["startedAt"], *[row["startedAt"] for row in attempts if row.get("startedAt")]]
    earliest = min(starts, key=instant)  # Resume may reset job.startedAt; attempts retain the original start.
    elapsed = (instant(closure["finishedAtUtc"]) - instant(earliest)).total_seconds()
    measured = direct + append + inspection  # Inner CAD/attempt subtotals are NOT added again.
    if elapsed + 0.1 < measured:
        raise ValueError("外层阶段合计不能超过实际经过时间。")
    return {"moduleSequence": closure["moduleSequence"], "startedAtUtc": earliest, "earliestAttemptOrJobStart": earliest,
            "latestRunStartedAt": job["startedAt"], "finishedAtUtc": closure["finishedAtUtc"],
            "preparationSeconds": seconds(preparation["preparationSeconds"]), "naturalLanguageTimingSeconds": preparation.get("naturalLanguageTimingSeconds"),
            "directOuterExecutionSeconds": direct, "directSuccessfulPacketSeconds": successful, "directFailedAttemptSeconds": failed,
            "directAdapterSubtotalSeconds": seconds(timing["directCadPacketSum"]), "directAttempts": attempts,
            "appendOuterExecutionSeconds": append, "appendStartedAtUtc": outer["startedAtUtc"], "appendFinishedAtUtc": outer["finishedAtUtc"],
            "appendAdapterSeconds": adapter, "appendOuterMinusAdapterSeconds": append - adapter,
            "readOnlyVerificationSeconds": inspection, "signedGeometryOfflineSeconds": seconds(timing.get("signedSupportGeometryVerification", 0)),
            "measuredOuterExecutionTotalSeconds": measured, "elapsedWallSeconds": elapsed,
            "interStageWaitingAndUnmeasuredOverheadSeconds": max(0, elapsed - measured),
            "legacyClosurePartialTotalSeconds": seconds(timing["totalMeasuredExecution"])}


def build_summary(root):
    started, clock, inputs = datetime.now(timezone.utc).isoformat(), perf_counter(), []
    def read(path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        inputs.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw.decode("utf-8-sig"))
    preparation = read(root / "direct-stage-preparation.json")
    cases = {}
    for name in ("standard", "reordered"):
        closure = read(root / name / "chain-closure.json")
        direct_closure = read(closure["directClosurePath"])
        job = read(direct_closure["jobPath"])
        prep = next(row for row in preparation["cases"] if row["orderName"] == name)
        if prep["jobId"] != job["jobId"]:
            raise ValueError("准备记录与实际任务身份不同。")
        cases[name] = summarize_case(closure, read(root / name / "outer-execution-timing.json"), job, prep)
    return {"schemaVersion": "six-role-chain-timing-summary/v1", "success": True, "cases": cases, "inputEvidence": inputs,
            "sharedPreparationSeconds": preparation["timingSeconds"], "preparationStartedAtUtc": preparation["startedAtUtc"],
            "preparationFinishedAtUtc": preparation["finishedAtUtc"], "startedAtUtc": started,
            "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "summaryDurationSeconds": perf_counter() - clock,
            "accountingRule": "外层执行合计=直接阶段累计编排+排胶杯完整generic命令+最终只读复核。adapter内部时间、成功包及失败尝试均为子集，不再相加。",
            "excludes": "开发、人工排查、阶段间等待、双模组先验测试、离线编译及signed geometry离线分析；总经过时间单列，不称为纯CAD耗时。"}


def write_summary(root, report):
    paths = [root / "timing-summary.json", root / "timing-summary-CN.md"]
    if any(path.exists() for path in paths):
        raise FileExistsError("拒绝覆盖已有时间摘要。")
    lines = ["# 六类累计装配耗时摘要", "", report["accountingRule"], "", "不含：" + report["excludes"], "",
             "| 环节（秒） | 标准顺序 | 变更顺序 |", "|---|---:|---:|"]
    for label, key in [("离线准备（另列）", "preparationSeconds"), ("前四包外层编排", "directOuterExecutionSeconds"),
                       ("其中：失败尝试（不再相加）", "directFailedAttemptSeconds"), ("其中：adapter内部（不再相加）", "directAdapterSubtotalSeconds"),
                       ("P000完整外层命令", "appendOuterExecutionSeconds"), ("其中：P000 adapter（不再相加）", "appendAdapterSeconds"),
                       ("最终只读复核", "readOnlyVerificationSeconds"), ("外层执行合计", "measuredOuterExecutionTotalSeconds"),
                       ("总经过时间（含阶段间等待）", "elapsedWallSeconds"), ("阶段间等待及未计入开销", "interStageWaitingAndUnmeasuredOverheadSeconds")]:
        lines.append(f"| {label} | {report['cases']['standard'][key]:.3f} | {report['cases']['reordered'][key]:.3f} |")
    for name, case in report["cases"].items():
        lines += ["", f"## {name}", "", f"最早尝试至最终复核：{case['startedAtUtc']} → {case['finishedAtUtc']}",
                  f"最近一次启动/恢复：{case['latestRunStartedAt']}。排障等待只计入总经过时间，不计入外层执行合计。", ""]
        lines += [f"- {row['packetId']} {row['moduleToken']} 尝试{row['attempt']}：{row['durationSeconds']:.3f}秒，{row['outcome']}。" for row in case["directAttempts"]]
    for path, content in ((paths[0], json.dumps(report, ensure_ascii=False, indent=2) + "\n"), (paths[1], "\n".join(lines) + "\n")):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    root = parser.parse_args().root.resolve()
    write_summary(root, build_summary(root))

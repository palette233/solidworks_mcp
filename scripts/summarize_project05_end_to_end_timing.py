#!/usr/bin/env python3
"""Summarize successful Project05 pipeline timings without hiding debug attempts."""

from __future__ import annotations

import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def main() -> int:
    started = time.perf_counter()
    solve = load("demo/layout_previews/project05_pipeline_timing.json")
    replay = load("demo/layout_previews/project05_replay_preparation_timing.json")
    closure = load("demo/semantic_ports/project05_ordered_direct_rank1_v7/project05_static_collision_release_closure.json")
    candidate = load("demo/semantic_ports/project05_ordered_direct_rank1_v7/conditional_brep_with_baseline/step08_B000_cumulative_leaf_details_batch.json")
    prototype = load("demo/layout_previews/project05_prototype_conditional_brep/FL9C254098AA00.001_leaf_details_batch.json")
    stages = closure["stageChain"]
    phases = [
        {"name": "constraint-solve-and-approval", "durationSeconds": solve["durationSeconds"], "evidence": "demo/layout_previews/project05_pipeline_timing.json"},
        {"name": "replay-manifest-preparation", "durationSeconds": replay["durationSeconds"], "evidence": "demo/layout_previews/project05_replay_preparation_timing.json"},
        {"name": "ordered-cad-save-reopen-gates", "durationSeconds": closure["stageDurationSeconds"], "evidence": "nine *.stage-result.json files across rank1_v1/v6/v7"},
        {"name": "prototype-conditional-brep-baseline", "durationSeconds": prototype["timing"]["durationSeconds"], "evidence": "demo/layout_previews/project05_prototype_conditional_brep/FL9C254098AA00.001_leaf_details_batch.json"},
        {"name": "candidate-conditional-brep-gate", "durationSeconds": candidate["timing"]["durationSeconds"], "evidence": "demo/semantic_ports/project05_ordered_direct_rank1_v7/conditional_brep_with_baseline/step08_B000_cumulative_leaf_details_batch.json"},
    ]
    payload = {
        "schemaVersion": "project05-end-to-end-timing/v1",
        "projectId": "project05",
        "successfulPipelineMeasured": closure["success"] is True,
        "phases": phases,
        "cadStages": stages,
        "successfulPhaseDurationSeconds": round(sum(float(item["durationSeconds"]) for item in phases), 6),
        "successfulPhaseDurationMinutes": round(sum(float(item["durationSeconds"]) for item in phases) / 60.0, 3),
        "interpretation": [
            "This is the sum of successful measured phases, not one uninterrupted wall-clock run.",
            "Failed calibration attempts are preserved in v1-v5 artifacts and are not hidden inside the successful-path total.",
            "Every CAD stage result contains per-MCP-call timestamps for further profiling.",
        ],
    }
    payload["summaryGenerationSeconds"] = round(time.perf_counter() - started, 6)
    json_path = ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v7/project05_end_to_end_timing.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = json_path.with_suffix(".md")
    lines = [
        "# 项目05端到端成功路径计时",
        "",
        f"成功阶段累计：**{payload['successfulPhaseDurationSeconds']:.3f} 秒（{payload['successfulPhaseDurationMinutes']:.3f} 分钟）**。",
        "",
        "| 环节 | 耗时（秒） |",
        "|---|---:|",
    ]
    lines.extend(f"| {item['name']} | {float(item['durationSeconds']):.3f} |" for item in phases)
    lines.extend(["", "## CAD逐阶段", "", "| 阶段 | 模组 | 耗时（秒） |", "|---|---|---:|"])
    lines.extend(
        f"| {item['stageId']} | {item['moduleToken']} | {float(item['durationSeconds']):.3f} |"
        for item in stages
    )
    lines.extend(["", "说明：这是成功路径各环节的计时求和，并非一次连续运行的墙钟时间；失败调试轮次仍保留在 v1-v5 证据中。", ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"success": True, "json": str(json_path), "markdown": str(markdown_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

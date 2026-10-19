from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_context_mate_graph_insert import project_target_context_graph  # noqa: E402


SUPPORTED = {
    "B000": ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/B000/assembly_plan_effective.json",
    "F000": ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/F000/assembly_plan_effective.json",
    "G000": ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/G000/assembly_plan_effective.json",
    "K000": ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/K000/assembly_plan_effective.json",
    "M000": ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/M000/assembly_plan_effective.json",
    "P000": ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/P000/assembly_plan_effective.json",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def build_nonanchor_graph(graph: dict[str, Any], target: str) -> dict[str, Any]:
    target = target.strip().upper()
    if target not in SUPPORTED:
        raise ValueError(f"不支持的Project05目标：{target}")
    projected = project_target_context_graph(graph, target)
    policy = projected.get("EditPolicy") or projected.get("editPolicy")
    if not isinstance(policy, dict):
        raise ValueError("有效图缺少EditPolicy。")
    original_anchors = [
        str(value).upper() for value in policy.get("caseAnchoredModuleTokens") or []
    ]
    if target not in original_anchors:
        raise ValueError(f"源有效图未声明{target}案例锚点，不能执行预期的消融。")
    policy["initialPlacementMode"] = "deterministic"
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    mates = projected.get("Mates") or projected.get("mates") or []
    active = [
        row
        for row in mates
        if not bool(row.get("IsSuppressed", row.get("isSuppressed", False)))
    ]
    if len(active) < 2:
        raise ValueError("无锚点实验至少需要两条有效机械配合。")
    projected["NonAnchorCheckpointExperiment"] = {
        "schemaVersion": "project05-nonanchor-checkpoint-graph/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "targetModuleToken": target,
        "sourceCaseAnchors": original_anchors,
        "caseAnchorsRemoved": True,
        "initialPlacementMode": "deterministic",
        "activeMateCount": len(active),
        "sourceGraphDigest": _digest(graph),
        "collisionStatus": "not_evaluated",
        "statement": (
            "目标从独立文件和确定性的非案例初始位姿插入；只允许配合求解定位。"
        ),
    }
    return projected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="生成Project05附加模组的无案例锚点checkpoint有效图。"
    )
    parser.add_argument("--target", required=True, choices=sorted(SUPPORTED))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    source = (args.source or SUPPORTED[args.target]).resolve()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"拒绝覆盖：{output}")
    graph = build_nonanchor_graph(_read(source), args.target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "targetModuleToken": args.target,
                "source": str(source),
                "output": str(output),
                "graphDigest": _digest(graph),
                "activeMateCount": graph["NonAnchorCheckpointExperiment"][
                    "activeMateCount"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

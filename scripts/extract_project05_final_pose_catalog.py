from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage-result",
        default="demo/semantic_ports/project05_ordered_direct_rank1_v7/step08_B000_cumulative.stage-result.json",
    )
    parser.add_argument(
        "--output",
        default="demo/semantic_ports/project05_ordered_direct_rank1_v7/step08_B000_top_level_poses.json",
    )
    args = parser.parse_args()
    source = (ROOT / args.stage_result).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    captures = [
        step.get("payload")
        for step in payload.get("steps") or []
        if step.get("tool") == "list_component_poses"
        and isinstance(step.get("payload"), list)
    ]
    if not captures:
        raise SystemExit("No list_component_poses payload exists in the stage result.")
    poses = captures[-1]
    expected = int(payload.get("expectedTopLevelCountAfterStage") or 0)
    if len(poses) != expected:
        raise SystemExit(f"Expected {expected} top-level poses, found {len(poses)}.")
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schemaVersion": "project05-top-level-pose-catalog/v1",
        "projectId": "project05",
        "sourceStageResultPath": str(source),
        "componentCount": len(poses),
        "components": poses,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output), "componentCount": len(poses)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract only selected Project02 module poses from a Replay result."
    )
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    replay = load(args.replay.resolve())
    layout = load(args.layout.resolve())
    required = {
        str(item.get("componentName") or "")
        for item in layout.get("components") or []
        if item.get("componentName")
    }
    pose_step = next(
        (
            step
            for step in replay.get("steps") or []
            if step.get("tool") == "list_component_poses"
        ),
        None,
    )
    if not pose_step or not isinstance(pose_step.get("payload"), list):
        raise SystemExit("Replay result has no list_component_poses payload")
    by_name = {
        str(item.get("Name") or ""): item
        for item in pose_step["payload"]
        if isinstance(item, dict)
    }
    missing = sorted(required - set(by_name))
    if missing:
        raise SystemExit(f"Replay pose capture is missing selected modules: {missing}")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([by_name[name] for name in sorted(required)], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "selectedModuleCount": len(required),
                "sourceTopLevelCount": len(by_name),
                "excludedContextObjectCount": len(by_name) - len(required),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

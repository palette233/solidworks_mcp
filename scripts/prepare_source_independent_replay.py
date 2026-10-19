"""Anchor the source-independent FL9A solution to A500 for safe SolidWorks Replay."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "demo" / "FL9A24D062A000_source_independent_layout2d.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_source_independent_replay_layout2d.json"
ANCHOR = "FL9A24D062A500.001-1"


def translate_bounds(bounds: list[float], delta_u: float, delta_v: float) -> None:
    if len(bounds) < 4:
        return
    bounds[0] = float(bounds[0]) + delta_u
    bounds[1] = float(bounds[1]) + delta_v
    bounds[2] = float(bounds[2]) + delta_u
    bounds[3] = float(bounds[3]) + delta_v


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate a source-independent layout so a selected component stays at the Replay origin."
    )
    parser.add_argument("--source", default=str(SOURCE), help="Source layout JSON path.")
    parser.add_argument("--output", default=str(OUTPUT), help="Anchored Replay layout JSON path.")
    parser.add_argument("--anchor", default=ANCHOR, help="Component instance kept at layout x=0, y=0.")
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    document = json.loads(source_path.read_text(encoding="utf-8"))
    result = copy.deepcopy(document)
    components = {item["componentName"]: item for item in result["components"]}
    anchor_name = str(args.anchor)
    if anchor_name not in components:
        raise SystemExit(f"Replay anchor is missing: {anchor_name}")

    anchor_layout = components[anchor_name]["layout2d"]
    delta_u = -float(anchor_layout["x"])
    delta_v = -float(anchor_layout["y"])

    for item in result["components"]:
        layout = item["layout2d"]
        layout["x"] = float(layout["x"]) + delta_u
        layout["y"] = float(layout["y"]) + delta_v
        footprint = item.get("projectedFootprint")
        if isinstance(footprint, dict):
            for key in ("minU", "maxU"):
                footprint[key] = float(footprint[key]) + delta_u
            for key in ("minV", "maxV"):
                footprint[key] = float(footprint[key]) + delta_v
        for envelope_name in (
            "interactionEnvelope",
            "hardBodyEnvelope",
            "transportSweepEnvelope",
            "transportStaticKeepoutEnvelope",
        ):
            envelope = item.get(envelope_name)
            bounds = envelope.get("bounds") if isinstance(envelope, dict) else None
            if isinstance(bounds, list):
                translate_bounds(bounds, delta_u, delta_v)

    plan = result.setdefault("constraintPlan", {})
    plan["pinnedComponentName"] = anchor_name
    plan["requiresAnchorTranslationBeforeReplay"] = False
    plan["replayAnchorTranslation"] = {
        "anchorComponentName": anchor_name,
        "deltaU": delta_u,
        "deltaV": delta_v,
        "preservesRelativeLayout": True,
        "reason": "Keep the real A500 bottom-face center fixed while replaying a source-position-independent relative solution.",
    }
    plan["validationDiagnosticsCoordinateFrame"] = (
        "source-independent coordinates before replay anchor translation; component envelopes were translated"
    )
    source_independent_test = result.setdefault("sourceIndependentTest", {})
    source_independent_test["replayApplied"] = False
    source_independent_test["note"] = (
        "Anchor translation completed; this file is ready for CAD Replay into a separate assembly copy."
    )
    result["message"] = (
        "Source-independent layout translated to the real A500 anchor and prepared for SolidWorks Replay."
    )

    anchored = components[anchor_name]["layout2d"]
    if abs(anchored["x"]) > 1e-12 or abs(anchored["y"]) > 1e-12:
        raise SystemExit(f"Anchor translation failed: {anchored}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "source": str(source_path),
                "output": str(output_path),
                "anchorComponentName": anchor_name,
                "deltaU": delta_u,
                "deltaV": delta_v,
                "componentCount": len(result["components"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

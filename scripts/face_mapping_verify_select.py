from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "apps" / "demo-backend" / "tools" / "McpToolRunner" / "bin" / "Release" / "net8.0" / "McpToolRunner.dll"
DEFAULT_MAPPING = ROOT / "vendor" / "solidworks-mcp" / "app" / "SolidWorksMcpApp" / "bin" / "Release" / "net8.0-windows" / "win-x64" / "face_mappings.json"


def call_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = json.dumps({"tools": tools}, ensure_ascii=True)
    completed = subprocess.run(
        ["dotnet", str(RUNNER)],
        cwd=ROOT,
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.decode("utf-8", errors="replace"))

    data = json.loads(completed.stdout.decode("utf-8"))
    return data.get("results", [])


def first_text(result: dict[str, Any]) -> str:
    for item in result.get("content", []):
        if item.get("type") == "text":
            return item.get("text", "")
    return ""


def parse_text_json(result: dict[str, Any]) -> dict[str, Any]:
    text = first_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"rawText": text}


def load_mapping(path: Path, component_name: str, face_name: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    component = data.get(component_name)
    if not isinstance(component, dict) or face_name not in component:
        raise SystemExit(f"Mapping not found: component={component_name}, face={face_name}, path={path}")
    mapping = component[face_name]
    if not isinstance(mapping, dict):
        raise SystemExit(f"Mapping entry is not an object: component={component_name}, face={face_name}, path={path}")
    return mapping


def get_key(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return None


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a recorded face, probe it, and compare it with the stored mapping.")
    parser.add_argument("--component", required=True, help="Component instance name, e.g. A-1")
    parser.add_argument("--face", default="\u5e95\u9762", help="Face mapping name. Default: bottom face")
    parser.add_argument("--mapping-path", default=str(DEFAULT_MAPPING), help="Path to face_mappings.json")
    parser.add_argument("--center-tolerance", type=float, default=1e-5, help="Allowed local-center distance in meters")
    parser.add_argument("--area-relative-tolerance", type=float, default=1e-3, help="Allowed relative area error")
    args = parser.parse_args()

    mapping_path = Path(args.mapping_path)
    recorded = load_mapping(mapping_path, args.component, args.face)

    results = call_tools(
        [
            {
                "tool": "clear_selection",
                "arguments": {},
            },
            {
                "tool": "select_face_by_name",
                "arguments": {"faceName": args.face, "componentName": args.component, "append": False},
            },
            {
                "tool": "get_selected_face_mapping_probe",
                "arguments": {"faceName": args.face, "componentName": args.component},
            },
        ]
    )

    select_result = parse_text_json(results[1])
    probe_result = parse_text_json(results[2])

    recorded_center = recorded.get("localCenter")
    selected_center = get_key(probe_result, "LocalCenter", "localCenter")
    recorded_area = recorded.get("area")
    selected_area = get_key(probe_result, "Area", "area")
    recorded_leaf = recorded.get("leafComponentName")
    selected_leaf = get_key(probe_result, "LeafComponentName", "leafComponentName")
    recorded_leaf_full = recorded.get("leafComponentFullName")
    selected_leaf_full = get_key(probe_result, "LeafComponentFullName", "leafComponentFullName")

    print("=== SelectFaceByName result ===")
    print(json.dumps(select_result, ensure_ascii=False, indent=2))
    print("\n=== Probe after select ===")
    print(json.dumps(probe_result, ensure_ascii=False, indent=2))

    if not isinstance(recorded_center, list) or not isinstance(selected_center, list):
        print("\nRESULT: FAIL")
        raise SystemExit("Could not compare local centers. Check mapping/probe output above.")
    if recorded_area is None or selected_area is None:
        print("\nRESULT: FAIL")
        raise SystemExit("Could not compare areas. Check mapping/probe output above.")

    center_distance = distance(recorded_center, selected_center)
    area_relative_error = abs(float(recorded_area) - float(selected_area)) / max(abs(float(recorded_area)), 1e-12)
    if recorded_leaf_full and selected_leaf_full:
        leaf_matches = recorded_leaf_full == selected_leaf_full
    else:
        leaf_matches = recorded_leaf == selected_leaf
    passed = (
        bool(get_key(select_result, "Success", "success"))
        and center_distance <= args.center_tolerance
        and area_relative_error <= args.area_relative_tolerance
        and leaf_matches
    )

    print("\n=== Comparison ===")
    print(f"mapping path: {mapping_path}")
    print(f"recorded leaf: {recorded_leaf}")
    print(f"selected leaf: {selected_leaf}")
    print(f"recorded leaf full: {recorded_leaf_full}")
    print(f"selected leaf full: {selected_leaf_full}")
    print(f"leaf matches: {leaf_matches}")
    print(f"recorded localCenter: {recorded_center}")
    print(f"selected localCenter: {selected_center}")
    print(f"center distance: {center_distance:.12g} m")
    print(f"center tolerance: {args.center_tolerance:.12g} m")
    print(f"recorded area: {recorded_area}")
    print(f"selected area: {selected_area}")
    print(f"area relative error: {area_relative_error:.12g}")
    print(f"area relative tolerance: {args.area_relative_tolerance:.12g}")
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

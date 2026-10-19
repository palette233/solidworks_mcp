"""Build source-position-independent leaf-body occupancy boxes for Project 02.

The SolidWorks captures store conservative world AABBs.  This script projects
their eight corners into the recorded Common Base frame, then subtracts the
component bottom-centre anchor.  The result can move with a candidate placement
without reading the prototype position during solving.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEOMETRY = ROOT / "demo" / "FL9A24D062A000_8components_real_geometry.json"
DEFAULT_CAPTURE = ROOT / "demo" / "FL9A24D062A000_interaction_v8_leaf_body_envelopes.json"
DEFAULT_CAPTURE_LAYOUT = ROOT / "demo" / "FL9A24D062A000_interaction_v8_replay_result.json"
DEFAULT_TRANSPORT = ROOT / "demo" / "FL9A24D062A800_leaf_body_envelopes.json"
DEFAULT_EVIDENCE = ROOT / "demo" / "interference_v10"
DEFAULT_OUTPUT = ROOT / "demo" / "FL9A24D062A000_structural_occupancy.json"
STRUCTURAL_CODES = ("A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401")
# Only leaf bodies that participated in an exact B-Rep collision become hard
# solver obstacles. Full leaf AABBs contain large empty corners on sparse
# frames and made the bounded search both over-conservative and prohibitively
# expensive; the remaining bodies stay covered by the final CAD B-Rep gate.
FULL_LEAF_OCCUPANCY_CODES: tuple[str, ...] = ()
PRESERVE_BODY_BOX_CODES = STRUCTURAL_CODES
# Repeated exact checks showed that an active-leaf cutting plane can move two
# service modules into a previously unseen part of each other's structure.
# For such service/service pairs, use a small number of full major-subassembly
# unions as a pair-specific coarse body gate. This remains much cheaper than
# hundreds of leaf boxes and does not block unrelated portal/frame nesting.
FULL_SUBASSEMBLY_PAIR_PARTNERS: dict[str, tuple[str, ...]] = {}
# Sparse nested frames need complete pair coverage, but direct-subassembly
# unions close real openings and can make the layout falsely infeasible.  For
# A100/A200 retain one box per leaf instance instead.  Partner scoping keeps
# this extra detail out of every unrelated module comparison.
# Kept as an opt-in mechanism.  Project 02 A100/A200 cannot enable it: even
# per-leaf AABBs close non-convex passages that exact B-Rep proves usable.
FULL_LEAF_PAIR_PARTNERS: dict[str, tuple[str, ...]] = {}


def parse_component_pairs(values: list[str] | None) -> tuple[set[frozenset[str]], dict[str, tuple[str, ...]]]:
    """Parse symmetric CODE:CODE pairs into an auditable partner lookup."""
    pairs: set[frozenset[str]] = set()
    partners: dict[str, set[str]] = {}
    for raw in values or []:
        parts = [part.strip().upper() for part in raw.split(":")]
        if len(parts) != 2 or not all(parts) or parts[0] == parts[1]:
            raise ValueError(
                f"Invalid component pair {raw!r}; expected two different codes such as A100:A300."
            )
        first, second = parts
        unknown = sorted({first, second} - set(STRUCTURAL_CODES))
        if unknown:
            raise ValueError(
                f"Unknown structural component code(s) in {raw!r}: {', '.join(unknown)}"
            )
        pair = frozenset((first, second))
        pairs.add(pair)
        partners.setdefault(first, set()).add(second)
        partners.setdefault(second, set()).add(first)
    return pairs, {
        code: tuple(sorted(code_partners))
        for code, code_partners in sorted(partners.items())
    }


def dot(first: list[float], second: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def subtract(first: list[float], second: list[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def component_code(name: str) -> str:
    if name.upper().startswith("T401"):
        return "T401"
    marker = "D062A"
    if marker not in name:
        return name
    return "A" + name.split(marker, 1)[1].split(".", 1)[0]


def corners(box: list[float]) -> list[list[float]]:
    return [
        [x, y, z]
        for x in (box[0], box[3])
        for y in (box[1], box[4])
        for z in (box[2], box[5])
    ]


def rotate_local(u: float, v: float, quarters: int) -> tuple[float, float]:
    radians = math.radians((quarters % 4) * 90.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    return cosine * u - sine * v, sine * u + cosine * v


def layout_components(document: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read rows from a layout, durable Replay result, or saved pose array."""
    if isinstance(document, list) and document:
        return document
    direct = document.get("components")
    if isinstance(direct, list) and direct:
        return direct
    for step in document.get("steps") or []:
        if step.get("tool") != "apply_captured_common_base_layout":
            continue
        payload = step.get("payload") or {}
        replayed = payload.get("components")
        if isinstance(replayed, list) and replayed:
            return replayed
    baseline_replay = document.get("baselineReplay")
    diagnostics = document.get("diagnostics")
    if isinstance(baseline_replay, str) and isinstance(diagnostics, list):
        baseline_path = Path(baseline_replay)
        if not baseline_path.is_absolute():
            baseline_path = ROOT / baseline_path
        baseline_rows = layout_components(
            json.loads(baseline_path.resolve().read_text(encoding="utf-8"))
        )
        deltas = {
            str(item.get("componentName")): item
            for item in diagnostics
            if isinstance(item, dict) and item.get("componentName")
        }
        projected_rows: list[dict[str, Any]] = []
        for source in baseline_rows:
            row = copy.deepcopy(source)
            component_name = str(row.get("componentName") or row.get("Name") or "")
            delta = deltas.get(component_name)
            layout = row.get("layout2d")
            if delta and isinstance(layout, dict):
                delta_layout = delta.get("deltaLayoutMeters")
                if isinstance(delta_layout, list) and len(delta_layout) >= 2:
                    layout["x"] = float(layout.get("x", 0.0)) + float(delta_layout[0])
                    layout["y"] = float(layout.get("y", 0.0)) + float(delta_layout[1])
                layout["thetaDegrees"] = float(layout.get("thetaDegrees", 0.0)) + float(
                    delta.get("thetaDeltaDegrees", 0.0)
                )
            projected_rows.append(row)
        return projected_rows
    raise ValueError(
        "Layout document has neither root components, an "
        "apply_captured_common_base_layout Replay record, nor a projection report."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--capture-layout", type=Path, default=DEFAULT_CAPTURE_LAYOUT)
    parser.add_argument("--transport-capture", type=Path, default=DEFAULT_TRANSPORT)
    parser.add_argument(
        "--extra-capture",
        type=Path,
        action="append",
        default=None,
        help="Additional leaf-body capture. Repeat together with --extra-capture-layout.",
    )
    parser.add_argument(
        "--extra-capture-layout",
        type=Path,
        action="append",
        default=None,
        help="Placement layout used when the matching --extra-capture was recorded.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        action="append",
        default=None,
        help="Exact B-Rep evidence directory. Repeat to merge evidence from multiple CAD iterations.",
    )
    parser.add_argument(
        "--evidence-layout",
        type=Path,
        action="append",
        default=None,
        help="Replay result matching an --evidence-dir. When supplied for every directory, exact interfering body AABBs are converted directly to local boxes.",
    )
    parser.add_argument(
        "--cad-only-pair",
        action="append",
        default=None,
        help="Component-code pair such as A200:A800 whose non-convex passage must remain an exact CAD gate instead of an AABB hard cut.",
    )
    parser.add_argument(
        "--full-leaf-pair",
        action="append",
        default=None,
        help=(
            "Component-code pair such as A100:A300 that requires one pair-scoped "
            "occupancy box per captured leaf instance. Repeat for additional pairs."
        ),
    )
    parser.add_argument(
        "--base-occupancy",
        type=Path,
        help=(
            "Existing local occupancy model to augment with new exact B-Rep evidence. "
            "This avoids replaying every historical evidence directory for each iteration."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        full_leaf_pairs, requested_full_leaf_partners = parse_component_pairs(
            args.full_leaf_pair
        )
    except ValueError as exc:
        parser.error(str(exc))
    full_leaf_pair_partners = {
        code: tuple(
            sorted(
                set(FULL_LEAF_PAIR_PARTNERS.get(code, ()))
                | set(requested_full_leaf_partners.get(code, ()))
            )
        )
        for code in set(FULL_LEAF_PAIR_PARTNERS) | set(requested_full_leaf_partners)
    }

    base_occupancy_path = args.base_occupancy.resolve() if args.base_occupancy else None
    base_occupancy = (
        json.loads(base_occupancy_path.read_text(encoding="utf-8"))
        if base_occupancy_path
        else None
    )
    base_components = (base_occupancy or {}).get("components") or {}

    geometry = json.loads(args.geometry.resolve().read_text(encoding="utf-8"))
    frame = geometry["baseFrame"]
    origin = [float(value) for value in frame["origin"]]
    axes = {
        "u": [float(value) for value in frame["uAxis"]],
        "v": [float(value) for value in frame["vAxis"]],
        "n": [float(value) for value in frame["normal"]],
    }
    geometry_layouts = {
        item["componentName"]: item["layout2d"]
        for item in geometry["components"]
    }
    capture_layout_document = json.loads(
        args.capture_layout.resolve().read_text(encoding="utf-8")
    )
    capture_layouts = {
        item["componentName"]: item["layout2d"]
        for item in layout_components(capture_layout_document)
    }
    extra_captures = [path.resolve() for path in (args.extra_capture or [])]
    extra_layout_paths = [path.resolve() for path in (args.extra_capture_layout or [])]
    if len(extra_captures) != len(extra_layout_paths):
        raise SystemExit(
            "--extra-capture and --extra-capture-layout must be supplied the same number of times."
        )
    capture_layouts_by_path: dict[Path, dict[str, Any]] = {
        args.capture.resolve(): capture_layouts,
        args.transport_capture.resolve(): geometry_layouts,
    }
    for capture_path, layout_path in zip(extra_captures, extra_layout_paths):
        layout_document = json.loads(layout_path.read_text(encoding="utf-8"))
        capture_layouts_by_path[capture_path] = {
            item["componentName"]: item["layout2d"]
            for item in layout_components(layout_document)
        }

    captures: dict[str, tuple[dict[str, Any], Path]] = {}
    for path in (
        args.capture.resolve(),
        args.transport_capture.resolve(),
        *extra_captures,
    ):
        document = json.loads(path.read_text(encoding="utf-8"))
        for item in document.get("captures", []):
            captures[item["TopLevelComponent"]["Name"]] = (item, path)

    active_leaf_names: set[str] = set()
    active_leaf_partner_codes: dict[str, set[str]] = {}
    evidence_files: list[str] = []
    evidence_pair_count = 0
    cad_only_pairs = {
        frozenset(part.strip() for part in value.split(":", 1))
        for value in (args.cad_only_pair or [])
        if ":" in value
    }
    evidence_directories = [
        path.resolve() for path in (args.evidence_dir or [DEFAULT_EVIDENCE])
    ]
    evidence_layout_paths = [path.resolve() for path in (args.evidence_layout or [])]
    if evidence_layout_paths and len(evidence_layout_paths) != len(evidence_directories):
        raise SystemExit(
            "--evidence-layout must be supplied once for every --evidence-dir."
        )
    exact_boxes_by_component: dict[str, list[dict[str, Any]]] = {}
    exact_box_keys: dict[str, set[tuple[Any, ...]]] = {}
    for directory_index, evidence_directory in enumerate(evidence_directories):
        evidence_layouts: dict[str, Any] | None = None
        if evidence_layout_paths:
            layout_document = json.loads(
                evidence_layout_paths[directory_index].read_text(encoding="utf-8")
            )
            evidence_layouts = {
                item["componentName"]: item["layout2d"]
                for item in layout_components(layout_document)
            }
        # New closure runs are stored in per-batch subdirectories.  Recursive
        # discovery keeps them usable without flattening or copying evidence.
        for evidence_path in sorted(evidence_directory.rglob("*.json")):
            document = json.loads(evidence_path.read_text(encoding="utf-8"))
            pairs = document.get("InterferingBodyPairs") or []
            if not pairs:
                continue
            evidence_files.append(str(evidence_path))
            evidence_pair_count += len(pairs)
            for pair in pairs:
                first = pair.get("FirstComponent") or {}
                second = pair.get("SecondComponent") or {}
                first_name = str(first.get("Name") or "")
                second_name = str(second.get("Name") or "")
                if first_name and second_name:
                    active_leaf_names.update((first_name, second_name))
                    active_leaf_partner_codes.setdefault(first_name, set()).add(
                        component_code(second_name)
                    )
                    active_leaf_partner_codes.setdefault(second_name, set()).add(
                        component_code(first_name)
                    )
                if evidence_layouts is None:
                    continue
                if frozenset((component_code(first_name), component_code(second_name))) in cad_only_pairs:
                    continue
                for side, component, partner in (
                    ("First", first, second),
                    ("Second", second, first),
                ):
                    leaf_name = str(component.get("Name") or "")
                    partner_name = str(partner.get("Name") or "")
                    top_name = leaf_name.split("/", 1)[0]
                    if top_name not in evidence_layouts or top_name not in geometry_layouts:
                        continue
                    world_box = pair.get(f"{side}BoundingBoxWorld")
                    if not isinstance(world_box, list) or len(world_box) != 6:
                        continue
                    projected = {
                        axis: [
                            dot(subtract(point, origin), vector)
                            for point in corners([float(value) for value in world_box])
                        ]
                        for axis, vector in axes.items()
                    }
                    evidence_layout = evidence_layouts[top_name]
                    anchor_u = float(evidence_layout["x"])
                    anchor_v = float(evidence_layout["y"])
                    source_theta = float(geometry_layouts[top_name].get("thetaDegrees", 0.0))
                    evidence_theta = float(evidence_layout.get("thetaDegrees", source_theta))
                    quarters = int(round((evidence_theta - source_theta) / 90.0))
                    local_corners = [
                        rotate_local(u - anchor_u, v - anchor_v, -quarters)
                        for u in (min(projected["u"]), max(projected["u"]))
                        for v in (min(projected["v"]), max(projected["v"]))
                    ]
                    bounds = [
                        min(point[0] for point in local_corners),
                        min(point[1] for point in local_corners),
                        max(point[0] for point in local_corners),
                        max(point[1] for point in local_corners),
                    ]
                    height = [
                        max(0.0, min(projected["n"])),
                        max(1e-6, max(projected["n"])),
                    ]
                    partner_code = component_code(partner_name)
                    key = tuple(round(value, 9) for value in (*bounds, *height)) + (
                        partner_code,
                    )
                    if key in exact_box_keys.setdefault(top_name, set()):
                        continue
                    exact_box_keys[top_name].add(key)
                    exact_boxes_by_component.setdefault(top_name, []).append(
                        {
                            "id": f"{component_code(top_name)}-exact-body-{len(exact_boxes_by_component.get(top_name, []))}",
                            "bounds": bounds,
                            "heightRangeMeters": height,
                            "leafComponent": component.get("HierarchyPath") or leaf_name,
                            "componentCode": component_code(top_name),
                            "collisionPartnerCodes": [partner_code],
                            "occupancyScope": "exact-interfering-body-aabb",
                            "minimumClearanceMeters": 0.0001,
                            "evidenceFile": str(evidence_path),
                        }
                    )

    components: dict[str, Any] = {}
    for name, (capture, capture_path) in captures.items():
        code = component_code(name)
        if code not in STRUCTURAL_CODES:
            continue
        layouts = capture_layouts_by_path[capture_path]
        if name not in layouts:
            raise SystemExit(f"Geometry capture does not contain {name}")
        anchor_u = float(layouts[name]["x"])
        anchor_v = float(layouts[name]["y"])
        boxes: list[dict[str, Any]] = []
        captured_bodies = list(capture.get("Bodies", []))
        base_component = base_components.get(name)
        active_bodies = (
            captured_bodies
            if code in FULL_LEAF_OCCUPANCY_CODES
            else [
                body
                for body in captured_bodies
                if str((body.get("Component") or {}).get("Name") or "") in active_leaf_names
            ]
        )
        if not active_bodies and not base_component:
            raise SystemExit(
                f"No collision-evidence leaf bodies were found for {name}; "
                "refresh the exact B-Rep evidence before solving."
            )
        for index, body in enumerate(active_bodies):
            world_box = [float(value) for value in body["BoundingBoxWorld"]]
            projected = {
                axis: [dot(subtract(point, origin), vector) for point in corners(world_box)]
                for axis, vector in axes.items()
            }
            min_u = min(projected["u"]) - anchor_u
            max_u = max(projected["u"]) - anchor_u
            min_v = min(projected["v"]) - anchor_v
            max_v = max(projected["v"]) - anchor_v
            min_h = max(0.0, min(projected["n"]))
            max_h = max(min_h + 1e-6, max(projected["n"]))
            values = (min_u, min_v, max_u, max_v, min_h, max_h)
            if not all(math.isfinite(value) for value in values):
                raise SystemExit(f"Non-finite occupancy box for {name} body {index}")
            component = body.get("Component") or {}
            boxes.append(
                {
                    "id": f"{code}-active-body-{index}",
                    "bounds": [min_u, min_v, max_u, max_v],
                    "heightRangeMeters": [min_h, max_h],
                    "leafComponent": component.get("HierarchyPath") or component.get("Name"),
                    "componentCode": code,
                    "collisionPartnerCodes": sorted(
                        active_leaf_partner_codes.get(str(component.get("Name") or ""), set())
                    ),
                    "bodyIndex": int(body.get("BodyIndex", 0)),
                }
            )
        merged_by_leaf: dict[str, dict[str, Any]] = {}
        for box in boxes:
            leaf = str(box.get("leafComponent") or box["id"])
            current = merged_by_leaf.get(leaf)
            if current is None:
                merged_by_leaf[leaf] = {
                    **box,
                    "id": f"{code}-active-leaf-{len(merged_by_leaf)}",
                    "bodyIndices": [int(box.get("bodyIndex", 0))],
                }
                continue
            bounds = current["bounds"]
            incoming = box["bounds"]
            current["bounds"] = [
                min(float(bounds[0]), float(incoming[0])),
                min(float(bounds[1]), float(incoming[1])),
                max(float(bounds[2]), float(incoming[2])),
                max(float(bounds[3]), float(incoming[3])),
            ]
            height = current["heightRangeMeters"]
            incoming_height = box["heightRangeMeters"]
            current["heightRangeMeters"] = [
                min(float(height[0]), float(incoming_height[0])),
                max(float(height[1]), float(incoming_height[1])),
            ]
            current["bodyIndices"].append(int(box.get("bodyIndex", 0)))
            current["collisionPartnerCodes"] = sorted(
                set(current.get("collisionPartnerCodes") or [])
                | set(box.get("collisionPartnerCodes") or [])
            )
        exact_boxes = exact_boxes_by_component.get(name)
        incremental_exact_box_count = len(exact_boxes or [])
        if base_component:
            boxes = copy.deepcopy(base_component.get("boxes") or [])
            existing_keys = {
                tuple(round(float(value), 9) for value in (*box["bounds"], *box["heightRangeMeters"]))
                + tuple(sorted(str(value) for value in box.get("collisionPartnerCodes") or []))
                for box in boxes
            }
            for box in exact_boxes or []:
                key = tuple(
                    round(float(value), 9)
                    for value in (*box["bounds"], *box["heightRangeMeters"])
                ) + tuple(
                    sorted(str(value) for value in box.get("collisionPartnerCodes") or [])
                )
                if key not in existing_keys:
                    boxes.append(box)
                    existing_keys.add(key)
            incremental_exact_box_count = len(boxes) - len(base_component.get("boxes") or [])
            exact_interfering_body_box_count = int(
                base_component.get("exactInterferingBodyBoxCount", 0)
            ) + incremental_exact_box_count
            active_merge_mode = "base-occupancy-plus-exact-interfering-body-aabb"
        elif exact_boxes:
            exact_interfering_body_box_count = len(exact_boxes)
            # Copy before appending pair-scoped structural coverage so the
            # evidence-only count remains stable in the output metadata.
            boxes = list(exact_boxes)
            active_merge_mode = "exact-interfering-body-aabb"
        elif code in PRESERVE_BODY_BOX_CODES:
            boxes = boxes
            active_merge_mode = "preserve-body-aabb"
        else:
            exact_interfering_body_box_count = 0
            boxes = list(merged_by_leaf.values())
            active_merge_mode = "union-by-leaf-component"
        full_pair_partners = FULL_SUBASSEMBLY_PAIR_PARTNERS.get(code, ())
        full_subassembly_box_count = 0
        if full_pair_partners:
            grouped: dict[str, dict[str, Any]] = {}
            for body in captured_bodies:
                component = body.get("Component") or {}
                leaf_name = str(component.get("Name") or "")
                name_parts = [part for part in leaf_name.split("/") if part]
                group_name = name_parts[1] if len(name_parts) >= 3 else name_parts[-1]
                world_box = [float(value) for value in body["BoundingBoxWorld"]]
                projected = {
                    axis: [
                        dot(subtract(point, origin), vector)
                        for point in corners(world_box)
                    ]
                    for axis, vector in axes.items()
                }
                incoming_bounds = [
                    min(projected["u"]) - anchor_u,
                    min(projected["v"]) - anchor_v,
                    max(projected["u"]) - anchor_u,
                    max(projected["v"]) - anchor_v,
                ]
                incoming_height = [
                    max(0.0, min(projected["n"])),
                    max(1e-6, max(projected["n"])),
                ]
                current = grouped.get(group_name)
                if current is None:
                    grouped[group_name] = {
                        "id": f"{code}-full-subassembly-{len(grouped)}",
                        "bounds": incoming_bounds,
                        "heightRangeMeters": incoming_height,
                        "leafComponent": group_name,
                        "componentCode": code,
                        "collisionPartnerCodes": list(full_pair_partners),
                        "occupancyScope": "full-major-subassembly-union",
                        "minimumClearanceMeters": 0.01,
                    }
                    continue
                current_bounds = current["bounds"]
                current_height = current["heightRangeMeters"]
                current["bounds"] = [
                    min(current_bounds[0], incoming_bounds[0]),
                    min(current_bounds[1], incoming_bounds[1]),
                    max(current_bounds[2], incoming_bounds[2]),
                    max(current_bounds[3], incoming_bounds[3]),
                ]
                current["heightRangeMeters"] = [
                    min(current_height[0], incoming_height[0]),
                    max(current_height[1], incoming_height[1]),
                ]
            boxes.extend(grouped.values())
            full_subassembly_box_count = len(grouped)
        component_full_leaf_partners = full_leaf_pair_partners.get(code, ())
        full_leaf_pair_boxes: dict[str, dict[str, Any]] = {}
        if component_full_leaf_partners:
            for body in captured_bodies:
                component = body.get("Component") or {}
                leaf_name = str(
                    component.get("Name")
                    or component.get("HierarchyPath")
                    or f"body-{len(full_leaf_pair_boxes)}"
                )
                world_box = [float(value) for value in body["BoundingBoxWorld"]]
                projected = {
                    axis: [
                        dot(subtract(point, origin), vector)
                        for point in corners(world_box)
                    ]
                    for axis, vector in axes.items()
                }
                incoming_bounds = [
                    min(projected["u"]) - anchor_u,
                    min(projected["v"]) - anchor_v,
                    max(projected["u"]) - anchor_u,
                    max(projected["v"]) - anchor_v,
                ]
                incoming_height = [
                    max(0.0, min(projected["n"])),
                    max(1e-6, max(projected["n"])),
                ]
                current = full_leaf_pair_boxes.get(leaf_name)
                if current is None:
                    full_leaf_pair_boxes[leaf_name] = {
                        "id": f"{code}-full-leaf-{len(full_leaf_pair_boxes)}",
                        "bounds": incoming_bounds,
                        "heightRangeMeters": incoming_height,
                        "leafComponent": leaf_name,
                        "componentCode": code,
                        "collisionPartnerCodes": list(component_full_leaf_partners),
                        "occupancyScope": "full-leaf-instance-union",
                        "minimumClearanceMeters": 0.0001,
                    }
                    continue
                current_bounds = current["bounds"]
                current_height = current["heightRangeMeters"]
                current["bounds"] = [
                    min(current_bounds[0], incoming_bounds[0]),
                    min(current_bounds[1], incoming_bounds[1]),
                    max(current_bounds[2], incoming_bounds[2]),
                    max(current_bounds[3], incoming_bounds[3]),
                ]
                current["heightRangeMeters"] = [
                    min(current_height[0], incoming_height[0]),
                    max(current_height[1], incoming_height[1]),
                ]
            boxes.extend(full_leaf_pair_boxes.values())
        components[name] = {
            "code": code,
            "hardClearance": True,
            "source": str(capture_path),
            "anchorSource": str(
                next(
                    (
                        str(layout_path)
                        for extra_capture, layout_path in zip(extra_captures, extra_layout_paths)
                        if capture_path == extra_capture
                    ),
                    str(
                        args.capture_layout.resolve()
                        if capture_path == args.capture.resolve()
                        else args.geometry.resolve()
                    ),
                )
            ),
            "boxCount": len(boxes),
            "capturedBodyCount": len(captured_bodies),
            "activeBodyCountBeforeLeafMerge": len(active_bodies),
            "exactInterferingBodyBoxCount": exact_interfering_body_box_count,
            "incrementalExactInterferingBodyBoxCount": incremental_exact_box_count,
            "boxMergeMode": active_merge_mode,
            "fullSubassemblyPairBoxCount": full_subassembly_box_count,
            "fullLeafPairBoxCount": len(full_leaf_pair_boxes),
            "boxes": boxes,
        }

    # A base model may contain components captured from additional historical
    # assemblies (for Project 02 this includes A300 and T401). Preserve those
    # unchanged when the incremental evidence does not mention them.
    for name, base_component in base_components.items():
        if name in components:
            continue
        components[name] = copy.deepcopy(base_component)
        components[name]["incrementalExactInterferingBodyBoxCount"] = 0
        components[name]["baseOccupancySource"] = str(base_occupancy_path)

    missing = sorted(set(STRUCTURAL_CODES) - {item["code"] for item in components.values()})
    if missing:
        raise SystemExit(f"Missing structural captures: {', '.join(missing)}")
    output = {
        "schemaVersion": 1,
        "coordinateFrame": "component bottom-centre local U/V plus Common Base normal height",
        "conservative": True,
        "occupancyMode": "collision-derived-active-structural-obstacles",
        "baseOccupancyPath": str(base_occupancy_path) if base_occupancy_path else None,
        "evidenceDirectories": [
            *((base_occupancy or {}).get("evidenceDirectories") or []),
            *(str(path) for path in evidence_directories),
        ],
        "evidenceLayouts": [
            *((base_occupancy or {}).get("evidenceLayouts") or []),
            *(str(path) for path in evidence_layout_paths),
        ],
        "cadOnlyPairs": sorted(
            {
                tuple(pair)
                for pair in [
                    *((base_occupancy or {}).get("cadOnlyPairs") or []),
                    *(sorted(pair) for pair in cad_only_pairs),
                ]
            }
        ),
        "fullLeafPairs": sorted(
            {
                tuple(pair)
                for pair in [
                    *((base_occupancy or {}).get("fullLeafPairs") or []),
                    *(sorted(pair) for pair in full_leaf_pairs),
                ]
            }
        ),
        "evidenceFiles": [
            *((base_occupancy or {}).get("evidenceFiles") or []),
            *evidence_files,
        ],
        "evidenceInterferingBodyPairCount": int(
            (base_occupancy or {}).get("evidenceInterferingBodyPairCount", 0)
        )
        + evidence_pair_count,
        "components": components,
    }
    args.output.resolve().write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(args.output.resolve()),
                "boxCounts": {name: item["boxCount"] for name, item in components.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

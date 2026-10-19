from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v2.json"
DEFAULT_OPERATION = ROOT / "demo/layout_previews/project02_a600_operation_face.json"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_a600_installation_frame.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Project02 A600 engineering installation frame from mate endpoints."
    )
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--operation-face", type=Path, default=DEFAULT_OPERATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    graph = json.loads(args.graph.resolve().read_text(encoding="utf-8"))
    operation = json.loads(args.operation_face.resolve().read_text(encoding="utf-8"))
    mates = _pick(graph, "Mates", []) or []

    contact = _unique_mate(mates, "重合35", {"A600", "A800"})
    width = _unique_mate(mates, "宽度9", {"A600", "A800"})
    top = _unique_endpoint(contact, "A600")
    width_faces = [
        item for item in (_pick(width, "Endpoints", []) or [])
        if _pick(item, "ModuleToken") == "A600"
    ]
    if len(width_faces) != 2:
        raise SystemExit(f"宽度9 must expose exactly two A600 endpoints; found {len(width_faces)}")

    top_center = _vector(top, "FaceCenterWorld")
    top_normal_raw = _unit(_vector(top, "FaceNormalWorld"))
    operation_probe = operation.get("selectedFaceProbe") or {}
    operation_center = _vector(operation_probe, "WorldCenter")
    operation_outward = _unit(_vector(operation_probe, "WorldNormal"))
    width_centers = [_vector(item, "FaceCenterWorld") for item in width_faces]
    width_midpoint = _scale(_add(width_centers[0], width_centers[1]), 0.5)
    width_span = _subtract(width_centers[0], width_centers[1])

    # The face sense of imported sheet/foreign topology may point into the cabinet.
    # Choose +Z/up using the direction from the operation-face center toward the
    # transport support plane; this is an engineering semantic, not a face-sense guess.
    toward_support = _subtract(top_center, operation_center)
    up = top_normal_raw if _dot(top_normal_raw, toward_support) >= 0 else _scale(top_normal_raw, -1.0)
    into_machine = _scale(operation_outward, -1.0)
    into_machine = _unit(_reject(into_machine, up))
    lateral = _unit(_cross(up, into_machine))

    origin = _three_plane_intersection(
        (operation_outward, operation_center),
        (up, top_center),
        (lateral, width_midpoint),
    )
    width_separation = _length(width_span)
    orthogonality = {
        "xDotY": _dot(into_machine, lateral),
        "xDotZ": _dot(into_machine, up),
        "yDotZ": _dot(lateral, up),
        "rightHandedResidual": _length(_subtract(_cross(into_machine, lateral), up)),
    }
    plane_residuals = {
        "operationFace": abs(_dot(operation_outward, _subtract(origin, operation_center))),
        "supportSurface": abs(_dot(up, _subtract(origin, top_center))),
        "transportCenterPlane": abs(_dot(lateral, _subtract(origin, width_midpoint))),
    }

    checks = [
        _check("mate-graph-v1.2-or-newer", str(_pick(graph, "SchemaVersion", "")).endswith("v1.2")),
        _check("operation-face-engineer-confirmed", operation.get("engineerConfirmed") is True),
        _check("a600-a800-contact-face-large", float(_pick(top, "FaceArea", 0.0)) > 0.5),
        _check("support-and-operation-planes-orthogonal", abs(_dot(up, operation_outward)) < 1e-6),
        _check("width-reference-span-positive", width_separation > 0.5),
        _check("frame-right-handed", orthogonality["rightHandedResidual"] < 1e-6),
        _check("three-plane-origin-valid", max(plane_residuals.values()) < 1e-6),
    ]
    success = all(item["passed"] for item in checks)
    result = {
        "schemaVersion": "project02-a600-installation-frame/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": "PASS_A600_INSTALLATION_FRAME" if success else "FAIL_A600_INSTALLATION_FRAME",
        "sourceMateGraph": str(args.graph.resolve()),
        "sourceOperationFace": str(args.operation_face.resolve()),
        "moduleCode": "A600",
        "frameName": "A600_INSTALLATION_FRAME",
        "originDefinition": "intersection(operation face, A800 support surface, A600-A800 width center plane)",
        "originWorldMeters": origin,
        "axesWorld": {
            "xIntoMachine": into_machine,
            "yTransportLateral": lateral,
            "zUp": up,
            "operationOutward": operation_outward,
        },
        "referencePlanes": {
            "operationFace": {
                "pointWorldMeters": operation_center,
                "normalWorld": operation_outward,
                "source": "engineer-confirmed persistent face mapping",
            },
            "transportSupportSurface": {
                "pointWorldMeters": top_center,
                "rawFaceNormalWorld": top_normal_raw,
                "engineeringUpNormalWorld": up,
                "mateName": _pick(contact, "MateName"),
                "mateType": _pick(contact, "MateTypeName"),
                "alignment": _pick(contact, "AlignmentName"),
                "a600Endpoint": top,
            },
            "transportCenterPlane": {
                "pointWorldMeters": width_midpoint,
                "normalWorld": lateral,
                "referenceFaceCentersWorldMeters": width_centers,
                "referenceFaceSeparationMeters": width_separation,
                "mateName": _pick(width, "MateName"),
                "mateType": _pick(width, "MateTypeName"),
                "note": "The two A600 endpoint centers define the width mid-plane; imported face normals are not used.",
            },
        },
        "orthogonality": orthogonality,
        "originPlaneResidualsMeters": plane_residuals,
        "checks": checks,
        "interpretation": {
            "bottomFaceRequiredForUpperModuleLayout": False,
            "bottomFaceOptionalUses": ["overall machine height", "floor clearance", "cabinet envelope"],
            "solverFrameUse": "Place A800 from vendor XYZ in this frame, then A180/service modules, and place A100 last by reachability.",
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output)}, ensure_ascii=False))
    return 0 if success else 2


def _pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def _unique_mate(mates: list[dict[str, Any]], name: str, tokens: set[str]) -> dict[str, Any]:
    matches = [
        item for item in mates
        if str(_pick(item, "MateName", "")) == name
        and set(_pick(item, "ModuleTokens", []) or []) == tokens
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one mate {name} for {sorted(tokens)}; found {len(matches)}")
    return matches[0]


def _unique_endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [item for item in (_pick(mate, "Endpoints", []) or []) if _pick(item, "ModuleToken") == token]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {token} endpoint in {_pick(mate, 'MateName')}; found {len(matches)}")
    return matches[0]


def _vector(item: dict[str, Any], name: str) -> list[float]:
    value = _pick(item, name)
    if not isinstance(value, list) or len(value) != 3:
        raise SystemExit(f"Missing three-value {name}: {value!r}")
    return [float(number) for number in value]


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed)}


def _add(a: list[float], b: list[float]) -> list[float]:
    return [a[i] + b[i] for i in range(3)]


def _subtract(a: list[float], b: list[float]) -> list[float]:
    return [a[i] - b[i] for i in range(3)]


def _scale(a: list[float], factor: float) -> list[float]:
    return [value * factor for value in a]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(a[i] * b[i] for i in range(3))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _length(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: list[float]) -> list[float]:
    length = _length(a)
    if length < 1e-9:
        raise SystemExit(f"Cannot normalize near-zero vector: {a}")
    return [value / length for value in a]


def _reject(vector: list[float], normal: list[float]) -> list[float]:
    return _subtract(vector, _scale(normal, _dot(vector, normal)))


def _three_plane_intersection(
    first: tuple[list[float], list[float]],
    second: tuple[list[float], list[float]],
    third: tuple[list[float], list[float]],
) -> list[float]:
    normals = [first[0], second[0], third[0]]
    rhs = [_dot(first[0], first[1]), _dot(second[0], second[1]), _dot(third[0], third[1])]
    det = _dot(normals[0], _cross(normals[1], normals[2]))
    if abs(det) < 1e-9:
        raise SystemExit("Reference planes do not define a unique origin.")
    return _scale(
        _add(
            _add(_scale(_cross(normals[1], normals[2]), rhs[0]), _scale(_cross(normals[2], normals[0]), rhs[1])),
            _scale(_cross(normals[0], normals[1]), rhs[2]),
        ),
        1.0 / det,
    )


if __name__ == "__main__":
    raise SystemExit(main())

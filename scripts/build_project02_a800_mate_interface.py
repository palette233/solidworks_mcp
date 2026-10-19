from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v2.json"
DEFAULT_FRAME = ROOT / "demo/layout_previews/project02_a600_installation_frame.json"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_a600_a800_mate_interface.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover the Project02 A600-A800 installation interface from mate faces."
    )
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    graph = _load(args.graph)
    frame = _load(args.frame)
    mates = graph.get("Mates") or []
    contact = _unique_mate(mates, "重合35", {"A600", "A800"})
    width = _unique_mate(mates, "宽度9", {"A600", "A800"})
    contact_a600 = _endpoints(contact, "A600")
    contact_a800 = _endpoints(contact, "A800")
    width_a600 = _endpoints(width, "A600")
    width_a800 = _endpoints(width, "A800")
    if len(contact_a600) != 1 or len(contact_a800) != 1:
        raise SystemExit("重合35 must contain one A600 face and one A800 face.")
    if len(width_a600) != 2 or len(width_a800) != 2:
        raise SystemExit("宽度9 must contain two A600 faces and two A800 faces.")

    origin = _numbers(frame, "originWorldMeters", 3)
    frame_axes = frame["axesWorld"]
    axes = [
        _numbers(frame_axes, "xIntoMachine", 3),
        _numbers(frame_axes, "yTransportLateral", 3),
        _numbers(frame_axes, "zUp", 3),
    ]
    contact_a600_frame = _point_to_frame(_face_center(contact_a600[0]), origin, axes)
    contact_a800_frame = _point_to_frame(_face_center(contact_a800[0]), origin, axes)
    width_a600_frame = [_point_to_frame(_face_center(item), origin, axes) for item in width_a600]
    width_a800_frame = [_point_to_frame(_face_center(item), origin, axes) for item in width_a800]
    width_a600_mid = _midpoint(width_a600_frame)
    width_a800_mid = _midpoint(width_a800_frame)

    # Coincident35 fixes the support height (Z) and Width9 fixes the transport
    # lateral centre (Y).  Neither mate fixes translation along the transport
    # longitudinal/into-machine axis (X).  We therefore retain the X station of
    # the selected A800 width-tab features as a measured prototype seed, while
    # keeping its status distinct from a vendor-confirmed dimension.
    mate_feature_datum = [width_a800_mid[0], 0.0, 0.0]
    checks = [
        _check("a600-installation-frame-valid", frame.get("success") is True),
        _check("a600-a800-contact-mate-present", contact.get("MateTypeName") == "swMateCOINCIDENT"),
        _check("a600-a800-width-mate-present", width.get("MateTypeName") == "swMateWIDTH"),
        _check("contact-a800-on-support-plane", abs(contact_a800_frame[2]) < 1e-6, contact_a800_frame[2]),
        _check("width-a600-centred-on-frame", abs(width_a600_mid[1]) < 1e-6, width_a600_mid[1]),
        _check("width-a800-centred-on-frame", abs(width_a800_mid[1]) < 1e-6, width_a800_mid[1]),
        _check("prototype-x-station-inside-a600", 0.0 <= mate_feature_datum[0] <= 1.6405, mate_feature_datum[0]),
    ]
    success = all(item["passed"] for item in checks)
    result = {
        "schemaVersion": "project02-a600-a800-mate-interface/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": "PASS_MATE_DERIVED_PARTIAL_INTERFACE" if success else "FAIL_MATE_DERIVED_INTERFACE",
        "baseModuleCode": "A600",
        "transportModuleCode": "A800",
        "frameName": frame.get("frameName"),
        "sourceMateGraph": str(args.graph.resolve()),
        "sourceFrame": str(args.frame.resolve()),
        "mateBundle": {
            "mateNames": [contact.get("MateName"), width.get("MateName")],
            "mateTypes": [contact.get("MateTypeName"), width.get("MateTypeName")],
            "contactAlignment": contact.get("AlignmentName"),
            "widthAlignment": width.get("AlignmentName"),
            "persistentFaceReferenceCount": sum(
                bool(item.get("SourceAssemblyPersistentReferenceBase64"))
                for item in [*contact_a600, *contact_a800, *width_a600, *width_a800]
            ),
        },
        "constraintInterpretation": {
            "fixedTranslationAxes": ["Y", "Z"],
            "freeTranslationAxes": ["X"],
            "orientationFullyConstrained": True,
            "remainingDegreeOfFreedom": "translation along A600 X / transport longitudinal axis",
            "reason": (
                "重合35 fixes the A800 mounting/support plane; 宽度9 centres A800 between the two "
                "A600 width faces and fixes the remaining in-plane orientation. No exported A600-A800 "
                "distance/end-face mate fixes the longitudinal X station."
            ),
        },
        "measuredMateFeaturesFrameMeters": {
            "contactFaceCenterA600": contact_a600_frame,
            "contactFaceCenterA800": contact_a800_frame,
            "widthFaceCentersA600": width_a600_frame,
            "widthFaceCentersA800": width_a800_frame,
            "widthMidpointA600": width_a600_mid,
            "widthTabMidpointA800": width_a800_mid,
        },
        "mateDerivedInstallationDatumFrameMeters": mate_feature_datum,
        "datumDefinition": (
            "Project the prototype A800 Width9 tab-face midpoint onto the A600 support plane and "
            "transport centre plane. Y=0 and Z=0 are mate-constrained; X is prototype-measured."
        ),
        "axisConfidence": {
            "xIntoMachine": "medium-prototype-feature-station-not-mate-constrained",
            "yTransportLateral": "high-width9-mate-constrained",
            "zUp": "high-coincident35-mate-constrained",
            "orientation": "high-coincident35-plus-width9-mate-constrained",
        },
        "usableAsMateDerivedCoarseInterface": success,
        "confirmedAsVendorInterface": False,
        "remainingRequiredConfirmation": (
            "Confirm the A800 longitudinal X locating dimension or its vendor end-face/dowel-hole datum."
        ),
        "checks": checks,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "mateDerivedInstallationDatumFrameMeters": mate_feature_datum,
                "freeTranslationAxes": ["X"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if success else 2


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


def _unique_mate(mates: list[dict[str, Any]], name: str, tokens: set[str]) -> dict[str, Any]:
    matches = [
        item
        for item in mates
        if item.get("MateName") == name and set(item.get("ModuleTokens") or []) == tokens
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {name} mate for {sorted(tokens)}; found {len(matches)}")
    return matches[0]


def _endpoints(mate: dict[str, Any], token: str) -> list[dict[str, Any]]:
    return [item for item in mate.get("Endpoints") or [] if item.get("ModuleToken") == token]


def _face_center(endpoint: dict[str, Any]) -> list[float]:
    return _numbers(endpoint, "FaceCenterWorld", 3)


def _numbers(item: dict[str, Any], name: str, length: int) -> list[float]:
    value = item.get(name)
    if not isinstance(value, list) or len(value) != length:
        raise SystemExit(f"Missing {length}-value {name}: {value!r}")
    return [float(number) for number in value]


def _point_to_frame(point: list[float], origin: list[float], axes: list[list[float]]) -> list[float]:
    delta = [point[index] - origin[index] for index in range(3)]
    return [_dot(delta, axis) for axis in axes]


def _midpoint(points: list[list[float]]) -> list[float]:
    if len(points) != 2:
        raise SystemExit(f"Expected two points; found {len(points)}")
    return [(points[0][index] + points[1][index]) / 2.0 for index in range(3)]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _check(name: str, passed: bool, actual: float | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if actual is not None:
        result["actual"] = actual
    return result


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = ROOT / "demo/FL9A24D062A000_real_process_request.json"
PREVIEW_PATH = ROOT / "demo/layout_previews/project02_preview.json"
SERVICE_AUDIT_PATH = ROOT / "demo/layout_previews/project02_service_access_audit.json"
OUTPUT_PATH = ROOT / "demo/layout_previews/project02_a700_functional_split.json"
A700 = "FL9A24D062A700.001-1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def close(first: float, second: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(float(first), float(second), abs_tol=tolerance)


def center(bounds: list[float]) -> dict[str, float]:
    return {
        "u": (float(bounds[0]) + float(bounds[2])) / 2.0,
        "v": (float(bounds[1]) + float(bounds[3])) / 2.0,
    }


def union_center(boxes: list[dict[str, Any]]) -> dict[str, float]:
    return center(
        [
            min(float(box["bounds"][0]) for box in boxes),
            min(float(box["bounds"][1]) for box in boxes),
            max(float(box["bounds"][2]) for box in boxes),
            max(float(box["bounds"][3]) for box in boxes),
        ]
    )


def same_point(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return close(first["u"], second["u"]) and close(first["v"], second["v"])


def main() -> int:
    request = load(REQUEST_PATH)
    preview = load(PREVIEW_PATH)
    service_audit = load(SERVICE_AUDIT_PATH)
    semantic = request["moduleSemantics"][A700]
    points = semantic["points"]
    parameters = semantic["parameters"]
    occupancies = {
        item["id"]: item for item in parameters.get("occupancyBoxesLocal") or []
    }
    protected = {
        item["id"]: item
        for item in parameters.get("protectedSpaceBoxesLocal") or []
    }
    cleaning_boxes = [occupancies["cleaning-a710"], occupancies["cleaning-a720"]]
    cleaning_center = union_center(cleaning_boxes)
    weighing_center = center(occupancies["weighing-a730"]["bounds"])
    constraints = {
        item.get("id"): item for item in request.get("processConstraints") or []
    }
    diagnostics = {item.get("id"): item for item in preview.get("diagnostics") or []}
    a700_service_row = next(
        (
            row
            for row in service_audit.get("modules") or []
            if row.get("componentName") == A700
        ),
        {},
    )

    cleaning_vertical = protected.get("cleaning-vertical-service-approach") or {}
    cleaning_access = protected.get("cleaning-operator-access") or {}
    weighing_vertical = protected.get("weighing-vertical-service-approach") or {}
    weighing_access = protected.get("weighing-operator-access") or {}
    function_names = parameters.get("functionalServicePointNames") or {}
    checks = {
        "a710A720A730OccupanciesPresent": all(
            name in occupancies
            for name in ("cleaning-a710", "cleaning-a720", "weighing-a730")
        ),
        "cleaningPointDerivedFromA710A720Union": same_point(
            points["cleaningServicePoint"], cleaning_center
        ),
        "weighingPointDerivedFromA730Center": same_point(
            points["weighingServicePoint"], weighing_center
        ),
        "legacyServicePointAliasesCleaning": same_point(
            points["servicePoint"], points["cleaningServicePoint"]
        ),
        "functionPointNamesDeclared": function_names
        == {
            "cleaning": "cleaningServicePoint",
            "weighing": "weighingServicePoint",
        },
        "weighingConstraintUsesWeighingPoint": (
            constraints.get("coarse-a700-weighing-reach") or {}
        ).get("point")
        == "weighingServicePoint",
        "cleaningReachPassed": diagnostics.get(
            "auto-cleaning-reach-FL9A24D062A700.001-1-dualValveReach", {}
        ).get("success")
        is True,
        "weighingReachPassed": diagnostics.get(
            "coarse-a700-weighing-reach", {}
        ).get("success")
        is True,
        "cleaningVerticalSpaceCentered": same_point(
            center(cleaning_vertical["bounds"]), points["cleaningServicePoint"]
        ),
        "weighingVerticalSpaceCentered": same_point(
            center(weighing_vertical["bounds"]), points["weighingServicePoint"]
        ),
        "cleaningAccessUsesNegativeVDirection": close(
            center(cleaning_access["bounds"])["u"], points["cleaningServicePoint"]["u"]
        )
        and center(cleaning_access["bounds"])["v"]
        < points["cleaningServicePoint"]["v"],
        "weighingAccessUsesNegativeVDirection": close(
            center(weighing_access["bounds"])["u"], points["weighingServicePoint"]["u"]
        )
        and center(weighing_access["bounds"])["v"]
        < points["weighingServicePoint"]["v"],
        "fourPurposeSpecificProtectedSpacesPass": a700_service_row.get(
            "protectedSpaceCount"
        )
        == 4
        and a700_service_row.get("passed") is True,
        "prototypeAuthorityPreserved": parameters.get(
            "functionalServicePointsAuthority"
        )
        == "prototypeBaselineAcceptedForCoarseLayout"
        and parameters.get("functionalServicePointsPrototypeDerived") is True,
    }
    success = bool(preview.get("metrics", {}).get("hardFeasible")) and all(
        checks.values()
    )
    report = {
        "schemaVersion": "project02-a700-functional-split/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": (
            "A700_CLEANING_WEIGHING_FUNCTIONS_SPLIT_FOR_COARSE_LAYOUT"
            if success
            else "A700_FUNCTIONAL_SPLIT_FAILED"
        ),
        "authority": "prototypeBaselineAcceptedForCoarseLayout",
        "vendorConfirmed": False,
        "scope": "project02-only",
        "rigidPlacementUnit": "A700 remains one rigid top-level module",
        "functions": {
            "cleaning": {
                "sourceSubassemblies": ["A710", "A720"],
                "sourceOccupancyIds": ["cleaning-a710", "cleaning-a720"],
                "derivedServicePointLocalMeters": cleaning_center,
                "pointName": "cleaningServicePoint",
                "protectedSpaceIds": [
                    "cleaning-vertical-service-approach",
                    "cleaning-operator-access",
                ],
            },
            "weighing": {
                "sourceSubassemblies": ["A730"],
                "sourceOccupancyIds": ["weighing-a730"],
                "derivedServicePointLocalMeters": weighing_center,
                "pointName": "weighingServicePoint",
                "protectedSpaceIds": [
                    "weighing-vertical-service-approach",
                    "weighing-operator-access",
                ],
            },
        },
        "checks": checks,
        "totalServiceAccessConstraintCount": service_audit.get(
            "protectedSpaceConstraintCount"
        ),
        "limitations": [
            "Service points are occupancy-center baselines, not measured nozzle/cup contact points.",
            "A700 remains one rigid solved module; A710/A720/A730 are not independently placed.",
            "Actual roll replacement, cleaning consumable and weighing-cup maintenance sweeps remain unverified.",
        ],
        "sourceFiles": {
            "request": str(REQUEST_PATH),
            "preview": str(PREVIEW_PATH),
            "serviceAccessAudit": str(SERVICE_AUDIT_PATH),
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

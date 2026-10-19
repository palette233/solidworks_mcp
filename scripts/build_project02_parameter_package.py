#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "demo/project02_engineering_inputs.json"
REQUEST_PATH = ROOT / "demo/FL9A24D062A000_real_process_request.json"
OUTPUT_PATH = ROOT / "demo/project02_parameter_package.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def evidence(relative_path: str) -> tuple[Path, dict[str, Any]]:
    path = ROOT / relative_path
    return path, load(path)


def main() -> int:
    inputs = load(INPUT_PATH)
    request = load(REQUEST_PATH)
    scan_path, scan = evidence(
        "demo/layout_previews/project02_dynamic_scan_prototype_baseline_acceptance.json"
    )
    valve_path, valve = evidence(
        "demo/layout_previews/project02_a100_prototype_baseline_acceptance.json"
    )
    service_path, service = evidence(
        "demo/layout_previews/project02_service_access_audit.json"
    )
    a700_path, a700 = evidence(
        "demo/layout_previews/project02_a700_functional_split.json"
    )
    closure_path, closure = evidence(
        "demo/layout_previews/project02_v22_incremental_brep_closure.json"
    )
    verification_path, verification = evidence(
        "demo/layout_previews/project02_verification_plan.json"
    )

    baseline_sections = {
        key: inputs[key]
        for key in (
            "transportInstallation",
            "dynamicScan",
            "dualValveReach",
            "serviceAccess",
        )
    }
    checks = {
        "allSectionsAreProject02PrototypeBaselines": all(
            section.get("sourceType") == "prototypeBaseline"
            and section.get("acceptedForCoarseLayout") is True
            and section.get("vendorConfirmed") is False
            and section.get("scope") == "project02-only"
            for section in baseline_sections.values()
        ),
        "dynamicScanEvidencePassed": scan.get("success") is True,
        "dualValveEvidencePassed": valve.get("success") is True,
        "serviceAccessEvidencePassed": service.get("success") is True,
        "a700FunctionalSplitPassed": a700.get("success") is True,
        "cadPolicyClosurePassed": closure.get("policyClosurePassed") is True
        and int(closure.get("unacceptedFailureCount", -1)) == 0,
        "literalZeroInterferenceNotMisreported": closure.get(
            "literalZeroInterference"
        )
        is False
        and int(closure.get("acceptedPrototypeBaselinePairCount", 0)) == 1,
        "closureAssemblyExists": Path(
            str(closure.get("currentAssemblyPath") or "")
        ).is_file(),
        "verificationPlanStillRecordsSelectedCandidate": verification.get("status")
        == "visual_review_approved",
        "productionReadyRemainsFalse": True,
    }
    success = all(checks.values())
    package = {
        "schemaVersion": "project02-coarse-layout-parameter-package/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectId": "project02",
        "success": success,
        "status": (
            "PROJECT02_COARSE_LAYOUT_PARAMETER_PACKAGE_READY"
            if success
            else "PROJECT02_PARAMETER_PACKAGE_INCOMPLETE"
        ),
        "productionReady": False,
        "top3SolveReady": success,
        "checks": checks,
        "portableRuleTemplates": [
            {
                "id": "base-transport-scanner-service-gantry-order",
                "rule": "A600 base -> A800 transport -> A180 scanner -> service modules -> A100 gantry",
            },
            {
                "id": "evidence-authority-tier",
                "rule": "prototypeBaseline is project-scoped and replaceable; vendorConfirmed is authoritative input",
            },
            {
                "id": "dynamic-scan-two-endpoints",
                "rule": "Both stop-window endpoints must pass working distance, line of sight and directed pointing",
            },
            {
                "id": "multi-function-rigid-module",
                "rule": "One rigid top-level module may expose separate function-specific occupancy, service points and maintenance spaces",
            },
            {
                "id": "staged-static-collision",
                "rule": "Strict inflated AABB for ordinary pairs; conditional B-rep only for structural/nested pairs or incomplete occupancy evidence",
            },
            {
                "id": "cad-validation-routing",
                "rule": "Reuse closed CAD evidence only when rigid poses, source CAD and approval binding are equivalent",
            },
        ],
        "projectSpecificParameters": baseline_sections,
        "requiredEvidence": [
            {
                "id": "moduleIdentity",
                "status": "available",
                "authority": "ppt-cad-confirmed",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "moduleCadPaths",
                "status": "available",
                "authority": "filesystem",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "baseOperationFace",
                "status": "available",
                "authority": "selected-face-and-prototype-baseline",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "baseTopInstallationSurface",
                "status": "available",
                "authority": "mate-derived-cad-frame",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "transportInstallationFrame",
                "status": "available",
                "authority": "prototype-calibrated-mate-interface",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "transportWorkPositions",
                "status": "available",
                "authority": "ppt-cad-inferred",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "barcodeFaceAndSide",
                "status": "available",
                "authority": "prototype-calibrated-optical-baseline",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "scannerWorkingDistanceAndAxis",
                "status": "available",
                "authority": "prototype-calibrated-not-vendor-confirmed",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "ccdWorkingGeometry",
                "status": "available",
                "authority": "ppt-prototype-estimate",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "dualValveReach",
                "status": "available",
                "authority": "prototype-calibrated-not-vendor-confirmed",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "serviceFunctionPoints",
                "status": "available",
                "authority": "ppt-cad-inferred",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "operationSideCapacity",
                "status": "available",
                "authority": "prototype-calibrated-maintenance-estimate",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "moduleOccupancy",
                "status": "available",
                "authority": "cad-leaf-aabb-plus-brep-feedback-v42",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "staticCollisionPolicy",
                "status": "available",
                "authority": "pair-complete-policy-and-v22-closure",
                "coarseLayoutRequired": True,
                "coarseLayoutUsable": True,
            },
            {
                "id": "allowedContactsAndSafeStates",
                "status": "partial",
                "authority": "prototype-baseline-awaiting-engineering-confirmation",
                "coarseLayoutRequired": False,
                "coarseLayoutUsable": True,
            },
            {
                "id": "glueSupplyFunctionalInterface",
                "status": "missing",
                "authority": "not-captured",
                "coarseLayoutRequired": False,
                "coarseLayoutUsable": False,
            },
            {
                "id": "secondGlueSupplyInstance",
                "status": "missing",
                "authority": "excluded-from-current-nine-object-scope",
                "coarseLayoutRequired": False,
                "coarseLayoutUsable": False,
            },
        ],
        "derivedModuleSemantics": {
            "A700": {
                "rigidPlacementUnit": "FL9A24D062A700.001-1",
                "functions": a700.get("functions"),
                "serviceAccessConstraintCount": service.get(
                    "protectedSpaceConstraintCount"
                ),
            }
        },
        "doNotCopyAsUniversalConstants": [
            "A800 installation-frame XYZ values",
            "5 mm dynamic scan stop baseline",
            "A100 left/right/common reach numeric bounds and 90 mm head spacing",
            "A500/A700/A300 protected-space dimensions",
            "A700 cleaning and weighing service-point coordinates",
            "Project02 prototype-calibrated relative windows",
        ],
        "requiredInputsForAnotherProject": [
            "Base operation face and installation frame",
            "Transport vendor XYZ datum and barcode side",
            "Barcode point, scanner optical origin/axis and stop tolerance",
            "Left/right valve reachable envelopes and valve-head spacing",
            "Calibration, cleaning, weighing and drain service points",
            "Function-specific occupancy and maintenance directions",
            "Project-specific allowed contacts or nested structural pairs",
        ],
        "remainingProject02Inputs": [
            "A100 measured U/V/Z axis limits and valve-tip offsets",
            "PLC trigger position and carrier stop tolerance",
            "Configured SR-X100 production working distance",
            "A710/A720 consumable replacement sweep and A730 weighing-cup maintenance sweep",
            "A500 calibration-part replacement and A300 cup removal sweeps",
            "Motion sweep, cable/hose and operator ergonomic validation",
        ],
        "evidence": {
            "dynamicScan": str(scan_path),
            "dualValveReach": str(valve_path),
            "serviceAccess": str(service_path),
            "a700FunctionalSplit": str(a700_path),
            "cadClosure": str(closure_path),
            "verificationPlan": str(verification_path),
            "request": str(REQUEST_PATH),
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(package, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

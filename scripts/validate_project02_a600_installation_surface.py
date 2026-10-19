from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "demo/layout_previews/project02_a600_installation_surface.json"
INTERFACE = ROOT / "demo/layout_previews/project02_a600_a800_prototype_interface.json"
OUTPUT = ROOT / "demo/layout_previews/project02_a600_installation_surface.validation.json"


def main() -> int:
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    interface = json.loads(INTERFACE.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, actual: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "actual": actual})

    platform = (surface.get("installationPlatform") or {}).get("safeBoundary") or {}
    support = surface.get("transportSupportRegion") or {}
    coverage = surface.get("captureCoverage") or {}
    check("surface-builder-passed", surface.get("success") is True, surface.get("status"))
    check(
        "safe-platform-positive",
        float(platform.get("maxX", 0)) > float(platform.get("minX", 0))
        and float(platform.get("maxY", 0)) > float(platform.get("minY", 0)),
        platform,
    )
    check(
        "transport-support-inside-safe-lateral-boundary",
        float(platform.get("minY", 0)) <= float(support.get("minY", 0))
        <= float(support.get("maxY", 0)) <= float(platform.get("maxY", 0)),
        support,
    )
    check(
        "leaf-capture-at-least-99-percent",
        float(coverage.get("coverageRatio", 0)) >= 0.99,
        coverage,
    )
    check(
        "hard-keepouts-present",
        len(surface.get("hardKeepoutRegions") or []) > 0,
        len(surface.get("hardKeepoutRegions") or []),
    )
    check(
        "oversized-frame-routed-conditionally",
        len(surface.get("conditionalStructuralBodies") or []) > 0,
        len(surface.get("conditionalStructuralBodies") or []),
    )
    check(
        "surface-not-final-collision-authority",
        surface.get("authoritativeForFinalCollision") is False,
        surface.get("authoritativeForFinalCollision"),
    )
    check("prototype-interface-passed", interface.get("success") is True, interface.get("status"))
    check(
        "prototype-center-near-transport-center-plane",
        abs(float(interface.get("transportCenterPlaneOffsetMeters", 1))) <= 0.01,
        interface.get("transportCenterPlaneOffsetMeters"),
    )
    check(
        "prototype-not-mislabeled-as-vendor-interface",
        interface.get("confirmedAsVendorInterface") is False,
        interface.get("confirmedAsVendorInterface"),
    )

    success = all(item["passed"] for item in checks)
    result = {
        "success": success,
        "status": (
            "PASS_A600_COARSE_SURFACE_AND_PROTOTYPE_INTERFACE"
            if success
            else "FAIL_A600_COARSE_SURFACE_AND_PROTOTYPE_INTERFACE"
        ),
        "checks": checks,
        "nextGate": (
            "Use the A600 safe boundary and hard keepouts in the sequential placement layer; "
            "retain conditional structure and missing bodies for visual/conditional B-Rep validation."
        ),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())

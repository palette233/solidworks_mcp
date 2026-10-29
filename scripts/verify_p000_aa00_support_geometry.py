"""Read-only signed-position witness for P000 on AA00; never calls CAD/COM."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project03-v1/support-position-demo-v1"


def _vector(value, size: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{label} requires {size} numbers")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError(f"{label} contains non-finite/non-numeric values")
    return [float(v) for v in value]


def _transform(value, label: str) -> list[float]:
    transform = _vector(value, 16, label)
    rows = [transform[i:i+3] for i in (0, 3, 6)]
    for i in range(3):
        for j in range(3):
            if abs(sum(a*b for a, b in zip(rows[i], rows[j])) - (1 if i == j else 0)) > 1e-6:
                raise ValueError(f"{label} rotation is not orthonormal")
    a, b, c = rows
    determinant = a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    if abs(determinant-1) > 1e-6 or transform[12] <= 0:
        raise ValueError(f"{label} is not a proper positive-scale transform")
    return transform


def apply_transform(point: list[float], transform: list[float]) -> list[float]:
    """SolidWorks ArrayData: 3 row-basis vectors, translation, then scale."""
    return [sum(point[i]*transform[i*3+j] for i in range(3))*transform[12]+transform[9+j] for j in range(3)]


def inverse_transform(point: list[float], transform: list[float]) -> list[float]:
    delta = [(point[j]-transform[9+j])/transform[12] for j in range(3)]
    return [sum(delta[j]*transform[i*3+j] for j in range(3)) for i in range(3)]


def verify_geometry(state: dict, audit: dict, *, current_assembly_sha256: str | None = None) -> dict:
    """Return machine-readable failure, including on malformed or missing input."""
    clock = time.perf_counter()
    if not isinstance(state, dict) or not isinstance(audit, dict):
        raise ValueError("State and audit must be JSON objects")
    report = {
        "schemaVersion": "p000-aa00-support-geometry-verification/v1",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "assemblyPath": state.get("assemblyPath"), "assemblySha256": state.get("assemblySha256"),
        "readOnlyStateStartedAtUtc": state.get("startedAtUtc"),
        "actualFixationMethod": "not_verified", "collisionOrBrep": "not_evaluated",
        "checkPurpose": "signed support/position verification, not fastener or collision verification",
        "checks": {}, "points": [], "errors": [],
    }
    checks = report["checks"]
    try:
        observed = state.get("observed") or {}
        state_checks = state.get("checks") or {}
        checks["sourceStatePassed"] = state.get("success") is True and bool(state_checks) and all(v is True for v in state_checks.values())
        checks["sourceStateReadOnly"] = observed.get("readOnly") is True
        checks["sourceAssemblyHashRecorded"] = bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(state.get("assemblySha256") or "")))
        if current_assembly_sha256 is not None:
            checks["sourceAssemblyHashMatchesCurrentFile"] = current_assembly_sha256.lower() == str(state.get("assemblySha256")).lower()
        witness = audit.get("geometricWitness") or {}
        if witness.get("baseModuleToken") != "AA00" or witness.get("coordinateFrame") != "AA00_module_local":
            raise ValueError("Expected AA00-local geometry witness")
        checks["witnessIsReadOnlyNotPoseAnchor"] = witness.get("notAnExecutablePoseAnchor") is True and witness.get("targetModuleTopLevelTransformUsed") is False
        checks["demoPolicyPreserved"] = audit.get("mode") == "support_position_demo" and audit.get("actualFixationMethod") == "not_verified" and audit.get("holePatternMatchRequired") is False
        tolerance = witness.get("positionToleranceMeters")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or not 0 < tolerance <= 1e-6:
            raise ValueError("Signed position tolerance must be positive and no more than 1e-6 metres")
        report["positionToleranceMeters"] = tolerance
        base = [row for row in observed.get("components", []) if re.search(r"AA00\.001-\d+$", str(row.get("name", "")))]
        if len(base) != 1:
            raise ValueError("Expected exactly one AA00 top-level component")
        leaf = observed.get("targetLeafWitness") or {}
        relative = str(witness.get("targetLeafRelativePath") or "")
        leaf_name = str(leaf.get("name") or "").replace("\\", "/")
        checks["targetLeafIdentityMatches"] = bool(relative) and (leaf_name == relative or leaf_name.endswith("/"+relative))
        base_transform = _transform(base[0].get("transform"), "AA00 transform")
        leaf_transform = _transform(leaf.get("transform"), "P000 total leaf transform")
        references = witness.get("referencePoints") or []
        if len(references) < 3:
            raise ValueError("At least three noncollinear witness points are required")
        local_points = [_vector(r.get("targetLeafPointMeters"), 3, "target leaf point") for r in references]
        expected_points = [_vector(r.get("expectedBaseModulePointMeters"), 3, "expected AA00 point") for r in references]
        p = local_points[0]
        vectors = [[a-b for a, b in zip(q, p)] for q in local_points[1:]]
        noncollinear = any(sum(c*c for c in (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])) > 1e-16
                          for u in vectors for v in vectors)
        if not noncollinear:
            raise ValueError("Witness points are collinear")
        for row, local, expected in zip(references, local_points, expected_points):
            world = apply_transform(local, leaf_transform)
            actual = inverse_transform(world, base_transform)
            residual = [a-b for a, b in zip(actual, expected)]
            norm = math.sqrt(sum(v*v for v in residual))
            report["points"].append({"name": row.get("name"), "targetLeafPointMeters": local,
                                    "observedWorldPointMeters": world, "observedBaseModulePointMeters": actual,
                                    "expectedBaseModulePointMeters": expected,
                                    "signedResidualMeters": residual, "residualNormMeters": norm,
                                    "withinTolerance": norm <= tolerance})
        checks["signedPositionsMatchDesignSide"] = all(p["withinTolerance"] for p in report["points"])
        report["maximumResidualMeters"] = max(p["residualNormMeters"] for p in report["points"])
    except (ValueError, TypeError, KeyError) as exc:
        checks["inputsValid"] = False
        report["errors"].append(str(exc))
    else:
        checks["inputsValid"] = True
    report["success"] = bool(checks) and all(v is True for v in checks.values())
    report["status"] = "PASSED_SIGNED_SUPPORT_POSITION" if report["success"] else "FAILED_SIGNED_SUPPORT_POSITION"
    report["finishedAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["durationSeconds"] = time.perf_counter()-clock
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_ROOT / "read-only-state-verification.json")
    parser.add_argument("--audit", type=Path, default=DEFAULT_ROOT / "candidate_audit.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT / "geometry-verification.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite geometry verification evidence")
    clock, started = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    try:
        state_bytes, audit_bytes = args.state.read_bytes(), args.audit.read_bytes()
        state, audit = json.loads(state_bytes.decode("utf-8-sig")), json.loads(audit_bytes.decode("utf-8-sig"))
        if not isinstance(state, dict) or not isinstance(audit, dict):
            raise ValueError("State and audit must be JSON objects")
        current_hash = hashlib.sha256(Path(state["assemblyPath"]).read_bytes()).hexdigest()
        result = verify_geometry(state, audit, current_assembly_sha256=current_hash)
        result.update({"statePath": str(args.state.resolve()), "stateSha256": hashlib.sha256(state_bytes).hexdigest(),
                       "auditPath": str(args.audit.resolve()), "auditSha256": hashlib.sha256(audit_bytes).hexdigest()})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"schemaVersion": "p000-aa00-support-geometry-verification/v1", "success": False,
                  "status": "FAILED_SIGNED_SUPPORT_POSITION", "checks": {"inputFilesReadableAndBound": False},
                  "errors": [str(exc)], "statePath": str(args.state.resolve()), "auditPath": str(args.audit.resolve())}
    result["startedAtUtc"] = started
    result["finishedAtUtc"] = datetime.now(timezone.utc).isoformat()
    result["durationSeconds"] = time.perf_counter()-clock
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit whether the expensive Project 03 static collision closure is reusable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from finalize_project03_full_static_collision_closure import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOSURE = (
    ROOT / "demo/semantic_ports/project03_full_hybrid_static_v1/interference_closure.json"
)
DEFAULT_OUTPUT = (
    ROOT / "demo/semantic_ports/project03_full_hybrid_static_v1/closure_reuse_audit.json"
)


def audit_closure_reuse(closure: dict[str, Any]) -> dict[str, Any]:
    artifacts = (closure.get("integrity") or {}).get("artifacts") or []
    checks = []
    for item in artifacts:
        path = Path(str(item.get("path") or ""))
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        expected = str(item.get("sha256") or "")
        checks.append(
            {
                "path": str(path),
                "exists": exists,
                "sha256Matches": exists and actual == expected,
                "expectedSha256": expected,
                "actualSha256": actual,
            }
        )
    reusable = (
        closure.get("success") is True
        and closure.get("status")
        == "PASSED_FULL_STATIC_GEOMETRY_NO_NEW_INTERFERENCE"
        and bool(artifacts)
        and all(row["sha256Matches"] for row in checks)
    )
    return {
        "schemaVersion": "project03-static-closure-reuse-audit/v1",
        "status": "REUSABLE" if reusable else "INVALIDATED",
        "reusable": reusable,
        "artifactCount": len(checks),
        "validArtifactCount": sum(row["sha256Matches"] for row in checks),
        "invalidArtifacts": [row for row in checks if not row["sha256Matches"]],
        "checks": checks,
        "decision": (
            "Skip SolidWorks replay and B-rep; reuse the versioned closure."
            if reusable
            else "Do not reuse; rebuild the changed stage and rerun affected collision evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    closure_path = args.closure.resolve()
    closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
    payload = audit_closure_reuse(closure)
    payload["closurePath"] = str(closure_path)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"reusable": payload["reusable"], "status": payload["status"], "output": str(output)},
            ensure_ascii=False,
        )
    )
    return 0 if payload["reusable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

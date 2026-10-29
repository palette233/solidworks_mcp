#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project01_gn00_two_hole_port import (
    build_project01_gn00_two_hole_candidate,
)


def _read(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / "demo/semantic_ports/project01_GN00_fourth_increment_v1",
    )
    parser.add_argument(
        "--discovery-root",
        type=Path,
        default=(
            ROOT
            / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
            "project01_GN00_project03_AG00"
        ),
    )
    parser.add_argument(
        "--target-leaf-catalog",
        type=Path,
        default=(
            ROOT
            / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
            "project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
            "project01_GN00_project03_AG00/two-hole-candidate-v1"
        ),
    )
    args = parser.parse_args()
    source = args.source_root.resolve()
    discovery = args.discovery_root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite candidate directory: {output}")
    result = build_project01_gn00_two_hole_candidate(
        _read(source / "assembly_plan_effective.json"),
        _read(source / "face_endpoint_catalog.json"),
        _read(source / "semantic_port_catalog.json"),
        _read(discovery / "gn00-primary-mount-leaf-face-catalog.json"),
        _read(discovery / "gn00-support-mount-leaf-face-catalog.json"),
        _read(args.target_leaf_catalog),
        _read(discovery / "secondary_datum_discovery_two_leaves.json"),
    )
    output.mkdir(parents=True)
    _write(output / "face_endpoint_catalog.json", result["endpointCatalog"])
    _write(output / "semantic_port_catalog.json", result["semanticCatalog"])
    _write(
        output / "assembly_plan_effective.nonprototype.json",
        result["effectiveGraph"],
    )
    _write(output / "candidate_summary.json", result["summary"])
    print(
        json.dumps(
            {"success": True, "output": str(output), **result["summary"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

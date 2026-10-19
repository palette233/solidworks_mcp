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

from demo_backend.project03_ag00_three_datum_port import (
    build_project03_ag00_three_datum_candidate,
)


def _read(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--diagnostic-root",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_diagnostic_v1",
    )
    parser.add_argument(
        "--discovery-root",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-datum-discovery-v1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1",
    )
    args = parser.parse_args()
    diagnostic = args.diagnostic_root.resolve()
    discovery_root = args.discovery_root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite candidate directory: {output}")
    result = build_project03_ag00_three_datum_candidate(
        _read(diagnostic / "assembly_plan_effective.json"),
        _read(diagnostic / "face_endpoint_catalog.json"),
        _read(diagnostic / "semantic_port_catalog.json"),
        _read(discovery_root / "ag00_primary_mount_leaf_faces.json"),
        _read(discovery_root / "ag00_support_mount_leaf_faces.json"),
        _read(discovery_root / "aa00_ag00_mount_leaf_faces.json"),
        _read(discovery_root / "ag00_secondary_datum_discovery_v2.json"),
    )
    output.mkdir(parents=True)
    _write(output / "face_endpoint_catalog.json", result["endpointCatalog"])
    _write(output / "semantic_port_catalog.json", result["semanticCatalog"])
    _write(output / "assembly_plan_effective.nonprototype.json", result["effectiveGraph"])
    _write(output / "candidate_summary.json", result["summary"])
    print(json.dumps({"success": True, "output": str(output), **result["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

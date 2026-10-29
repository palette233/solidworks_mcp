#!/usr/bin/env python3
"""Derive support-constrained calibration station candidates; never run CAD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.calibration_function_point import (  # noqa: E402
    build_station_candidate_decision_index,
    build_calibration_function_point_catalog,
    derive_calibration_planar_station_candidates,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialize_package(directory: Path, package: dict) -> dict:
    directory.mkdir()
    package = json.loads(json.dumps(package))
    graph = package.pop("effectiveGraph")
    endpoints = package.pop("selectedEndpointCatalog")
    graph_path = directory / "effective-mate-graph.json"
    endpoints_path = directory / "selected-face-endpoint-catalog.json"
    manifest_path = directory / "validation-package.json"
    _write(graph_path, graph)
    _write(endpoints_path, endpoints)
    package["artifacts"] = {
        "effectiveGraph": {"path": str(graph_path.resolve()), "sha256": _sha(graph_path)},
        "selectedEndpointCatalog": {
            "path": str(endpoints_path.resolve()), "sha256": _sha(endpoints_path),
        },
    }
    _write(manifest_path, package)
    return {"path": str(manifest_path.resolve()), "sha256": _sha(manifest_path)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources", type=Path,
        default=Path("data/assembly_stations/calibration-function-point-sources-v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = (ROOT / args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite calibration candidates: {output}")
    output.mkdir(parents=True)
    catalog = build_calibration_function_point_catalog(ROOT, args.sources)
    report = derive_calibration_planar_station_candidates(ROOT, catalog)
    for row in report["candidates"]:
        package = row.pop("candidatePackage", None)
        if package is None:
            continue
        name = "-to-".join((
            row["sourceModuleDefinitionId"].replace("::", "-"),
            row["targetBaseDefinitionId"].replace("::", "-"),
        ))
        row["candidatePackageArtifact"] = _materialize_package(output / name, package)
    report_path = output / "calibration-planar-station-candidates.json"
    _write(report_path, report)
    index = build_station_candidate_decision_index(
        report,
        report_path=str(report_path.relative_to(ROOT)).replace("\\", "/"),
        report_sha256=_sha(report_path),
    )
    _write(output / "station-candidate-decision-index.json", index)
    _write(output / "calibration-function-point-catalog.json", catalog)
    print(json.dumps({"output": str(output), **report["summary"], "cadExecuted": False},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

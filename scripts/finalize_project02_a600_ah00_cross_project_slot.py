#!/usr/bin/env python3
"""Finalize and publish the CAD-validated A600/AH00 cross-project slot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_slot_release import (  # noqa: E402
    finalize_a600_ah00_cross_project_slot,
)


ACQUISITION = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)
VALIDATION = ACQUISITION / "cad-validation-v1"
OUTPUT = (
    ROOT
    / "demo/semantic_ports/"
    "project02_A600_project03_AH00_cross_project_slot_v1"
)
AH00_PACKAGE = ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _write(path: Path, value: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"拒绝覆盖已存在的发布文件：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()

    candidate_path = ACQUISITION / "candidate_semantic_port.json"
    plan_path = VALIDATION / "candidate_validation_plan.json"
    graph_path = VALIDATION / "candidate_effective_mate_graph.json"
    result_path = VALIDATION / "candidate_cad_result.json"
    assembly_path = (
        VALIDATION / "project02-a600-project03-ah00-candidate-v1.SLDASM"
    )
    candidate = _read(candidate_path)
    plan = _read(plan_path)
    graph = _read(graph_path)
    result = _read(result_path)
    source_paths = {
        key: Path(value).resolve()
        for key, value in (plan.get("sourceModulePaths") or {}).items()
    }
    required_files = [
        candidate_path,
        plan_path,
        graph_path,
        result_path,
        assembly_path,
        *source_paths.values(),
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少发布输入：" + ", ".join(missing))

    closure_path = output / "cross_project_slot_closure.json"
    package = finalize_a600_ah00_cross_project_slot(
        candidate=candidate,
        validation_plan=plan,
        effective_graph=graph,
        effective_graph_file_sha256=_sha256(graph_path),
        cad_result=result,
        output_assembly_sha256=_sha256(assembly_path),
        current_source_sha256={
            key: _sha256(path) for key, path in source_paths.items()
        },
        a600_face_catalog=_read(
            ACQUISITION / "a600-native-service-leaf-face-catalog-v1.json"
        ),
        ah00_semantic_catalog=_read(AH00_PACKAGE / "semantic_port_catalog.json"),
        ah00_face_catalog=_read(AH00_PACKAGE / "face_endpoint_catalog.json"),
        endpoint_catalog_path="face_endpoint_catalog.json",
        effective_graph_path=_relative(graph_path),
        validation_evidence_path=_relative(closure_path),
        output_assembly_path=str(assembly_path.resolve()),
    )
    _write(
        output / "face_endpoint_catalog.json",
        package["endpointCatalog"],
        overwrite=args.overwrite,
    )
    _write(
        output / "semantic_port_catalog.json",
        package["semanticCatalog"],
        overwrite=args.overwrite,
    )
    _write(closure_path, package["closure"], overwrite=args.overwrite)
    summary = {
        "success": True,
        "status": package["closure"]["status"],
        "productionReady": False,
        "semanticPortCatalogPath": str(output / "semantic_port_catalog.json"),
        "faceEndpointCatalogPath": str(output / "face_endpoint_catalog.json"),
        "closurePath": str(closure_path),
        "closureDigest": package["closure"]["closureDigest"],
        "outputAssemblyPath": str(assembly_path.resolve()),
        "outputAssemblySha256": package["closure"]["outputAssemblySha256"],
        "collisionOrBrep": "not_evaluated",
        "nextAction": "rebuild-global-catalog-and-release-authorized-template",
    }
    _write(output / "build_summary.json", summary, overwrite=args.overwrite)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

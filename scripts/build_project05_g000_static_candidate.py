#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_module_catalog import (  # noqa: E402
    build_global_module_catalog,
    validate_global_module_catalog,
)
from demo_backend.project05_g000_static_port import (  # noqa: E402
    build_g000_static_candidate,
)


SOURCE = ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/G000"
PROTOTYPE_GRAPH = ROOT / "demo/layout_previews/project05_module_mate_graph_v2_axes.json"
DEFAULT_OUTPUT = ROOT / "demo/global_assembly_catalog/coverage-v2/g000-four-relation-candidate-v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建Project05 G000静态四关系无锚点候选。")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    candidate, graph = build_g000_static_candidate(
        _read(SOURCE / "semantic_port_catalog.json"),
        _read(SOURCE / "face_endpoint_catalog.json"),
        _read(SOURCE / "assembly_plan_effective.json"),
        _read(PROTOTYPE_GRAPH),
    )
    candidate["endpointCatalogPath"] = (
        output / "face_endpoint_catalog.json"
    ).relative_to(ROOT).as_posix()
    candidate["effectiveMateGraphPath"] = (
        output / "assembly_plan_effective.json"
    ).relative_to(ROOT).as_posix()
    _write(output / "semantic_port_catalog.json", candidate)
    _write(output / "face_endpoint_catalog.json", _read(SOURCE / "face_endpoint_catalog.json"))
    _write(output / "assembly_plan_effective.json", graph)
    catalog = build_global_module_catalog(
        ROOT,
        additional_semantic_catalog_paths=[output / "semantic_port_catalog.json"],
    )
    validate_global_module_catalog(catalog)
    _write(output / "global_module_catalog.candidate.json", catalog)
    template = next(
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == "G000_to_A000_static_four_relation_v2"
    )
    summary = {
        "schemaVersion": "project05-g000-static-candidate/v1",
        "status": "candidate_pending_nonprototype_cad",
        "projectId": "project05",
        "moduleToken": "G000",
        "legacyTemplateId": template["legacyTemplateId"],
        "globalTemplateId": template["globalTemplateId"],
        "mateCount": len(template.get("mateSteps") or []),
        "casePoseAnchorUsed": False,
        "leafPoseAnchorCount": 0,
        "internalFlexibilityPreserved": True,
        "externalPlacementWitnessRequired": True,
        "productionReady": False,
        "collisionStatus": "not_evaluated",
    }
    _write(output / "candidate_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

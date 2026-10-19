#!/usr/bin/env python3
"""Build the D000 deterministic non-source-pose semantic-port candidate."""

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
from demo_backend.driving_relation_release_publisher import (  # noqa: E402
    publish_driving_relation_release,
)
from demo_backend.project05_complete_cumulative_chain import (  # noqa: E402
    D000_REFRESH_LEGACY_ID,
    build_d000_deterministic_candidate,
)


SOURCE = ROOT / "demo/global_assembly_catalog/v1/driving-v1-preview/project05_D000_A000_scoped_driving_v2"
SOURCE_GRAPH = ROOT / "demo/semantic_ports/project05_resolved_pair_jobs/project05-job-2fd5dca2ddd7/attempt-01/transaction/effective-graph.json"
DEFAULT_OUTPUT = ROOT / "demo/global_assembly_catalog/coverage-v2/d000-deterministic-candidate-v1"
DEFAULT_RELEASE_ID = "relation-v60-project05-d000-deterministic-driving-20261014"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    args = parser.parse_args()
    output = args.output.resolve() if args.output.is_absolute() else (ROOT / args.output).resolve()
    semantic_path = output / "semantic_port_catalog.json"
    endpoint_path = output / "face_endpoint_catalog.json"
    graph0_path = output / "assembly_plan_effective_seed0.json"
    graph1_path = output / "assembly_plan_effective_seed1.json"
    relative = lambda path: path.resolve().relative_to(ROOT).as_posix()
    semantic, graph0 = build_d000_deterministic_candidate(
        _read(SOURCE / "semantic_port_catalog.json"),
        _read(SOURCE_GRAPH),
        semantic_catalog_path=relative(semantic_path),
        endpoint_catalog_path=relative(endpoint_path),
        effective_graph_path=relative(graph0_path),
        initial_placement_variant=0,
    )
    _, graph1 = build_d000_deterministic_candidate(
        _read(SOURCE / "semantic_port_catalog.json"),
        _read(SOURCE_GRAPH),
        semantic_catalog_path=relative(semantic_path),
        endpoint_catalog_path=relative(endpoint_path),
        effective_graph_path=relative(graph1_path),
        initial_placement_variant=1,
    )
    _write(semantic_path, semantic)
    _write(endpoint_path, _read(SOURCE / "face_endpoint_catalog.json"))
    _write(graph0_path, graph0)
    _write(graph1_path, graph1)
    catalog = build_global_module_catalog(
        ROOT, additional_semantic_catalog_paths=[semantic_path]
    )
    validate_global_module_catalog(catalog)
    _write(output / "global_module_catalog.candidate.json", catalog)
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId") == D000_REFRESH_LEGACY_ID
    )
    summary = {
        "schemaVersion": "project05-d000-deterministic-candidate/v1",
        "status": "candidate_pending_two_pose_cad",
        "legacyTemplateId": D000_REFRESH_LEGACY_ID,
        "globalTemplateId": template["globalTemplateId"],
        "mateCount": len(template.get("mateSteps") or []),
        "initialPlacementVariants": [0, 1],
        "casePoseAnchorUsed": False,
        "leafPoseAnchorCount": 0,
        "collisionStatus": "not_evaluated",
    }
    _write(output / "candidate_summary.json", summary)
    if args.publish:
        baseline = output / "project05_D000_deterministic_seed0_v3.result.json"
        confirmation = output / "project05_D000_deterministic_seed1_confirmation_v3.result.json"
        if not baseline.is_file() or not confirmation.is_file():
            raise FileNotFoundError("发布D000前必须完成两种非原型初始位姿CAD实验。")
        spec = {
            "schemaVersion": "driving-relation-release-spec/v1",
            "releaseId": args.release_id,
            "projectId": "project05",
            "drivingScope": "project05_A000_D000_deterministic_non_source_repeatability",
            "catalogPath": relative(output / "global_module_catalog.candidate.json"),
            "templates": [
                {
                    "legacyTemplateId": D000_REFRESH_LEGACY_ID,
                    "globalTemplateId": template["globalTemplateId"],
                    "evidencePath": relative(confirmation),
                    "repeatabilityBaselineEvidencePath": relative(baseline),
                    "expectedMateCount": 3,
                    "requireDeclaredClosed": True,
                }
            ],
            "authorizedTemplateCombinationIds": [],
        }
        _write(output / "driving_release_spec.json", spec)
        publication = publish_driving_relation_release(ROOT, spec)
        summary["status"] = "published"
        summary["releaseId"] = args.release_id
        summary["releaseManifestPath"] = publication["manifestPath"]
        summary["repeatabilityBaselineEvidencePath"] = relative(baseline)
        summary["confirmationEvidencePath"] = relative(confirmation)
        _write(output / "publication_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

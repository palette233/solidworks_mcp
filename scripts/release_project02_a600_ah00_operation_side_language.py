#!/usr/bin/env python3
"""Publish the A600/AH00 operation-side natural-language binding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_slot_release import (  # noqa: E402
    augment_a600_ah00_template_with_operation_side_semantics,
    build_a600_ah00_operation_side_release_evidence,
)
from demo_backend.global_relation_catalog_release import (  # noqa: E402
    build_relation_catalog_release,
    finalize_relation_catalog_release,
)


SOURCE_RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v41-project02-a600-project03-ah00-driving-20261012"
)
PACKAGE = ROOT / (
    "demo/semantic_ports/project02_A600_project03_AH00_cross_project_slot_v1"
)
CAD_RESULT = ROOT / (
    "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition/cad-validation-v1/"
    "candidate_cad_result.json"
)
DEFAULT_RELEASE_ID = (
    "relation-v42-project02-a600-ah00-operation-side-language-20261012"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖不可变发布文件：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/releases",
    )
    args = parser.parse_args()

    source_catalog_path = SOURCE_RELEASE / "global_module_catalog.json"
    source_manifest_path = SOURCE_RELEASE / "release-manifest.json"
    source_catalog = _read(source_catalog_path)
    source_manifest = _read(source_manifest_path)
    closure = _read(PACKAGE / "cross_project_slot_closure.json")
    candidate = augment_a600_ah00_template_with_operation_side_semantics(
        source_catalog
    )
    candidate_path = PACKAGE / "global_module_catalog.operation-side-preview.json"
    _write(candidate_path, candidate)

    evidence = build_a600_ah00_operation_side_release_evidence(
        candidate,
        source_catalog=source_catalog,
        source_manifest=source_manifest,
        closure=closure,
    )
    evidence["sourceCatalogPath"] = source_catalog_path.relative_to(ROOT).as_posix()
    evidence["sourceReleaseManifestPath"] = (
        source_manifest_path.relative_to(ROOT).as_posix()
    )
    evidence["sourceEvidence"] = {
        "slotClosurePath": (
            PACKAGE / "cross_project_slot_closure.json"
        ).relative_to(ROOT).as_posix(),
        "liveCadResultPath": CAD_RESULT.relative_to(ROOT).as_posix(),
    }
    evidence_path = PACKAGE / "operation_side_language_release_evidence.json"
    _write(evidence_path, evidence)

    template_id = evidence["authorizedDrivingTemplateIds"][0]
    released_catalog, manifest = build_relation_catalog_release(
        catalog_path=candidate_path,
        derivation_evidence_path=evidence_path,
        validation_evidence_paths=[CAD_RESULT],
        release_id=args.release_id,
        authorized_driving_template_ids=[template_id],
        authorized_template_combination_ids=[],
    )
    output = args.output_root.resolve() / args.release_id
    if output.exists():
        raise FileExistsError(f"拒绝覆盖不可变发布目录：{output}")
    catalog_output = output / "global_module_catalog.json"
    manifest_output = output / "release-manifest.json"
    _write(catalog_output, released_catalog)
    manifest = finalize_relation_catalog_release(
        manifest,
        released_catalog_path=catalog_output,
        workspace_root=ROOT,
    )
    _write(manifest_output, manifest)
    print(
        json.dumps(
            {
                "success": True,
                "releaseId": args.release_id,
                "catalogDigest": manifest["catalogDigest"],
                "authorizedDrivingTemplateIds": [template_id],
                "sideSemantics": ["operator_side"],
                "catalogPath": str(catalog_output),
                "manifestPath": str(manifest_output),
                "solidWorksExecutedInThisPublish": False,
                "collisionStatus": "not_evaluated",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

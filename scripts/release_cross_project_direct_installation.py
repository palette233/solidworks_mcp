#!/usr/bin/env python3
"""Publish one CAD-validated cross-project direct installation bundle."""

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
    augment_release_catalog_with_cross_project_template,
    build_cross_project_direct_release_evidence,
)
from demo_backend.global_relation_catalog_release import (  # noqa: E402
    build_relation_catalog_release,
    finalize_relation_catalog_release,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖不可变证据：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-release", type=Path, required=True)
    parser.add_argument("--substitution-catalog", type=Path, required=True)
    parser.add_argument("--legacy-template-id", required=True)
    parser.add_argument("--cad-result", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--release-project-id", required=True)
    parser.add_argument("--source-project-id", required=True)
    parser.add_argument("--target-project-id", required=True)
    parser.add_argument("--driving-scope", required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/releases",
    )
    args = parser.parse_args()

    source_release = args.source_release.resolve()
    source_catalog_path = source_release / "global_module_catalog.json"
    source_manifest_path = source_release / "release-manifest.json"
    substitution_path = args.substitution_catalog.resolve()
    cad_result_path = args.cad_result.resolve()
    candidate = augment_release_catalog_with_cross_project_template(
        _read(source_catalog_path),
        _read(substitution_path),
        legacy_template_id=args.legacy_template_id,
    )
    package = substitution_path.parent
    preview_path = package / f"{args.release_id}.catalog-preview.json"
    evidence_path = package / f"{args.release_id}.release-evidence.json"
    _write(preview_path, candidate)
    evidence = build_cross_project_direct_release_evidence(
        candidate,
        _read(cad_result_path),
        legacy_template_id=args.legacy_template_id,
        release_project_id=args.release_project_id,
        source_project_id=args.source_project_id,
        target_project_id=args.target_project_id,
        driving_scope=args.driving_scope,
        statement=args.statement,
    )
    evidence["sourceCatalogPath"] = _relative(source_catalog_path)
    evidence["sourceReleaseManifestPath"] = _relative(source_manifest_path)
    evidence["sourceEvidence"] = {
        "substitutionCatalogPath": _relative(substitution_path),
        "liveCadResultPath": _relative(cad_result_path),
    }
    _write(evidence_path, evidence)

    template_id = evidence["authorizedDrivingTemplateIds"][0]
    released_catalog, manifest = build_relation_catalog_release(
        catalog_path=preview_path,
        derivation_evidence_path=evidence_path,
        validation_evidence_paths=[cad_result_path],
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
                "catalogPath": str(catalog_output),
                "manifestPath": str(manifest_output),
                "reusedLiveCadEvidence": str(cad_result_path),
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

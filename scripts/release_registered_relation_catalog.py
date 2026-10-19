from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_relation_catalog_release import (  # noqa: E402
    build_relation_catalog_release,
    finalize_relation_catalog_release,
)


DEFAULT_EVIDENCE = [
    ROOT / "demo/global_assembly_contexts/manifest_jobs/project03-job-ac77c693ae78/packet-runs/packet-002-attempt-02/cad-result.json",
    ROOT / "demo/global_assembly_contexts/project01-relation-validation-v1/final-validation-report.json",
    ROOT / "demo/global_assembly_contexts/project01-coincident-validation-v1/final-validation-report.json",
    ROOT / "demo/global_assembly_contexts/project01-concentric-validation-v1/final-validation-report.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Release a validated registered relation catalog.")
    parser.add_argument("--release-id", default="relation-v5-20261011")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v5-preview.json",
    )
    parser.add_argument(
        "--derivation-evidence",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1/relation-v5-preview/derivation-evidence.json",
    )
    parser.add_argument("--validation-evidence", type=Path, action="append")
    parser.add_argument("--authorize-driving-template", action="append")
    parser.add_argument("--authorize-template-combination", action="append")
    parser.add_argument("--output-root", type=Path, default=ROOT / "demo/global_assembly_catalog/releases")
    args = parser.parse_args()

    catalog, manifest = build_relation_catalog_release(
        catalog_path=args.catalog,
        derivation_evidence_path=args.derivation_evidence,
        validation_evidence_paths=args.validation_evidence or DEFAULT_EVIDENCE,
        release_id=args.release_id,
        authorized_driving_template_ids=args.authorize_driving_template or [],
        authorized_template_combination_ids=(
            args.authorize_template_combination or []
        ),
    )
    output = args.output_root.resolve() / args.release_id
    output.mkdir(parents=True, exist_ok=True)
    catalog_output = output / "global_module_catalog.json"
    manifest_output = output / "release-manifest.json"
    catalog_output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = finalize_relation_catalog_release(
        manifest,
        released_catalog_path=catalog_output,
        workspace_root=ROOT,
    )
    manifest_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "releaseId": args.release_id,
                "catalogDigest": manifest["catalogDigest"],
                "derivedTemplateCount": len(manifest["derivedTemplateIds"]),
                "validationEvidenceCount": len(manifest["validationEvidence"]),
                "catalog": str(catalog_output),
                "manifest": str(manifest_output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

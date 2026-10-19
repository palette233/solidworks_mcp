#!/usr/bin/env python3
"""Publish one Project01-base transport/scanner/calibration chain release.

The script does not run SolidWorks and does not invent geometry.  It combines
three already CAD-proven, pose-anchor-free installation templates into one
immutable authorization set:

* Project03 AE00 transport -> Project01 JJ00 transport slot;
* Project01 SM00 scanner -> Project01 JJ00 scanner slot;
* Project03 AH00 calibration -> Project01 JJ00 calibration slot.
"""

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
    TRANSPORT_LEGACY_TEMPLATE_ID,
    augment_release_catalog_with_cross_project_template,
)
from demo_backend.driving_relation_release_publisher import (  # noqa: E402
    publish_driving_relation_release,
)


RELEASE_ID = (
    "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014"
)
BASE_RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v38-project01-topology-bound-combination-driving-20261011"
)
TRANSPORT_CATALOG = ROOT / (
    "demo/cross_project_substitution/transport-v1/"
    "cross_project_substitution_catalog.json"
)
CALIBRATION_CATALOG = ROOT / (
    "demo/cross_project_substitution/mvp-v1/"
    "cross_project_substitution_catalog.json"
)
PACKAGE = ROOT / "demo/cross_project_substitution/cumulative-project01-v1"

TRANSPORT_TEMPLATE_ID = (
    "template/cross-project/ae00-to-project01-ss00-slot/97aed2cb02"
)
SCANNER_TEMPLATE_ID = (
    "template/project01/sm00-to-jj00-three-datum-installation/3cc07ef613"
)
CALIBRATION_TEMPLATE_ID = (
    "template/cross-project/ah00-to-project01-bd00-slot/6ef3e3ad8d"
)
CALIBRATION_LEGACY_TEMPLATE_ID = (
    "cross_project_project03_AH00_to_project01_BD00_slot"
)

TRANSPORT_EVIDENCE = ROOT / (
    "demo/cross_project_substitution/transport-v1/jobs/"
    "project03-job-e64acfa17a55/packet-runs/packet-001-attempt-01/"
    "cad-result.json"
)
SCANNER_EVIDENCE = ROOT / (
    "demo/semantic_ports/project01_SM00_release_refresh_v1/"
    "step03_SM00_release_refresh.cad-result.json"
)
CALIBRATION_EVIDENCE = ROOT / (
    "demo/cross_project_substitution/mvp-v1/jobs/"
    "project03-job-d75711e079d8/packet-runs/packet-001-attempt-01/"
    "cad-result.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖不可变发布输入：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def build_candidate_catalog() -> dict:
    catalog = _read(BASE_RELEASE / "global_module_catalog.json")
    catalog = augment_release_catalog_with_cross_project_template(
        catalog,
        _read(TRANSPORT_CATALOG),
        legacy_template_id=TRANSPORT_LEGACY_TEMPLATE_ID,
    )
    return augment_release_catalog_with_cross_project_template(
        catalog,
        _read(CALIBRATION_CATALOG),
        legacy_template_id=CALIBRATION_LEGACY_TEMPLATE_ID,
    )


def build_release_spec(release_id: str, catalog_path: Path) -> dict:
    return {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": release_id,
        "projectId": "project-global",
        "drivingScope": (
            "project01_JJ00_with_project03_AE00_transport_"
            "project01_SM00_scanner_project03_AH00_calibration"
        ),
        "catalogPath": _relative(catalog_path),
        "templates": [
            {
                "legacyTemplateId": TRANSPORT_LEGACY_TEMPLATE_ID,
                "globalTemplateId": TRANSPORT_TEMPLATE_ID,
                "evidencePath": _relative(TRANSPORT_EVIDENCE),
                "expectedMateCount": 3,
            },
            {
                "legacyTemplateId": "SM00_to_JJ00_three_datum_installation",
                "globalTemplateId": SCANNER_TEMPLATE_ID,
                "evidencePath": _relative(SCANNER_EVIDENCE),
                "expectedMateCount": 3,
            },
            {
                "legacyTemplateId": CALIBRATION_LEGACY_TEMPLATE_ID,
                "globalTemplateId": CALIBRATION_TEMPLATE_ID,
                "evidencePath": _relative(CALIBRATION_EVIDENCE),
                "expectedMateCount": 3,
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=RELEASE_ID)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/releases",
    )
    args = parser.parse_args()

    PACKAGE.mkdir(parents=True, exist_ok=True)
    candidate_path = PACKAGE / f"{args.release_id}.catalog-preview.json"
    spec_path = PACKAGE / f"{args.release_id}.release-spec.json"
    _write_new(candidate_path, build_candidate_catalog())
    spec = build_release_spec(args.release_id, candidate_path)
    _write_new(spec_path, spec)
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = (ROOT / output_root).resolve()
    report = publish_driving_relation_release(
        ROOT,
        spec,
        output_root=output_root,
    )
    report["candidateCatalogPath"] = str(candidate_path)
    report["releaseSpecPath"] = str(spec_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
SCRIPTS = ROOT / "scripts"
for entry in (BACKEND, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from build_project05_nonanchor_driving_candidate import build_candidate  # noqa: E402
from demo_backend.global_module_catalog import (  # noqa: E402
    build_global_module_catalog,
    validate_global_module_catalog,
)


CHECKPOINT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-k000-checkpoint-v1/project05-k000-nonanchor-checkpoint.result.json"
)
D000_CANDIDATE = ROOT / (
    "demo/global_assembly_catalog/v1/driving-v1-preview/"
    "project05_D000_A000_scoped_driving_v2/semantic_port_catalog.json"
)
V5_ROOT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v5"
)
P000_CANDIDATE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v6/P000/semantic_port_catalog.json"
)
N000_CANDIDATE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v7/N000/semantic_port_catalog.json"
)
DEFAULT_PACKAGE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v8/K000"
)
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.project05-nonanchor-driving-v8-preview.json"
)
DEFAULT_EVIDENCE = DEFAULT_PACKAGE.parent / "candidate-evidence.json"


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_k000_package(package_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return build_candidate("K000", CHECKPOINT, package_dir)


def build_combined_catalog(package_dir: Path) -> dict[str, Any]:
    paths = [
        D000_CANDIDATE,
        *(V5_ROOT / token / "semantic_port_catalog.json" for token in ("F000", "M000", "G000")),
        P000_CANDIDATE,
        N000_CANDIDATE,
        package_dir / "semantic_port_catalog.json",
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("候选聚合缺少语义包：" + "; ".join(missing))
    catalog = build_global_module_catalog(
        ROOT,
        additional_semantic_catalog_paths=paths,
    )
    validate_global_module_catalog(catalog)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="构建Project05 K000三配合无锚点驱动候选。")
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()

    package_dir = args.package_dir.resolve()
    candidate, assessment = build_k000_package(package_dir)
    catalog = build_combined_catalog(package_dir)
    source = _relative(package_dir / "semantic_port_catalog.json")
    matches = [
        row
        for row in catalog.get("connectionTemplates") or []
        if (row.get("provenance") or {}).get("semanticCatalogPath") == source
    ]
    if len(matches) != 1:
        raise ValueError(f"K000预期一个候选模板，实际为{len(matches)}。")
    template = matches[0]
    evidence = {
        "schemaVersion": "project05-k000-nonanchor-driving-candidate/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project05",
        "moduleToken": "K000",
        "packagePath": _relative(package_dir),
        "sourceCatalogPath": _relative(args.catalog_output.resolve()),
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "legacyTemplateId": template.get("legacyTemplateId"),
        "globalTemplateId": template.get("globalTemplateId"),
        "mateCount": len(template.get("mateSteps") or []),
        "checkpointPath": _relative(CHECKPOINT),
        "checkpointAssessment": assessment,
        "expectedResidualDof": 0,
        "caseAnchorAllowed": False,
        "collisionStatus": "not_evaluated",
    }
    _write(args.catalog_output.resolve(), catalog)
    _write(args.evidence_output.resolve(), evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

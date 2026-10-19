from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_relation_template_derivation import (  # noqa: E402
    derive_standalone_validation_relation,
)


def _load(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a candidate global catalog from registered relation derivations."
    )
    parser.add_argument(
        "--source-catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/relation_template_derivations.v2.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v5-preview.json",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/relation-v5-preview/derivation-evidence.json",
    )
    args = parser.parse_args()

    catalog = _load(args.source_catalog)
    registry = _load(args.registry)
    if registry.get("schemaVersion") != "global-relation-template-derivation-registry/v1":
        raise ValueError("不支持的关系模板派生注册表版本。")
    evidence_rows = []
    for entry in registry.get("entries") or []:
        mode = str(entry.get("mode") or "")
        if mode not in {"extract_validate_only", "existing_mate_observation"}:
            raise ValueError(f"未知派生模式：{mode}")
        catalog, evidence = derive_standalone_validation_relation(
            catalog,
            source_global_template_id=str(entry["sourceGlobalTemplateId"]),
            mate_name=str(entry["mateName"]),
            observation_of_existing_mate=mode == "existing_mate_observation",
        )
        evidence_rows.append({"entry": entry, "result": evidence})

    report = {
        "schemaVersion": "global-relation-template-derivation-run/v1",
        "status": "ready",
        "sourceCatalogPath": str(args.source_catalog.resolve()),
        "registryPath": str(args.registry.resolve()),
        "outputCatalogPath": str(args.output.resolve()),
        "outputCatalogDigest": catalog["catalogDigest"],
        "derivedTemplateCount": len(evidence_rows),
        "derivations": evidence_rows,
        "solidWorksExecuted": False,
    }
    _write(args.output.resolve(), catalog)
    _write(args.evidence.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

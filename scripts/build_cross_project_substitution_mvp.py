from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.cross_project_module_substitution import (  # noqa: E402
    augment_catalog_with_role_and_port_overlay,
    build_cross_project_substitution_catalog,
    build_module_role_overlay,
    compile_substitution_preview,
    compose_cross_project_effective_mate_graph,
    validate_module_role_overlay,
)
from demo_backend.global_module_catalog import validate_global_module_catalog  # noqa: E402


DEFAULT_CATALOG = (
    WORKSPACE / "demo" / "global_assembly_catalog" / "v1" / "global_module_catalog.json"
)
DEFAULT_OUTPUT = WORKSPACE / "demo" / "cross_project_substitution" / "mvp-v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="构建全目录角色/端口轻量覆盖，并编译一个跨项目同角色替换MVP。"
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", default="project03:AH00")
    parser.add_argument("--replace", default="project01:BD00")
    parser.add_argument(
        "--requirement",
        default="在项目01基座中使用项目03 AH00针头校准模组替换BD00，并编译装配事务。",
    )
    args = parser.parse_args()

    started = perf_counter()
    timings: dict[str, float] = {}
    catalog_path = args.catalog.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    checkpoint = perf_counter()
    catalog = _read_json(catalog_path)
    catalog_validation = validate_global_module_catalog(catalog)
    timings["loadAndValidateCatalogSeconds"] = perf_counter() - checkpoint

    checkpoint = perf_counter()
    overlay = build_module_role_overlay(catalog)
    overlay_validation = validate_module_role_overlay(overlay, catalog)
    normalized = augment_catalog_with_role_and_port_overlay(catalog, overlay)
    timings["roleAndPortOverlaySeconds"] = perf_counter() - checkpoint

    checkpoint = perf_counter()
    effective_graph_path = output / "cross_project_effective_mate_graph.json"
    effective_graph = compose_cross_project_effective_mate_graph(
        WORKSPACE,
        catalog,
        overlay,
        source_module=args.source,
        replaced_module=args.replace,
    )
    effective_graph_relative = effective_graph_path.relative_to(WORKSPACE).as_posix()
    effective_graph["SavedJsonPath"] = str(effective_graph_path)
    _write_json(effective_graph_path, effective_graph)
    timings["effectiveMateGraphCompositionSeconds"] = perf_counter() - checkpoint

    checkpoint = perf_counter()
    candidate, substitution_report = build_cross_project_substitution_catalog(
        catalog,
        overlay,
        source_module=args.source,
        replaced_module=args.replace,
        effective_mate_graph_path=effective_graph_relative,
    )
    timings["compatibilityEvaluationSeconds"] = perf_counter() - checkpoint

    checkpoint = perf_counter()
    preview = compile_substitution_preview(
        catalog,
        overlay,
        source_module=args.source,
        replaced_module=args.replace,
        requirement=args.requirement,
        effective_mate_graph_path=effective_graph_relative,
    )
    timings["naturalLanguageAndTransactionCompileSeconds"] = perf_counter() - checkpoint
    timings["totalSeconds"] = perf_counter() - started

    paths = {
        "roleOverlay": output / "module_semantic_role_overlay.json",
        "normalizedCatalog": output / "global_module_catalog_role_port_overlay.json",
        "substitutionCatalog": output / "cross_project_substitution_catalog.json",
        "substitutionReport": output / "cross_project_substitution_report.json",
        "compiledPreview": output / "cross_project_substitution_preview.json",
        "effectiveMateGraph": effective_graph_path,
        "assemblyContext": output / "cross_project_assembly_context.json",
        "transactionDag": output / "cross_project_transaction_dag.json",
        "cadTransactionManifest": output / "cross_project_cad_transaction_manifest.json",
        "summary": output / "build_summary.json",
    }
    _write_json(paths["roleOverlay"], overlay)
    _write_json(paths["normalizedCatalog"], normalized)
    _write_json(paths["substitutionCatalog"], candidate)
    _write_json(paths["substitutionReport"], substitution_report)
    _write_json(paths["compiledPreview"], preview)
    _write_json(paths["assemblyContext"], preview.get("context") or {})
    _write_json(paths["transactionDag"], preview.get("transactionDag") or {})
    _write_json(
        paths["cadTransactionManifest"],
        preview.get("cadTransactionManifest") or {},
    )

    summary = {
        "schemaVersion": "cross-project-substitution-mvp-build/v1",
        "status": preview.get("status"),
        "success": preview.get("success") is True,
        "sourceCatalogPath": str(catalog_path),
        "sourceCatalogDigest": catalog.get("catalogDigest"),
        "sourceModule": args.source,
        "replacedModule": args.replace,
        "requirement": args.requirement,
        "catalogValidation": catalog_validation,
        "overlayValidation": overlay_validation,
        "roleCoverage": {
            "moduleCount": overlay.get("moduleCount"),
            "acceptedRoleCount": sum(
                row.get("roleReviewStatus") == "accepted_by_user"
                for row in overlay.get("modules") or []
            ),
        },
        "portCoverage": {
            "semanticPortCount": len(normalized.get("semanticPorts") or []),
            "normalizedPortCount": sum(
                bool(row.get("normalizedInterface"))
                for row in normalized.get("semanticPorts") or []
            ),
        },
        "compatibility": {
            "status": substitution_report.get("status"),
            "blockers": substitution_report.get("blockers") or [],
            "canonicalInterfaceClass": substitution_report.get(
                "canonicalInterfaceClass"
            ),
            "locatingFeatureGeometry": substitution_report.get(
                "locatingFeatureGeometry"
            ),
            "derivedTemplateId": substitution_report.get("derivedTemplateId"),
        },
        "compiledTransaction": {
            "contextInstanceCount": len(
                (preview.get("context") or {}).get("instances") or []
            ),
            "contextConnectionCount": len(
                (preview.get("context") or {}).get("connections") or []
            ),
            "packetCount": (preview.get("cadTransactionManifest") or {}).get(
                "packetCount"
            ),
            "mateCount": sum(
                len(connection.get("mates") or [])
                for packet in (
                    (preview.get("cadTransactionManifest") or {}).get("packets")
                    or []
                )
                for connection in packet.get("connections") or []
            ),
            "cadStarted": preview.get("cadStarted"),
            "collisionStatus": preview.get("collisionStatus"),
        },
        "timings": {key: round(value, 6) for key, value in timings.items()},
        "artifacts": {key: str(path) for key, path in paths.items() if key != "summary"},
        "boundary": {
            "solidWorksExecuted": False,
            "collisionOrBrepEvaluated": False,
            "statement": "本构建只验证角色、端口、兼容性与CAD事务编译；实体执行另行触发。",
        },
    }
    _write_json(paths["summary"], summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

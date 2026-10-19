from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_module_catalog import validate_global_module_catalog  # noqa: E402
from demo_backend.global_relation_semantics import (  # noqa: E402
    normalize_template_relation_profile,
)


DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json"
)
DEFAULT_CLOSURE = ROOT / (
    "demo/global_assembly_catalog/v1/relation-v2-preview/"
    "project01-gn00-standalone-parallel-closure.json"
)
DEFAULT_SS00_RESULT = ROOT / (
    "demo/global_assembly_catalog/v1/relation-v2-preview/"
    "project01-ss00-current-insert-v1/cad-result.json"
)
DEFAULT_GN00_RESULT = ROOT / (
    "demo/global_assembly_catalog/v1/relation-v2-preview/"
    "project01-gn00-current-insert-v2/cad-result.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_catalog/v1/relation-v2-preview/"
    "project01-driving-release-evidence.json"
)
TEMPLATE_IDS = {
    "SS00_to_JJ00_three_datum_installation": (
        "template/project01/ss00-to-jj00-three-datum-installation/c087ea93d1"
    ),
    "GN00_to_JJ00_primary": "template/project01/gn00-to-jj00-primary/8ff522aead",
    "GN00_SS00_standalone_parallel": (
        "template/project01/gn00-ss00-standalone-parallel/5df3a32e59"
    ),
}


class Project01DrivingCandidateError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Project01DrivingCandidateError(f"JSON根节点必须是对象：{path}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _independent_insert_passed(payload: dict[str, Any], expected_mates: int) -> bool:
    tool = payload.get("toolResult") or {}
    mate_results = tool.get("MateResults") or []
    verifications = tool.get("MateVerifications") or []
    return bool(
        payload.get("schemaVersion") == "checkpoint-selected-face-context-insert-run/v1"
        and payload.get("success") is True
        and payload.get("sourceAssemblyUnchanged") is True
        and payload.get("outputClosedAfterVerification") is True
        and payload.get("targetSourceClosedAfterVerification") is True
        and payload.get("targetSourceSessionClean") is True
        and payload.get("outputAssemblySha256")
        and tool.get("Success") is True
        and tool.get("ExecutionMode") == "context_incremental_insert"
        and tool.get("OriginalComponentRemoved") is True
        and tool.get("IndependentComponentInserted") is True
        and tool.get("TargetCaseAnchored") is False
        and int(tool.get("RequestedMateCount") or 0) == expected_mates
        and int(tool.get("CreatedMateCount") or 0) == expected_mates
        and tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True
        and tool.get("TargetFullyConstrained") is True
        and tool.get("TargetConstraintStateAccepted") is True
        and tool.get("MateSolveClean") is True
        and tool.get("ComponentSemanticsMatch") is True
        and len(mate_results) == expected_mates
        and all(row.get("Success") is True for row in mate_results)
        and len(verifications) == expected_mates
        and all(
            row.get("Found") is True
            and row.get("TypeMatches") is True
            and row.get("AlignmentMatches") is True
            and row.get("DistanceMatches") is True
            and row.get("AngleMatches") is True
            and row.get("AdvancedOptionsMatch") is True
            for row in verifications
        )
    )


def build_evidence(
    catalog: dict[str, Any],
    closure: dict[str, Any],
    ss00_result: dict[str, Any],
    gn00_result: dict[str, Any],
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    templates = {
        str(row.get("legacyTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    missing = sorted(set(TEMPLATE_IDS) - set(templates))
    if missing:
        raise Project01DrivingCandidateError(
            "候选目录缺少Project01驱动模板：" + ", ".join(missing)
        )
    for legacy_id, expected_id in TEMPLATE_IDS.items():
        if templates[legacy_id].get("globalTemplateId") != expected_id:
            raise Project01DrivingCandidateError(f"模板ID发生变化：{legacy_id}")
        if normalize_template_relation_profile(templates[legacy_id]).get(
            "drivesPlacement"
        ) is not True:
            raise Project01DrivingCandidateError(f"模板未声明驱动位姿：{legacy_id}")

    closure_value = closure.get("closure") or {}
    constraint = closure_value.get("constraintAssessment") or {}
    checks = {
        "catalogDigestMatchesClosure": (
            closure.get("catalogDigest") == catalog.get("catalogDigest")
        ),
        "declaredCombinationClosed": (
            closure_value.get("status") == "passed"
            and constraint.get("state") == "closed_by_declared_template_combination"
            and constraint.get("expectedResidualDof") == 0
        ),
        "ss00IndependentInsertPassed": _independent_insert_passed(ss00_result, 3),
        "gn00IndependentInsertPassed": _independent_insert_passed(gn00_result, 3),
        "exactAuthorizedTemplateSet": (
            {
                templates[value]["globalTemplateId"] for value in TEMPLATE_IDS
            }
            == set(TEMPLATE_IDS.values())
        ),
    }
    status = "ready" if all(checks.values()) else "blocked"
    derivations = []
    for legacy_id, template_id in TEMPLATE_IDS.items():
        derivations.append(
            {
                "entry": {
                    "mode": "register_scoped_driving_bundle",
                    "sourceProjectId": "project01",
                    "legacyTemplateId": legacy_id,
                },
                "result": {
                    "derivedGlobalTemplateId": template_id,
                    "drivingScope": (
                        "project01_JJ00_HL00_SS00_then_GN00_declared_bundle_only"
                    ),
                },
            }
        )
    return {
        "schemaVersion": "project01-scoped-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "sourceCatalogPath": _relative(DEFAULT_CATALOG),
        "outputCatalogDigest": catalog["catalogDigest"],
        "authorizedDrivingTemplateIds": sorted(TEMPLATE_IDS.values()),
        "checks": checks,
        "derivations": derivations,
        "sourceEvidence": {
            "declaredCombinationClosurePath": _relative(DEFAULT_CLOSURE),
            "ss00IndependentInsertPath": _relative(DEFAULT_SS00_RESULT),
            "gn00IndependentInsertPath": _relative(DEFAULT_GN00_RESULT),
        },
        "solidWorksExecuted": True,
        "collisionStatus": "not_evaluated",
        "statement": (
            "Project01首包SS00与后续GN00均由独立子装配体、非case-anchor初始位姿"
            "完成定位；GN00主定位与防转模板必须作为声明组合共同使用。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Project01 scoped driving release evidence."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    parser.add_argument("--ss00-result", type=Path, default=DEFAULT_SS00_RESULT)
    parser.add_argument("--gn00-result", type=Path, default=DEFAULT_GN00_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    evidence = build_evidence(
        _read(args.catalog),
        _read(args.closure),
        _read(args.ss00_result),
        _read(args.gn00_result),
    )
    evidence["sourceCatalogPath"] = _relative(args.catalog)
    evidence["sourceEvidence"] = {
        "declaredCombinationClosurePath": _relative(args.closure),
        "ss00IndependentInsertPath": _relative(args.ss00_result),
        "gn00IndependentInsertPath": _relative(args.gn00_result),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())

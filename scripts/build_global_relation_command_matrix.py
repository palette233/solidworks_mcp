#!/usr/bin/env python3
"""Build the Stage-C command-level relation regression matrix."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.global_assembly_context import context_digest  # noqa: E402
from demo_backend.global_relation_edits import (  # noqa: E402
    GlobalRelationEditError,
    preview_global_relation_edit,
)


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def _definition(catalog: dict, project_id: str, token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias.get("projectId") == project_id
            and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    )


def _instance(context: dict, definition_id: str) -> str:
    return next(
        row["instanceId"]
        for row in context["instances"]
        if row["moduleDefinitionId"] == definition_id
    )


def _template(catalog: dict, legacy_id: str) -> dict:
    return next(
        row
        for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId") == legacy_id
    )


def _port(catalog: dict, alias: str) -> dict:
    return next(
        row for row in catalog["semanticPorts"] if alias in (row.get("aliases") or [])
    )


def _codes(preview: dict) -> list[str]:
    result = [str(row.get("code")) for row in preview.get("blockers") or []]
    for assessment in preview.get("relationCandidateAssessments") or []:
        result.extend(
            str(row.get("code"))
            for row in (assessment.get("relationAssessment") or {}).get("reasons") or []
        )
    return sorted(set(result))


def main() -> int:
    candidate = _load(
        "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json"
    )
    project01 = _load(
        "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.json"
    )
    project01_without_parallel = deepcopy(project01)
    parallel_id = _template(candidate, "GN00_SS00_standalone_parallel")[
        "globalTemplateId"
    ]
    project01_without_parallel["connections"] = [
        row
        for row in project01_without_parallel["connections"]
        if row["globalTemplateId"] != parallel_id
    ]
    project01_without_parallel["contextDigest"] = context_digest(
        project01_without_parallel
    )

    refreshed = _load(
        "demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json"
    )
    project02 = _load(
        "demo/global_assembly_contexts/project02-full-static-graph-catalog-refresh-v1.json"
    )
    project02_with_distance = _load(
        "demo/global_assembly_contexts/project02-full-static-graph-relation-edit-v1.json"
    )

    gn00 = _instance(project01, _definition(candidate, "project01", "GN00")["moduleDefinitionId"])
    jj00 = _instance(project01, _definition(candidate, "project01", "JJ00")["moduleDefinitionId"])
    ss00 = _instance(project01, _definition(candidate, "project01", "SS00")["moduleDefinitionId"])
    a500 = _instance(project02, _definition(refreshed, "project02", "A500")["moduleDefinitionId"])
    a700 = _instance(project02, _definition(refreshed, "project02", "A700")["moduleDefinitionId"])
    distance_connection = project02_with_distance["connections"][-1]["connectionId"]

    cases = [
        {
            "caseId": "project01-add-coincident",
            "catalog": candidate,
            "context": project01,
            "payload": {
                "operation": "add",
                "requirement": "让GN00与JJ00安装面重合",
                "instanceAId": gn00,
                "instanceBId": jj00,
                "globalTemplateId": _template(candidate, "GN00_JJ00_standalone_coincident")["globalTemplateId"],
                "portAId": _port(candidate, "GN00.primary_installation")["globalPortId"],
                "portBId": _port(candidate, "JJ00.gn00_primary")["globalPortId"],
            },
            "expectedStatus": "ready",
        },
        {
            "caseId": "project01-add-concentric",
            "catalog": candidate,
            "context": project01,
            "payload": {
                "operation": "add",
                "requirement": "让GN00与JJ00安装孔同轴",
                "instanceAId": gn00,
                "instanceBId": jj00,
                "globalTemplateId": _template(candidate, "GN00_JJ00_standalone_concentric")["globalTemplateId"],
                "portAId": _port(candidate, "GN00.primary_installation")["globalPortId"],
                "portBId": _port(candidate, "JJ00.gn00_primary")["globalPortId"],
            },
            "expectedStatus": "ready",
        },
        {
            "caseId": "project01-add-parallel",
            "catalog": candidate,
            "context": project01_without_parallel,
            "payload": {
                "operation": "add",
                "requirement": "让GN00防转面与SS00基准面平行",
                "instanceAId": gn00,
                "instanceBId": ss00,
                "globalTemplateId": parallel_id,
                "portAId": _port(candidate, "GN00.anti_rotation")["globalPortId"],
                "portBId": _port(candidate, "SS00.gn00_anti_rotation")["globalPortId"],
            },
            "expectedStatus": "ready",
        },
        {
            "caseId": "project02-add-registered-50mm",
            "catalog": refreshed,
            "context": project02,
            "payload": {"operation": "add", "requirement": "让A500与A700保持50mm间距", "instanceAId": a500, "instanceBId": a700},
            "expectedStatus": "ready",
        },
        {
            "caseId": "project02-reject-unregistered-60mm",
            "catalog": refreshed,
            "context": project02,
            "payload": {"operation": "add", "requirement": "让A500与A700保持60mm间距", "instanceAId": a500, "instanceBId": a700},
            "expectedStatus": "blocked",
            "expectedCode": "REQUESTED_DISTANCE_NOT_SUPPORTED_BY_TEMPLATE",
        },
        {
            "caseId": "reject-ambiguous-align",
            "catalog": refreshed,
            "context": project02,
            "payload": {"operation": "add", "requirement": "把A500和A700对齐", "instanceAId": a500, "instanceBId": a700},
            "expectedStatus": "blocked",
            "expectedCode": "ALIGNMENT_KIND_REQUIRED",
        },
        {
            "caseId": "reject-duplicate-relation",
            "catalog": refreshed,
            "context": project02_with_distance,
            "payload": {"operation": "add", "requirement": "让A500与A700保持50mm间距", "instanceAId": a500, "instanceBId": a700},
            "expectedStatus": "blocked",
            "expectedCode": "RELATION_ALREADY_EXISTS",
        },
        {
            "caseId": "reject-compound-installation-as-standalone",
            "catalog": candidate,
            "context": project01,
            "payload": {
                "operation": "add",
                "requirement": "只让GN00与JJ00安装面重合",
                "instanceAId": gn00,
                "instanceBId": jj00,
                "globalTemplateId": _template(candidate, "GN00_to_JJ00_primary")["globalTemplateId"],
            },
            "expectedStatus": "blocked",
            "expectedCode": "STANDALONE_RELATION_TEMPLATE_REQUIRED",
        },
        {
            "caseId": "reject-unknown-instance",
            "catalog": refreshed,
            "context": project02,
            "payload": {"operation": "add", "requirement": "让两个面保持50mm间距", "instanceAId": "unknown-instance", "instanceBId": a700},
            "expectedStatus": "error",
            "expectedCode": "RELATION_ENDPOINT_INSTANCE_NOT_FOUND",
        },
        {
            "caseId": "project02-delete-relation",
            "catalog": refreshed,
            "context": project02_with_distance,
            "payload": {"operation": "delete", "connectionId": distance_connection},
            "expectedStatus": "ready",
        },
        {
            "caseId": "project02-reject-replace-with-60mm",
            "catalog": refreshed,
            "context": project02_with_distance,
            "payload": {"operation": "replace", "connectionId": distance_connection, "requirement": "改为60mm间距"},
            "expectedStatus": "blocked",
            "expectedCode": "REQUESTED_DISTANCE_NOT_SUPPORTED_BY_TEMPLATE",
        },
        {
            "caseId": "reject-catalog-digest-mismatch",
            "catalog": candidate,
            "context": project02,
            "payload": {"operation": "add", "requirement": "保持50mm间距", "instanceAId": a500, "instanceBId": a700},
            "expectedStatus": "error",
            "expectedCode": "CATALOG_DIGEST_MISMATCH",
        },
    ]

    rows = []
    for case in cases:
        try:
            preview = preview_global_relation_edit(
                case["catalog"], case["context"], case["payload"]
            )
            actual_status = preview["status"]
            codes = _codes(preview)
        except GlobalRelationEditError as exc:
            actual_status = "error"
            message = str(exc)
            if "摘要不一致" in message:
                codes = ["CATALOG_DIGEST_MISMATCH"]
            elif "instanceAId" in message or "instanceBId" in message:
                codes = ["RELATION_ENDPOINT_INSTANCE_NOT_FOUND"]
            else:
                codes = ["GLOBAL_RELATION_EDIT_ERROR"]
        passed = actual_status == case["expectedStatus"] and (
            not case.get("expectedCode") or case["expectedCode"] in codes
        )
        rows.append(
            {
                "caseId": case["caseId"],
                "expectedStatus": case["expectedStatus"],
                "actualStatus": actual_status,
                "expectedCode": case.get("expectedCode"),
                "observedCodes": codes,
                "passed": passed,
            }
        )

    report = {
        "schemaVersion": "global-relation-command-matrix/v1",
        "caseCount": len(rows),
        "passedCount": sum(1 for row in rows if row["passed"]),
        "failedCount": sum(1 for row in rows if not row["passed"]),
        "cases": rows,
        "solidWorksExecuted": False,
        "collisionStatus": "not_evaluated",
    }
    output = (
        ROOT
        / "demo/global_assembly_catalog/v1/relation-v2-preview/global_relation_command_matrix.json"
    )
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), **report}, ensure_ascii=False, indent=2))
    return 0 if report["failedCount"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

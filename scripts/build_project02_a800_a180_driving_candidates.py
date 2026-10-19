from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import assess_driving_insert_evidence  # noqa: E402
from demo_backend.global_module_catalog import (  # noqa: E402
    build_global_module_catalog,
    validate_global_module_catalog,
)


AUDIT_ROOT = ROOT / "demo/semantic_ports/project02_a800_a180_dof_audit_v1"
SOURCE_PACKAGES = {
    "A800": ROOT / "demo/semantic_ports/project02_A800_case_anchored_installation_v1",
    "A180": ROOT / "demo/semantic_ports/project02_A180_scanner_installation_v1",
    "A500": ROOT / "demo/semantic_ports/project02_A500_full_installation_v2",
    "A700": ROOT / "demo/semantic_ports/project02_service_installations_v1/A700",
    "A300": ROOT / "demo/semantic_ports/project02_service_installations_v1/A300",
    "A200": ROOT / "demo/semantic_ports/project02_a200_t401_installations_v1/A200",
    "A100": ROOT / "demo/semantic_ports/project02_service_installations_v1/A100",
}
EFFECTIVE_GRAPHS = {
    "A800": AUDIT_ROOT / "a800-nonanchor-effective.json",
    "A180": AUDIT_ROOT / "a180-nonanchor-effective.json",
    "A500": ROOT / (
        "demo/semantic_ports/project02_a500_nonanchor_v1/"
        "a500-nonanchor-effective.json"
    ),
    "A700": ROOT / (
        "demo/semantic_ports/project02_a700_nonanchor_v1/"
        "a700-nonanchor-effective.json"
    ),
    "A300": ROOT / (
        "demo/semantic_ports/project02_a300_nonanchor_v1/"
        "a300-nonanchor-effective.json"
    ),
    "A200": ROOT / (
        "demo/semantic_ports/project02_a200_nonanchor_v1/"
        "a200-nonanchor-effective.json"
    ),
    "A100": ROOT / (
        "demo/semantic_ports/project02_a100_nonanchor_v1/"
        "a100-nonanchor-effective.json"
    ),
}
CHECKPOINTS = {
    "A800": AUDIT_ROOT / "project02-a800-nonanchor-checkpoint-v2.result.json",
    "A180": AUDIT_ROOT / "project02-a800-a180-nonanchor-checkpoint-v3.result.json",
    "A500": ROOT / (
        "demo/semantic_ports/project02_a500_nonanchor_v1/"
        "project02-a500-nonanchor-checkpoint-v2.result.json"
    ),
    "A700": ROOT / (
        "demo/semantic_ports/project02_a700_nonanchor_v1/"
        "project02-a700-nonanchor-checkpoint-v1.result.json"
    ),
    "A300": ROOT / (
        "demo/semantic_ports/project02_a300_nonanchor_v1/"
        "project02-a300-nonanchor-checkpoint-v1.result.json"
    ),
    "A200": ROOT / (
        "demo/semantic_ports/project02_a200_nonanchor_v1/"
        "project02-a200-nonanchor-checkpoint-v1.result.json"
    ),
    "A100": ROOT / (
        "demo/semantic_ports/project02_a100_nonanchor_v1/"
        "project02-a100-nonanchor-checkpoint-v1.result.json"
    ),
}
DEFAULT_OUTPUT_ROOT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-seven-addon-driving-v6"
)
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.project02-seven-addon-driving-v6-preview.json"
)
DEFAULT_EVIDENCE = DEFAULT_OUTPUT_ROOT / "candidate-evidence.json"


class Project02DrivingCandidateError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Project02DrivingCandidateError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _face(catalog: dict[str, Any], token: str, body: int, face: int) -> dict[str, Any]:
    rows = [
        copy.deepcopy(row)
        for row in catalog.get("Endpoints") or []
        if str((row.get("Endpoint") or {}).get("ModuleToken") or "").upper()
        == token
        and int((row.get("Endpoint") or {}).get("BodyIndex", -1)) == body
        and int((row.get("Endpoint") or {}).get("FaceIndexInBody", -1)) == face
    ]
    if len(rows) != 1:
        raise Project02DrivingCandidateError(
            f"{token} BodyIndex={body}, FaceIndexInBody={face}命中{len(rows)}项。"
        )
    return rows[0]


def _reference(endpoint: dict[str, Any]) -> str:
    return str(endpoint.get("SourceAssemblyPersistentReferenceBase64") or "")


def _ensure_endpoint(catalog: dict[str, Any], row: dict[str, Any]) -> str:
    reference = _reference(row.get("Endpoint") or {})
    matches = [
        str(existing.get("EndpointId") or "")
        for existing in catalog.get("Endpoints") or []
        if _reference(existing.get("Endpoint") or {}) == reference
    ]
    if len(matches) == 1 and matches[0]:
        return matches[0]
    if matches:
        raise Project02DrivingCandidateError("稳定引用在端点目录中重复。")
    token = str((row.get("Endpoint") or {}).get("ModuleToken") or "").lower()
    row["EndpointId"] = f"face:{token}:locator:{_digest(row['Endpoint'])[:16]}"
    catalog.setdefault("Endpoints", []).append(row)
    catalog["EndpointCount"] = len(catalog.get("Endpoints") or [])
    return row["EndpointId"]


def _endpoint_id(catalog: dict[str, Any], endpoint: dict[str, Any]) -> str:
    reference = _reference(endpoint)
    matches = [
        str(row.get("EndpointId") or "")
        for row in catalog.get("Endpoints") or []
        if _reference(row.get("Endpoint") or {}) == reference
    ]
    if len(matches) != 1 or not matches[0]:
        raise Project02DrivingCandidateError(
            f"{endpoint.get('ModuleToken')}面端点在合并目录中命中{len(matches)}项。"
        )
    return matches[0]


def _mate_steps(
    graph: dict[str, Any], endpoint_catalog: dict[str, Any], target: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    steps: list[dict[str, Any]] = []
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    for mate_index, mate in enumerate(graph.get("Mates") or [], start=1):
        roles: list[dict[str, str]] = []
        local_counts = {target: 0, "A600": 0}
        for endpoint in mate.get("Endpoints") or []:
            token = str(endpoint.get("ModuleToken") or "").upper()
            if token not in local_counts:
                raise Project02DrivingCandidateError(
                    f"配合{mate.get('MateName')}出现范围外模组：{token}。"
                )
            local_counts[token] += 1
            side = "A" if token == target else "B"
            side_name = "target" if side == "A" else "context"
            role = f"mate_{mate_index}_{side_name}_{local_counts[token]}"
            binding = {"role": role, "endpointId": _endpoint_id(endpoint_catalog, endpoint)}
            (target_bindings if side == "A" else context_bindings).append(binding)
            roles.append({"side": side, "role": role})
        step: dict[str, Any] = {
            "mateName": mate["MateName"],
            "mateType": mate["MateType"],
            "mateTypeName": mate["MateTypeName"],
            "alignment": mate["Alignment"],
            "alignmentName": mate["AlignmentName"],
            "endpointRoles": roles,
        }
        if mate.get("Distance") is not None:
            step["distanceMeters"] = mate["Distance"]
        if mate.get("Angle") is not None:
            step["angleRadians"] = mate["Angle"]
        if mate.get("AdvancedOptions") is not None:
            step["advancedOptions"] = copy.deepcopy(mate["AdvancedOptions"])
        steps.append(step)
    return steps, target_bindings, context_bindings


def build_candidate(target: str, package_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    target = target.upper()
    if target not in SOURCE_PACKAGES:
        raise Project02DrivingCandidateError(f"不支持的Project02目标：{target}")
    source = SOURCE_PACKAGES[target]
    candidate = copy.deepcopy(_read(source / "semantic_port_catalog.json"))
    endpoint_catalog = copy.deepcopy(_read(source / "face_endpoint_catalog.json"))
    graph = _read(EFFECTIVE_GRAPHS[target])
    checkpoint = _read(CHECKPOINTS[target])
    expected_count = len(graph.get("Mates") or [])
    assessment = assess_driving_insert_evidence(
        checkpoint, expected_mate_count=expected_count
    )
    if assessment.get("checkpointPassed") is not True:
        raise Project02DrivingCandidateError(
            f"{target}严格CAD检查点未通过：{', '.join(assessment.get('blockers') or [])}"
        )

    if target == "A800":
        a800_faces = _read(AUDIT_ROOT / "a800-mount-leaf-face-catalog.json")
        a600_faces = _read(AUDIT_ROOT / "a600-a180-support-leaf-face-catalog.json")
        _ensure_endpoint(endpoint_catalog, _face(a800_faces, "A800", 0, 106))
        _ensure_endpoint(endpoint_catalog, _face(a600_faces, "A600", 0, 0))

    steps, target_bindings, context_bindings = _mate_steps(
        graph, endpoint_catalog, target
    )
    ports = {
        str(row.get("moduleToken") or "").upper(): row
        for row in candidate.get("ports") or []
        if str(row.get("moduleToken") or "").upper() in {target, "A600"}
        and str(row.get("category") or "").casefold() == "mechanical"
    }
    if set(ports) != {target, "A600"}:
        raise Project02DrivingCandidateError(f"{target}语义包安装端口范围异常：{sorted(ports)}")
    candidate["ports"] = [ports[target], ports["A600"]]
    ports[target]["endpointBindings"] = target_bindings
    ports["A600"]["endpointBindings"] = context_bindings
    ports[target]["status"] = "cad-verified-nonanchor-demo"
    ports["A600"]["status"] = "cad-verified-nonanchor-demo"

    template = copy.deepcopy((candidate.get("connectionTemplates") or [])[0])
    template["templateId"] = f"{target}_to_A600_nonanchor_driving_v1"
    template["mateSteps"] = steps
    template["constraintEffect"] = {
        "purpose": f"Drive the verified Project02 {target}-to-A600 exact mate bundle.",
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "closed_by_nonanchor_cad_checkpoint",
        "drivingAuthorization": "candidate_only_not_released",
        "exactMateBundleRequired": True,
        "residualDofScope": "external_module_placement",
        "internalFlexibilityPreserved": target in {"A700", "A200", "A100"},
        "parameterAuthority": (
            "prototype_estimate" if target == "A800" else "source_mate_bundle"
        ),
        "productionReady": False,
    }
    candidate["schemaVersion"] = "semantic-port-catalog/v2-candidate"
    candidate["catalogPurpose"] = (
        f"Project02 {target}/A600 portable non-anchor driving candidate proven "
        "by a strict saved-and-reopened CAD checkpoint."
    )
    candidate["endpointCatalogPath"] = "face_endpoint_catalog.json"
    candidate["effectiveMateGraphPath"] = _relative(
        package_dir / "assembly_plan_effective.json"
    )
    candidate["connectionTemplates"] = [template]
    candidate["readOnlySourceRelations"] = []
    candidate["drivingScope"] = {
        "status": "candidate_only_not_released",
        "allowedModuleTokens": ["A600", target],
        "exactMateBundleRequired": True,
        "mateNames": [row["mateName"] for row in steps],
        "checkpointPath": _relative(CHECKPOINTS[target]),
        "caseAnchorAllowed": False,
        "parameterAuthority": template["constraintEffect"]["parameterAuthority"],
        "productionReady": False,
    }
    if target == "A180":
        candidate["upgradedSourceRelations"] = [
            {
                "mateName": "槽口3",
                "previousMode": "evidence_only",
                "candidateMode": "driving_as_part_of_exact_bundle",
                "reason": "槽口端点、Free槽口参数及保存重开后的完全约束状态均已由CAD验证。",
            }
        ]
    elif target == "A800":
        candidate["upgradedSourceRelations"] = [
            {
                "mateName": "A800_LOCATING_DISTANCE_X",
                "candidateMode": "driving_as_part_of_exact_bundle",
                "parameterAuthority": "prototype_estimate",
                "distanceMeters": steps[-1].get("distanceMeters"),
                "productionReady": False,
            }
        ]

    package_dir.mkdir(parents=True, exist_ok=True)
    _write(package_dir / "semantic_port_catalog.json", candidate)
    _write(package_dir / "face_endpoint_catalog.json", endpoint_catalog)
    _write(package_dir / "assembly_plan_effective.json", graph)
    return candidate, assessment


def build_catalog(output_root: Path) -> dict[str, Any]:
    paths = [
        output_root / token / "semantic_port_catalog.json"
        for token in ("A800", "A180", "A500", "A700", "A300", "A200", "A100")
    ]
    catalog = build_global_module_catalog(
        ROOT, additional_semantic_catalog_paths=paths
    )
    validate_global_module_catalog(catalog)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(
        description="构建Project02七个附加模组的无锚点驱动候选包。"
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    assessments: dict[str, dict[str, Any]] = {}
    targets = ("A800", "A180", "A500", "A700", "A300", "A200", "A100")
    for target in targets:
        _, assessments[target] = build_candidate(target, output_root / target)
    catalog = build_catalog(output_root)
    rows: list[dict[str, Any]] = []
    for target in targets:
        source = _relative(output_root / target / "semantic_port_catalog.json")
        matches = [
            row
            for row in catalog.get("connectionTemplates") or []
            if (row.get("provenance") or {}).get("semanticCatalogPath") == source
        ]
        if len(matches) != 1:
            raise Project02DrivingCandidateError(
                f"{target}预期一个候选模板，实际为{len(matches)}。"
            )
        template = matches[0]
        rows.append(
            {
                "moduleToken": target,
                "packagePath": _relative(output_root / target),
                "legacyTemplateId": template.get("legacyTemplateId"),
                "globalTemplateId": template.get("globalTemplateId"),
                "mateCount": len(template.get("mateSteps") or []),
                "checkpointPath": _relative(CHECKPOINTS[target]),
                "checkpointAssessment": assessments[target],
            }
        )
    evidence = {
        "schemaVersion": "project02-seven-addon-driving-candidate/v6",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project02",
        "sourceCatalogPath": _relative(args.catalog_output.resolve()),
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "targetCount": len(rows),
        "targets": rows,
        "collisionStatus": "not_evaluated_optional_postcheck",
    }
    _write(args.catalog_output.resolve(), catalog)
    _write(args.evidence_output.resolve(), evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

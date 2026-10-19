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


SEVEN_ROOT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-seven-addon-driving-v6"
)
SOURCE_ROOT = ROOT / "demo/semantic_ports/project02_a200_t401_installations_v1"
LOCATOR_ROOT = ROOT / "demo/semantic_ports/project02_t401_locator_discovery_v1"
DEFAULT_OUTPUT_ROOT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-nine-addon-driving-v7"
)
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.project02-nine-addon-driving-v7-preview.json"
)
DEFAULT_EVIDENCE = DEFAULT_OUTPUT_ROOT / "candidate-evidence.json"

SPECS = {
    "T401-1": {
        "context": "A600",
        "source": SOURCE_ROOT / "T401-1",
        "graph": LOCATOR_ROOT / "t401-1-nonanchor-effective.json",
        "checkpoint": LOCATOR_ROOT / "cad/project02-t401-1-nonanchor-checkpoint-v1.result.json",
        "templateId": "T401_1_to_A600_nonanchor_driving_v1",
        "purpose": "Drive the first Project02 glue-supply occurrence against A600.",
    },
    "T401-2": {
        "context": "A200",
        "source": SOURCE_ROOT / "T401-2",
        "graph": LOCATOR_ROOT / "t401-2-nonanchor-effective.json",
        "checkpoint": LOCATOR_ROOT / "cad/project02-t401-2-nonanchor-checkpoint-v1.result.json",
        "templateId": "T401_2_to_A200_nonanchor_driving_v1",
        "purpose": "Drive the second Project02 glue-supply occurrence against A200.",
    },
}


class Project02T401CandidateError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Project02T401CandidateError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        # Tests may build an isolated candidate package outside the workspace.
        # Production publication still writes below ROOT and therefore records
        # a portable workspace-relative path.
        return str(resolved)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _reference(endpoint: dict[str, Any]) -> str:
    return str(endpoint.get("SourceAssemblyPersistentReferenceBase64") or "")


def _merge_endpoint_catalogs(base: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    rows = list(result.get("Endpoints") or [])
    references = {
        _reference(row.get("Endpoint") or {}): str(row.get("EndpointId") or "")
        for row in rows
        if _reference(row.get("Endpoint") or {})
    }
    sources = (
        LOCATOR_ROOT / "project02_T401_instance1_face_catalog_v1.json",
        LOCATOR_ROOT / "project02_T401_instance2_face_catalog_v1.json",
        LOCATOR_ROOT / "a600-t401-support-leaf-face-catalog.json",
        LOCATOR_ROOT / "a200-support-leaf-face-catalog.json",
    )
    # The first two catalogs historically live in mate_reconstruction_pipeline.
    sources = tuple(
        path
        if path.is_file()
        else ROOT / "demo/mate_reconstruction_pipeline" / path.name
        for path in sources
    )
    for source in sources:
        for row in _read(source).get("Endpoints") or []:
            reference = _reference(row.get("Endpoint") or {})
            if not reference or reference in references:
                continue
            item = copy.deepcopy(row)
            token = str((item.get("Endpoint") or {}).get("ModuleToken") or "").lower()
            item["EndpointId"] = f"face:{token}:locator:{_digest(item['Endpoint'])[:16]}"
            references[reference] = item["EndpointId"]
            rows.append(item)
    result["Endpoints"] = rows
    result["EndpointCount"] = len(rows)
    return result


def _endpoint_id(catalog: dict[str, Any], endpoint: dict[str, Any]) -> str:
    reference = _reference(endpoint)
    matches = [
        str(row.get("EndpointId") or "")
        for row in catalog.get("Endpoints") or []
        if _reference(row.get("Endpoint") or {}) == reference
    ]
    if len(matches) != 1 or not matches[0]:
        raise Project02T401CandidateError(
            f"{endpoint.get('ModuleToken')}端点在合并面目录中命中{len(matches)}项。"
        )
    return matches[0]


def _mate_steps(
    graph: dict[str, Any], endpoint_catalog: dict[str, Any], context: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    steps: list[dict[str, Any]] = []
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    for mate_index, mate in enumerate(graph.get("Mates") or [], start=1):
        counts = {"T401": 0, context: 0}
        roles: list[dict[str, str]] = []
        for endpoint in mate.get("Endpoints") or []:
            token = str(endpoint.get("ModuleToken") or "").upper()
            if token not in counts:
                raise Project02T401CandidateError(
                    f"配合{mate.get('MateName')}出现范围外模组：{token}。"
                )
            counts[token] += 1
            side = "A" if token == "T401" else "B"
            side_name = "target" if side == "A" else "context"
            role = f"mate_{mate_index}_{side_name}_{counts[token]}"
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


def build_candidate(name: str, package_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = SPECS[name]
    source = Path(spec["source"])
    context = str(spec["context"])
    candidate = copy.deepcopy(_read(source / "semantic_port_catalog.json"))
    endpoint_catalog = _merge_endpoint_catalogs(
        _read(source / "face_endpoint_catalog.json")
    )
    graph = _read(Path(spec["graph"]))
    checkpoint = _read(Path(spec["checkpoint"]))
    assessment = assess_driving_insert_evidence(
        checkpoint, expected_mate_count=len(graph.get("Mates") or [])
    )
    if assessment.get("checkpointPassed") is not True:
        raise Project02T401CandidateError(
            f"{name}严格CAD检查点未通过：{', '.join(assessment.get('blockers') or [])}"
        )

    steps, target_bindings, context_bindings = _mate_steps(
        graph, endpoint_catalog, context
    )
    ports = {
        str(row.get("moduleToken") or "").upper(): copy.deepcopy(row)
        for row in candidate.get("ports") or []
        if str(row.get("moduleToken") or "").upper() in {"T401", context}
        and str(row.get("category") or "").casefold() == "mechanical"
    }
    if set(ports) != {"T401", context}:
        raise Project02T401CandidateError(
            f"{name}语义包安装端口范围异常：{sorted(ports)}"
        )
    ports["T401"]["endpointBindings"] = target_bindings
    ports[context]["endpointBindings"] = context_bindings
    ports["T401"]["status"] = "cad-verified-nonanchor-demo"
    ports[context]["status"] = "cad-verified-nonanchor-demo"
    candidate["ports"] = [ports["T401"], ports[context]]

    template = copy.deepcopy((candidate.get("connectionTemplates") or [])[0])
    template["templateId"] = str(spec["templateId"])
    template["mateSteps"] = steps
    template["constraintEffect"] = {
        "purpose": str(spec["purpose"]),
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "closed_by_nonanchor_cad_checkpoint",
        "drivingAuthorization": "candidate_only_not_released",
        "exactMateBundleRequired": True,
        "residualDofScope": "external_module_placement",
        "internalFlexibilityPreserved": False,
        "parameterAuthority": "prototype_estimate",
        "productionReady": False,
    }
    candidate["schemaVersion"] = "semantic-port-catalog/v2-candidate"
    candidate["catalogPurpose"] = (
        f"Project02 {name} portable non-anchor driving candidate proven by a "
        "strict saved-and-reopened CAD checkpoint."
    )
    candidate["endpointCatalogPath"] = "face_endpoint_catalog.json"
    candidate["effectiveMateGraphPath"] = _relative(
        package_dir / "assembly_plan_effective.json"
    )
    candidate["connectionTemplates"] = [template]
    candidate["readOnlySourceRelations"] = []
    candidate["drivingScope"] = {
        "status": "candidate_only_not_released",
        "allowedModuleTokens": [context, "T401"],
        "exactMateBundleRequired": True,
        "mateNames": [row["mateName"] for row in steps],
        "checkpointPath": _relative(Path(spec["checkpoint"])),
        "caseAnchorAllowed": False,
        "parameterAuthority": "prototype_estimate",
        "productionReady": False,
        "occurrenceRole": name,
    }
    candidate["upgradedSourceRelations"] = [
        {
            "candidateMode": "driving_as_part_of_exact_bundle",
            "parameterAuthority": "prototype_estimate",
            "occurrenceRole": name,
            "productionReady": False,
        }
    ]

    package_dir.mkdir(parents=True, exist_ok=True)
    _write(package_dir / "semantic_port_catalog.json", candidate)
    _write(package_dir / "face_endpoint_catalog.json", endpoint_catalog)
    _write(package_dir / "assembly_plan_effective.json", graph)
    return candidate, assessment


def build_catalog(output_root: Path) -> dict[str, Any]:
    seven_paths = [
        SEVEN_ROOT / token / "semantic_port_catalog.json"
        for token in ("A800", "A180", "A500", "A700", "A300", "A200", "A100")
    ]
    t401_paths = [
        output_root / name / "semantic_port_catalog.json" for name in SPECS
    ]
    catalog = build_global_module_catalog(
        ROOT, additional_semantic_catalog_paths=(*seven_paths, *t401_paths)
    )
    validate_global_module_catalog(catalog)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(
        description="构建Project02两个T401实例的无锚点驱动候选包。"
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    assessments: dict[str, dict[str, Any]] = {}
    for name in SPECS:
        _, assessments[name] = build_candidate(name, output_root / name)
    catalog = build_catalog(output_root)
    rows: list[dict[str, Any]] = []
    for name, spec in SPECS.items():
        source = _relative(output_root / name / "semantic_port_catalog.json")
        matches = [
            row
            for row in catalog.get("connectionTemplates") or []
            if (row.get("provenance") or {}).get("semanticCatalogPath") == source
        ]
        if len(matches) != 1:
            raise Project02T401CandidateError(
                f"{name}预期一个候选模板，实际为{len(matches)}。"
            )
        template = matches[0]
        rows.append(
            {
                "occurrenceRole": name,
                "moduleToken": "T401",
                "contextModuleToken": spec["context"],
                "packagePath": _relative(output_root / name),
                "legacyTemplateId": template.get("legacyTemplateId"),
                "globalTemplateId": template.get("globalTemplateId"),
                "mateCount": len(template.get("mateSteps") or []),
                "checkpointPath": _relative(Path(spec["checkpoint"])),
                "checkpointAssessment": assessments[name],
            }
        )
    evidence = {
        "schemaVersion": "project02-nine-addon-driving-candidate/v7",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project02",
        "sourceCatalogPath": _relative(args.catalog_output.resolve()),
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "targetCount": 9,
        "newOccurrenceCount": len(rows),
        "targets": rows,
        "collisionStatus": "not_evaluated_optional_postcheck",
    }
    _write(args.catalog_output.resolve(), catalog)
    _write(args.evidence_output.resolve(), evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

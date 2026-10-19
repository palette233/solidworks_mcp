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
from demo_backend.global_module_catalog import build_global_module_catalog, validate_global_module_catalog  # noqa: E402


SOURCE_PACKAGE = ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/N000"
SOURCE_SEMANTIC = SOURCE_PACKAGE / "semantic_port_catalog.json"
SOURCE_ENDPOINTS = SOURCE_PACKAGE / "face_endpoint_catalog.json"
EFFECTIVE_GRAPH = ROOT / (
    "demo/semantic_ports/project05_n000_locator_discovery_v1/"
    "n000-free-slot-plus-derived-x-distance-nonanchor-effective.json"
)
CHECKPOINT = ROOT / (
    "demo/semantic_ports/project05_n000_locator_discovery_v1/cad/"
    "project05-n000-derived-x-distance-checkpoint-v2.result.json"
)
D000_CANDIDATE = ROOT / (
    "demo/global_assembly_catalog/v1/driving-v1-preview/"
    "project05_D000_A000_scoped_driving_v2/semantic_port_catalog.json"
)
EXISTING_CANDIDATES = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v5"
)
P000_CANDIDATE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v6/P000/semantic_port_catalog.json"
)
DEFAULT_PACKAGE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v7/N000"
)
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.project05-nonanchor-driving-v7-preview.json"
)
DEFAULT_EVIDENCE = DEFAULT_PACKAGE.parent / "candidate-evidence.json"


class Project05N000CandidateError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Project05N000CandidateError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _reference(endpoint: dict[str, Any]) -> str:
    return str(endpoint.get("SourceAssemblyPersistentReferenceBase64") or "")


def _ensure_endpoint(
    catalog: dict[str, Any], endpoint: dict[str, Any]
) -> str:
    reference = _reference(endpoint)
    matches = [
        row for row in catalog.get("Endpoints") or []
        if _reference(row.get("Endpoint") or {}) == reference
    ]
    if len(matches) > 1:
        raise Project05N000CandidateError("持久引用在N000面目录中不唯一。")
    if matches:
        endpoint_id = str(matches[0].get("EndpointId") or "")
        if not endpoint_id:
            raise Project05N000CandidateError("已登记端点缺少EndpointId。")
        return endpoint_id
    if not reference:
        raise Project05N000CandidateError("新增端点缺少源装配持久引用。")
    token = str(endpoint.get("ModuleToken") or "").lower()
    endpoint_id = f"face:{token}:nonanchor:{_digest(endpoint)[:16]}"
    catalog.setdefault("Endpoints", []).append(
        {"EndpointId": endpoint_id, "Endpoint": copy.deepcopy(endpoint)}
    )
    return endpoint_id


def _mate_step(
    mate: dict[str, Any], endpoint_catalog: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    counts = {"N000": 0, "A000": 0}
    roles: list[dict[str, str]] = []
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    for endpoint in mate.get("Endpoints") or []:
        token = str(endpoint.get("ModuleToken") or "").upper()
        if token not in counts:
            raise Project05N000CandidateError(
                f"配合{mate.get('MateName')}出现范围外端点：{token}。"
            )
        counts[token] += 1
        side = "A" if token == "N000" else "B"
        role = f"{mate['MateName']}_{'target' if side == 'A' else 'context'}_{counts[token]}"
        binding = {"role": role, "endpointId": _ensure_endpoint(endpoint_catalog, endpoint)}
        (target_bindings if side == "A" else context_bindings).append(binding)
        roles.append({"side": side, "role": role})
    if len(roles) != 2 or counts != {"N000": 1, "A000": 1}:
        raise Project05N000CandidateError(
            f"配合{mate.get('MateName')}不是一对N000/A000端点。"
        )
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
    return step, target_bindings, context_bindings


def build_candidate_package(
    semantic: dict[str, Any],
    source_endpoints: dict[str, Any],
    effective_graph: dict[str, Any],
    checkpoint: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    assessment = assess_driving_insert_evidence(checkpoint, expected_mate_count=4)
    if assessment.get("checkpointPassed") is not True:
        raise Project05N000CandidateError(
            "N000四配合无锚点checkpoint未通过："
            + ", ".join(assessment.get("blockers") or [])
        )
    mates = effective_graph.get("Mates") or []
    expected_names = ["重合42", "平行13", "槽口4", "N000_LOCATING_DISTANCE_X"]
    if [str(row.get("MateName") or "") for row in mates] != expected_names:
        raise Project05N000CandidateError("N000有效图不是已验证的四配合顺序。")
    if int((mates[2].get("AdvancedOptions") or {}).get("SlotConstraint", -1)) != 0:
        raise Project05N000CandidateError("槽口4必须保留显式Free参数。")
    datum = mates[3].get("DerivedEngineeringDatum") or {}
    if (
        datum.get("authority") != "prototype_estimate"
        or datum.get("notVendorDatum") is not True
        or datum.get("productionReady") is not False
    ):
        raise Project05N000CandidateError("N000定位距离的原型估计权限声明不完整。")

    endpoint_catalog = copy.deepcopy(source_endpoints)
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    mate_steps: list[dict[str, Any]] = []
    initial_count = len(endpoint_catalog.get("Endpoints") or [])
    for mate in mates:
        step, target_rows, context_rows = _mate_step(mate, endpoint_catalog)
        mate_steps.append(step)
        target_bindings.extend(target_rows)
        context_bindings.extend(context_rows)
    endpoint_catalog["EndpointCount"] = len(endpoint_catalog.get("Endpoints") or [])
    endpoint_catalog["CatalogMode"] = "source_mate_endpoints_plus_free_slot_endpoints"
    endpoint_catalog["DerivedPackage"] = {
        "schemaVersion": "face-endpoint-package-derivation/v1",
        "sourceCatalogPath": _relative(SOURCE_ENDPOINTS),
        "geometryChanged": False,
        "appendedEndpointCount": endpoint_catalog["EndpointCount"] - initial_count,
        "parameterAuthority": "prototype_estimate",
    }

    candidate = copy.deepcopy(semantic)
    candidate["schemaVersion"] = "semantic-port-catalog/v2-candidate"
    candidate["catalogPurpose"] = (
        "Project05 N000/A000 non-anchor driving candidate: source Free slot plus "
        "a prototype-estimated X installation distance closes the residual translation."
    )
    candidate["endpointCatalogPath"] = "face_endpoint_catalog.json"
    candidate["effectiveMateGraphPath"] = "assembly_plan_effective.json"
    candidate["drivingScope"] = {
        "status": "candidate_only_not_released",
        "allowedModuleTokens": ["A000", "N000"],
        "exactMateBundleRequired": True,
        "mateNames": expected_names,
        "checkpointPath": _relative(CHECKPOINT),
        "caseAnchorAllowed": False,
        "parameterAuthority": "prototype_estimate",
        "productionReady": False,
    }
    by_token = {str(row.get("moduleToken")): row for row in candidate.get("ports") or []}
    by_token["N000"]["endpointBindings"] = target_bindings
    by_token["A000"]["endpointBindings"] = context_bindings
    by_token["N000"]["status"] = "cad-verified-nonanchor-demo"
    by_token["A000"]["status"] = "cad-verified-nonanchor-demo"
    template = copy.deepcopy((candidate.get("connectionTemplates") or [])[0])
    template["templateId"] = "N000_to_A000_nonanchor_driving_v2"
    template["constraintEffect"] = {
        "purpose": "Drive the proven Project05 N000-to-A000 four-relation installation bundle.",
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "closed_by_source_free_slot_plus_prototype_estimated_x_distance",
        "drivingAuthorization": "candidate_only_not_released",
        "exactMateBundleRequired": True,
        "residualDofScope": "external_module_placement",
        "internalFlexibilityPreserved": False,
        "parameterAuthority": "prototype_estimate",
        "productionReady": False,
    }
    template["mateSteps"] = mate_steps
    candidate["connectionTemplates"] = [template]
    candidate["readOnlySourceRelations"] = []
    candidate["upgradedSourceRelations"] = [
        {
            "mateName": "槽口4",
            "previousMode": "evidence_only",
            "candidateMode": "driving_as_part_of_exact_bundle",
            "reason": "源图已补齐SlotConstraint=Free、槽轴和两端点证据。",
        },
        {
            "mateName": "N000_LOCATING_DISTANCE_X",
            "candidateMode": "driving_as_part_of_exact_bundle",
            "parameterAuthority": "prototype_estimate",
            "distanceMeters": mates[3].get("Distance"),
            "productionReady": False,
        },
    ]
    return candidate, endpoint_catalog, assessment


def write_candidate_package(package_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate, endpoints, assessment = build_candidate_package(
        _read(SOURCE_SEMANTIC),
        _read(SOURCE_ENDPOINTS),
        _read(EFFECTIVE_GRAPH),
        _read(CHECKPOINT),
    )
    candidate["effectiveMateGraphPath"] = _relative(
        package_dir / "assembly_plan_effective.json"
    )
    package_dir.mkdir(parents=True, exist_ok=True)
    _write(package_dir / "semantic_port_catalog.json", candidate)
    _write(package_dir / "face_endpoint_catalog.json", endpoints)
    _write(package_dir / "assembly_plan_effective.json", _read(EFFECTIVE_GRAPH))
    return candidate, assessment


def main() -> int:
    parser = argparse.ArgumentParser(description="构建Project05 N000四配合无锚点驱动候选。")
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    package_dir = args.package_dir.resolve()
    candidate, assessment = write_candidate_package(package_dir)
    additional = [
        D000_CANDIDATE,
        *(EXISTING_CANDIDATES / token / "semantic_port_catalog.json" for token in ("F000", "M000", "G000")),
        P000_CANDIDATE,
        package_dir / "semantic_port_catalog.json",
    ]
    catalog = build_global_module_catalog(ROOT, additional_semantic_catalog_paths=additional)
    validate_global_module_catalog(catalog)
    source = _relative(package_dir / "semantic_port_catalog.json")
    matches = [
        row for row in catalog.get("connectionTemplates") or []
        if (row.get("provenance") or {}).get("semanticCatalogPath") == source
    ]
    if len(matches) != 1:
        raise Project05N000CandidateError(f"N000预期一个候选模板，实际为{len(matches)}。")
    template = matches[0]
    evidence = {
        "schemaVersion": "project05-n000-nonanchor-driving-candidate/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project05",
        "moduleToken": "N000",
        "packagePath": _relative(package_dir),
        "sourceCatalogPath": _relative(args.catalog_output.resolve()),
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "legacyTemplateId": template.get("legacyTemplateId"),
        "globalTemplateId": template.get("globalTemplateId"),
        "mateCount": len(template.get("mateSteps") or []),
        "checkpointPath": _relative(CHECKPOINT),
        "checkpointAssessment": assessment,
        "parameterAuthority": "prototype_estimate",
        "productionReady": False,
        "collisionStatus": "not_evaluated",
    }
    _write(args.catalog_output.resolve(), catalog)
    _write(args.evidence_output.resolve(), evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

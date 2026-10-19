from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_module_catalog import (  # noqa: E402
    build_global_module_catalog,
    validate_global_module_catalog,
)
from demo_backend.global_relation_semantics import (  # noqa: E402
    normalize_template_relation_profile,
)


SOURCE_PACKAGE = ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/D000"
SOURCE_SEMANTIC = SOURCE_PACKAGE / "semantic_port_catalog.json"
SOURCE_ENDPOINTS = SOURCE_PACKAGE / "face_endpoint_catalog.json"
SOURCE_GRAPH = ROOT / (
    "demo/semantic_ports/project05_resolved_pair_jobs/"
    "project05-job-2fd5dca2ddd7/attempt-01/transaction/effective-graph.json"
)
SOURCE_AUDIT = ROOT / (
    "demo/semantic_ports/project05_resolved_pair_jobs/"
    "project05-job-2fd5dca2ddd7/attempt-01/driving-pilot-audit-v1.json"
)
DEFAULT_PACKAGE = ROOT / (
    "demo/global_assembly_catalog/v1/driving-v1-preview/"
    "project05_D000_A000_scoped_driving_v2"
)
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/global_module_catalog.driving-v1-preview.json"
)
DEFAULT_EVIDENCE = ROOT / (
    "demo/global_assembly_catalog/v1/driving-v1-preview/evidence.json"
)
CURRENT_DIRECT_CAD_ATTEMPT = ROOT / (
    "demo/semantic_ports/project05_D000_A000_scoped_driving_v2/cad/"
    "current-cad-rerun-v1.result.json"
)
CACHED_CONTEXT_CAD_RESULT = DEFAULT_PACKAGE / (
    "cad-cache/remate-current-v1.result.json"
)
NONPROTOTYPE_POSE_CAD_RESULT = DEFAULT_PACKAGE / (
    "cad-cache/fresh-insert-v1.result.json"
)


class Project05ScopedDrivingCandidateError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Project05ScopedDrivingCandidateError(f"JSON root must be an object: {path}")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def build_candidate_package(
    semantic: dict[str, Any],
    endpoints: dict[str, Any],
    effective_graph: dict[str, Any],
    audit: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Upgrade the proven Project05 A000/D000 three-mate bundle without guessing faces."""

    if audit.get("status") != "candidate_for_scoped_driving_release":
        raise Project05ScopedDrivingCandidateError(
            "The real-CAD pilot audit is not a scoped driving candidate."
        )
    width_rows = [
        row
        for row in effective_graph.get("Mates") or []
        if str(row.get("MateName") or "") == "宽度17"
    ]
    if len(width_rows) != 1:
        raise Project05ScopedDrivingCandidateError("Expected exactly one 宽度17 relation.")
    width = width_rows[0]
    if int(width.get("MateType", -1)) != 11 or len(width.get("Endpoints") or []) != 4:
        raise Project05ScopedDrivingCandidateError("宽度17 must be a four-endpoint width mate.")
    advanced = deepcopy(width.get("AdvancedOptions") or {})
    if advanced.get("WidthEndpointIndices") != [0, 1] or advanced.get(
        "TabEndpointIndices"
    ) != [2, 3]:
        raise Project05ScopedDrivingCandidateError(
            "宽度17 is missing authoritative width/tab endpoint grouping."
        )

    endpoint_rows = endpoints.get("Endpoints") or []
    if len(endpoint_rows) != 8:
        raise Project05ScopedDrivingCandidateError("Expected the proven eight-endpoint catalog.")
    width_endpoint_ids = [str(row.get("EndpointId") or "") for row in endpoint_rows[-4:]]
    expected_tokens = ["A000", "A000", "D000", "D000"]
    actual_tokens = [
        str((row.get("Endpoint") or {}).get("ModuleToken") or "")
        for row in endpoint_rows[-4:]
    ]
    if actual_tokens != expected_tokens or not all(width_endpoint_ids):
        raise Project05ScopedDrivingCandidateError(
            "The endpoint catalog order does not match the proven width mate."
        )

    candidate = deepcopy(semantic)
    candidate["schemaVersion"] = "semantic-port-catalog/v2-candidate"
    candidate["catalogPurpose"] = (
        "Scoped Project05 A000/D000 driving candidate reconstructed from the real "
        "three-mate bundle; not a general relation release."
    )
    candidate["endpointCatalogPath"] = "face_endpoint_catalog.json"
    candidate["effectiveMateGraphPath"] = _relative(SOURCE_GRAPH)
    candidate["drivingScope"] = {
        "status": "candidate_only_not_released",
        "allowedModuleTokens": ["A000", "D000"],
        "exactMateBundleRequired": True,
        "mateNames": ["重合3", "距离1", "宽度17"],
        "realCadPilotAuditPath": _relative(SOURCE_AUDIT),
        "authorityBoundary": (
            "This candidate may drive only the complete A000/D000 installation bundle; "
            "it does not authorize standalone width-mate creation or other module pairs."
        ),
    }

    by_token = {str(row.get("moduleToken")): row for row in candidate.get("ports") or []}
    by_token["A000"]["endpointBindings"].extend(
        [
            {"role": "宽度17_context_1", "endpointId": width_endpoint_ids[0]},
            {"role": "宽度17_context_2", "endpointId": width_endpoint_ids[1]},
        ]
    )
    by_token["D000"]["endpointBindings"].extend(
        [
            {"role": "宽度17_target_1", "endpointId": width_endpoint_ids[2]},
            {"role": "宽度17_target_2", "endpointId": width_endpoint_ids[3]},
        ]
    )

    template = deepcopy((candidate.get("connectionTemplates") or [])[0])
    template["templateId"] = "D000_to_A000_scoped_driving_v2"
    template["constraintEffect"] = {
        "purpose": "Drive the proven Project05 D000-to-A000 installation bundle.",
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "closed_by_exact_three_mate_bundle",
        "drivingAuthorization": "candidate_only_not_released",
        "exactMateBundleRequired": True,
    }
    template["mateSteps"].append(
        {
            "mateName": "宽度17",
            "mateType": 11,
            "mateTypeName": "swMateWIDTH",
            "alignment": int(width.get("Alignment", 1)),
            "alignmentName": width.get("AlignmentName"),
            "endpointRoles": [
                {"side": "B", "role": "宽度17_context_1"},
                {"side": "B", "role": "宽度17_context_2"},
                {"side": "A", "role": "宽度17_target_1"},
                {"side": "A", "role": "宽度17_target_2"},
            ],
            "advancedOptions": advanced,
        }
    )
    candidate["connectionTemplates"] = [template]
    candidate["readOnlySourceRelations"] = []
    candidate["upgradedSourceRelations"] = [
        {
            "mateName": "宽度17",
            "previousMode": "evidence_only",
            "candidateMode": "driving_as_part_of_exact_bundle",
            "reason": (
                "The effective graph now carries all four endpoints plus authoritative "
                "WidthEndpointIndices and TabEndpointIndices."
            ),
        }
    ]

    endpoint_copy = deepcopy(endpoints)
    endpoint_copy["DerivedPackage"] = {
        "schemaVersion": "face-endpoint-package-derivation/v1",
        "sourceCatalogPath": _relative(SOURCE_ENDPOINTS),
        "sourceCatalogDigest": _digest(endpoints),
        "geometryChanged": False,
        "statement": "All eight endpoint identities are reused; no face was re-guessed.",
    }
    return candidate, endpoint_copy


def write_candidate_package(package_dir: Path) -> dict[str, Any]:
    semantic = _read(SOURCE_SEMANTIC)
    endpoints = _read(SOURCE_ENDPOINTS)
    graph = _read(SOURCE_GRAPH)
    audit = _read(SOURCE_AUDIT)
    candidate, endpoint_copy = build_candidate_package(semantic, endpoints, graph, audit)
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "semantic_port_catalog.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (package_dir / "face_endpoint_catalog.json").write_text(
        json.dumps(endpoint_copy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the scoped Project05 A000/D000 three-mate driving candidate."
    )
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()

    package_dir = args.package_dir.resolve()
    candidate = write_candidate_package(package_dir)
    catalog = build_global_module_catalog(
        ROOT,
        additional_semantic_catalog_paths=[
            package_dir / "semantic_port_catalog.json"
        ],
    )
    validate_global_module_catalog(catalog)
    candidate_source = _relative(package_dir / "semantic_port_catalog.json")
    templates = [
        row
        for row in catalog.get("connectionTemplates") or []
        if (row.get("provenance") or {}).get("semanticCatalogPath") == candidate_source
    ]
    if len(templates) != 1:
        raise Project05ScopedDrivingCandidateError(
            f"Expected one global candidate template, found {len(templates)}."
        )
    global_template = templates[0]
    profile = normalize_template_relation_profile(global_template)
    nonprototype_result = (
        _read(NONPROTOTYPE_POSE_CAD_RESULT)
        if NONPROTOTYPE_POSE_CAD_RESULT.is_file()
        else None
    )
    nonprototype_tool = (nonprototype_result or {}).get("toolResult") or {}
    nonprototype_gate_passed = bool(
        nonprototype_result
        and nonprototype_result.get("success") is True
        and nonprototype_result.get("sourceAssemblyUnchanged") is True
        and nonprototype_result.get("outputAssemblySha256")
        and nonprototype_tool.get("OriginalComponentRemoved") is True
        and nonprototype_tool.get("IndependentComponentInserted") is True
        and nonprototype_tool.get("TargetCaseAnchored") is False
        and nonprototype_tool.get("TargetFullyConstrained") is True
        and nonprototype_tool.get("MateSolveClean") is True
    )
    checks = {
        "exactThreeMateBundle": len(global_template.get("mateSteps") or []) == 3,
        "allCandidatePortsPortable": all(
            row.get("portableForTemplate") is True
            for row in catalog.get("compatibility") or []
            if row.get("globalTemplateId") == global_template.get("globalTemplateId")
        ),
        "drivesPlacement": profile.get("drivesPlacement") is True,
        "declaresClosedDof": (
            profile.get("constraintExplanation", {}).get("expectedResidualDof") == 0
        ),
        "stillCandidateOnly": (
            candidate.get("drivingScope", {}).get("status")
            == "candidate_only_not_released"
        ),
        "nonPrototypeInitialPoseGate": nonprototype_gate_passed,
    }
    current_cad_attempt = (
        _read(CURRENT_DIRECT_CAD_ATTEMPT)
        if CURRENT_DIRECT_CAD_ATTEMPT.is_file()
        else None
    )
    cached_context_cad_result = (
        _read(CACHED_CONTEXT_CAD_RESULT)
        if CACHED_CONTEXT_CAD_RESULT.is_file()
        else None
    )
    cad_closed = bool(
        cached_context_cad_result
        and cached_context_cad_result.get("success") is True
        and cached_context_cad_result.get("published") is True
        and cached_context_cad_result.get("sourceAssemblyUnchanged") is True
    )
    evidence_status = (
        "ready"
        if cad_closed
        else "blocked_on_cold_session_leaf_resolution"
        if current_cad_attempt and current_cad_attempt.get("success") is not True
        else "ready_for_current_cad_rerun"
    )
    evidence = {
        "schemaVersion": "project05-scoped-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": evidence_status if all(checks.values()) else "blocked",
        "packagePath": _relative(package_dir),
        "globalTemplateId": global_template.get("globalTemplateId"),
        "legacyTemplateId": global_template.get("legacyTemplateId"),
        "checks": checks,
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "derivations": [
            {
                "entry": {
                    "mode": "register_scoped_driving_bundle",
                    "sourceProjectId": "project05",
                    "mateNames": ["重合3", "距离1", "宽度17"],
                },
                "result": {
                    "derivedGlobalTemplateId": global_template.get(
                        "globalTemplateId"
                    ),
                    "drivingScope": "project05_A000_D000_exact_bundle_only",
                },
            }
        ],
        "templateProfile": profile,
        "sourceEvidence": {
            "effectiveMateGraphPath": _relative(SOURCE_GRAPH),
            "pilotAuditPath": _relative(SOURCE_AUDIT),
            "endpointCatalogPath": _relative(SOURCE_ENDPOINTS),
        },
        "solidWorksExecuted": bool(current_cad_attempt or cached_context_cad_result),
        "currentCadAttempt": (
            {
                "resultPath": _relative(CURRENT_DIRECT_CAD_ATTEMPT),
                "success": current_cad_attempt.get("success"),
                "published": current_cad_attempt.get("published"),
                "durationSeconds": current_cad_attempt.get("durationSeconds"),
                "sourceAssemblyUnchanged": current_cad_attempt.get(
                    "sourceAssemblyUnchanged"
                ),
                "requestedMateCount": (
                    current_cad_attempt.get("toolResult") or {}
                ).get("RequestedMateCount"),
                "createdMateCount": (
                    current_cad_attempt.get("toolResult") or {}
                ).get("CreatedMateCount"),
                "failureClass": "cold_session_target_leaf_resolution_failed",
            }
            if current_cad_attempt
            else None
        ),
        "cachedContextCadClosure": (
            {
                "resultPath": _relative(CACHED_CONTEXT_CAD_RESULT),
                "success": cached_context_cad_result.get("success"),
                "published": cached_context_cad_result.get("published"),
                "durationSeconds": cached_context_cad_result.get("durationSeconds"),
                "sourceAssemblyUnchanged": cached_context_cad_result.get(
                    "sourceAssemblyUnchanged"
                ),
                "outputAssemblyPath": cached_context_cad_result.get(
                    "outputAssemblyPath"
                ),
                "outputAssemblySha256": cached_context_cad_result.get(
                    "outputAssemblySha256"
                ),
            }
            if cached_context_cad_result
            else None
        ),
        "nonPrototypeInitialPoseCadClosure": (
            {
                "resultPath": _relative(NONPROTOTYPE_POSE_CAD_RESULT),
                "success": nonprototype_result.get("success"),
                "published": nonprototype_result.get("published"),
                "sourceAssemblyUnchanged": nonprototype_result.get(
                    "sourceAssemblyUnchanged"
                ),
                "targetExplicitlyDisplaced": nonprototype_tool.get(
                    "TargetComponentExplicitlyDisplaced"
                ),
                "originalComponentRemoved": nonprototype_tool.get(
                    "OriginalComponentRemoved"
                ),
                "independentComponentInserted": nonprototype_tool.get(
                    "IndependentComponentInserted"
                ),
                "targetCaseAnchored": nonprototype_tool.get(
                    "TargetCaseAnchored"
                ),
                "initialDisplacementMaximumElementDelta": nonprototype_tool.get(
                    "InitialDisplacementMaximumElementDelta"
                ),
                "returnToSourcePoseMaximumElementError": nonprototype_tool.get(
                    "ReturnToSourcePoseMaximumElementError"
                ),
                "targetReturnedToSourcePose": nonprototype_tool.get(
                    "TargetReturnedToSourcePose"
                ),
                "targetFullyConstrained": nonprototype_tool.get(
                    "TargetFullyConstrained"
                ),
                "mateMessages": [
                    row.get("Message")
                    for row in nonprototype_tool.get("MateResults") or []
                ],
            }
            if nonprototype_result
            else None
        ),
        "releaseDecision": (
            "eligible_for_scoped_template_only_release"
            if cad_closed and nonprototype_gate_passed
            else "blocked_until_nonprototype_initial_pose_is_solved_by_mates"
            if cad_closed
            else "not_released_until_current_cad_copy_rerun_passes"
        ),
    }
    args.catalog_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.catalog_output.resolve().write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.evidence_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.evidence_output.resolve().write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": evidence["status"], "checks": checks}, ensure_ascii=False, indent=2))
    print(args.evidence_output.resolve())
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

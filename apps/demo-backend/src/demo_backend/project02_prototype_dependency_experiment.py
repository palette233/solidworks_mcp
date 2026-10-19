"""Project02 prototype-dependency audit and initial-pose ablation helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .prototype_dependency_audit import audit_project_profile_dependencies
from .resolved_pair_transaction_jobs import _load_source_registry, sha256_file


SCHEMA = "project02-prototype-dependency-experiment/v1"


def _get(mapping: dict[str, Any], name: str, default=None):
    return mapping.get(name, mapping.get(name[0].lower() + name[1:], default))


def _set(mapping: dict[str, Any], name: str, value: Any) -> None:
    if name in mapping:
        mapping[name] = value
    else:
        mapping[name[0].lower() + name[1:]] = value


def _target_module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [
        row
        for row in _get(graph, "Modules", []) or []
        if str(_get(row, "ModuleToken", "")).upper() == token.upper()
    ]
    if len(matches) != 1:
        raise ValueError(f"Target {token} resolved to {len(matches)} graph modules.")
    return matches[0]


def build_top_level_initial_pose_ablation(
    graph: dict[str, Any], target_token: str
) -> dict[str, Any]:
    variant = deepcopy(graph)
    policy = _get(variant, "EditPolicy") or {}
    _set(policy, "InitialPlacementMode", "deterministic_nonprototype_pose")
    _set(policy, "CaseAnchoredModuleTokens", [])
    # Internal leaf-state anchors are deliberately retained.  They are audited
    # separately so this experiment isolates top-level placement dependence.
    target = _target_module(variant, target_token)
    target["PrototypeInitialPoseAblated"] = True
    return variant


def build_project02_prototype_dependency_experiment(
    workspace: Path,
    output_directory: Path,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    project = (_load_source_registry().get("projects") or {}).get("project02") or {}
    rows: list[dict[str, Any]] = []
    occurrence: dict[tuple[str, str], int] = {}
    case_anchor_count = 0
    internal_anchor_module_count = 0
    for order, profile in enumerate(
        project.get("independentPairInstallations") or [], start=1
    ):
        target = str(profile.get("targetModuleToken") or "").upper()
        context = str(profile.get("contextModuleToken") or "").upper()
        key = (target, context)
        occurrence[key] = occurrence.get(key, 0) + 1
        source_graph = Path(str(profile.get("effectiveMateGraphPath") or ""))
        if not source_graph.is_absolute():
            source_graph = workspace / source_graph
        source_graph = source_graph.resolve()
        graph = json.loads(source_graph.read_text(encoding="utf-8"))
        policy = _get(graph, "EditPolicy") or {}
        case_anchors = list(_get(policy, "CaseAnchoredModuleTokens", []) or [])
        leaf_anchors = list(_get(policy, "TargetLeafPoseAnchors", []) or [])
        active_mates = [
            mate
            for mate in _get(graph, "Mates", []) or []
            if not bool(_get(mate, "IsSuppressed", False))
        ]
        case_anchor_count += int(bool(case_anchors))
        internal_anchor_module_count += int(bool(leaf_anchors))
        slug = f"{order:02d}-{target.lower()}-to-{context.lower()}"
        ablated_path = output_directory / f"{slug}-top-level-ablation.json"
        variant = build_top_level_initial_pose_ablation(graph, target)
        ablated_path.write_text(
            json.dumps(variant, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "order": order,
                "targetModuleToken": target,
                "contextModuleToken": context,
                "occurrenceIndexForPair": occurrence[key],
                "sourceGraphPath": str(source_graph),
                "sourceGraphSha256": sha256_file(source_graph),
                "activeMateCount": len(active_mates),
                "constraintRequirement": str(
                    profile.get("constraintRequirement") or "fully_constrained"
                ),
                "activeMateTypes": [
                    str(_get(mate, "MateTypeName", "")) for mate in active_mates
                ],
                "sourceInitialPlacementMode": _get(
                    policy, "InitialPlacementMode"
                ),
                "caseAnchorSelectors": case_anchors,
                "topLevelPlacementDependsOnPrototypeCaseAnchor": bool(
                    case_anchors
                ),
                "internalLeafStateAnchorCount": len(leaf_anchors),
                "internalStateDependsOnPrototypePose": bool(leaf_anchors),
                "mateEndpointsDerivedFromPrototype": True,
                "ablatedGraphPath": str(ablated_path),
                "ablatedGraphSha256": sha256_file(ablated_path),
                "experimentBoundary": (
                    "Only top-level source/case placement is removed. Real mate geometry "
                    "and any internal flexible-state anchors are retained."
                ),
            }
        )

    profile_audit = audit_project_profile_dependencies(
        "project02", workspace=workspace
    )
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "projectId": "project02",
        "summary": {
            "installationStepCount": len(rows),
            "topLevelCaseAnchorStepCount": case_anchor_count,
            "alreadyNonprototypeInitialPoseStepCount": len(rows)
            - case_anchor_count,
            "internalPrototypeStateAnchorModuleCount": internal_anchor_module_count,
            "prototypeDerivedMateGeometryStepCount": len(rows),
            "profilePrototypeDependentModuleCount": profile_audit[
                "prototypeDependentModuleCount"
            ],
            "productionProfileAccepted": profile_audit[
                "productionProfileAccepted"
            ],
        },
        "baseDependency": {
            "moduleToken": "A600",
            "role": "fixed independent base context",
            "dependency": (
                "The A600-only base and its identity datum are extracted from the "
                "Project02 case; this experiment does not replace the machine datum."
            ),
        },
        "steps": rows,
        "interpretationBoundary": {
            "provesIfCadPasses": (
                "The registered mate bundle can locate the target from a deterministic "
                "non-source top-level pose in the tested static context."
            ),
            "doesNotProve": [
                "vendor datum authority",
                "cross-project portability",
                "collision freedom",
                "dynamic travel or process coverage",
                "optical working distance or field of view",
                "maintenance accessibility",
            ],
        },
    }


def summarize_initial_pose_result(
    row: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    tool = evidence.get("toolResult") or {}
    requirement = str(row.get("constraintRequirement") or "fully_constrained")
    required_full = requirement == "fully_constrained"
    full = bool(_get(tool, "TargetFullyConstrained", False))
    accepted = bool(_get(tool, "TargetConstraintStateAccepted", False))
    passed = (
        evidence.get("success") is True
        and _get(tool, "TargetCaseAnchored", True) is False
        and _get(tool, "IndependentComponentInserted", False) is True
        and _get(tool, "Reopened", False) is True
        and _get(tool, "ReopenedMateParametersMatch", False) is True
        and _get(tool, "ComponentSemanticsMatch", False) is True
        and accepted
        and bool(_get(tool, "MateSolveClean", False))
        and (full or not required_full)
    )
    return {
        "order": row["order"],
        "targetModuleToken": row["targetModuleToken"],
        "contextModuleToken": row["contextModuleToken"],
        "constraintRequirement": requirement,
        "topLevelCaseAnchorRemoved": True,
        "internalLeafStateAnchorCountRetained": row[
            "internalLeafStateAnchorCount"
        ],
        "cadTransactionSuccess": evidence.get("success") is True,
        "targetCaseAnchored": bool(_get(tool, "TargetCaseAnchored", False)),
        "requestedMateCount": _get(tool, "RequestedMateCount"),
        "createdMateCount": _get(tool, "CreatedMateCount"),
        "targetFullyConstrained": full,
        "targetConstraintStateAccepted": accepted,
        "mateSolveClean": bool(_get(tool, "MateSolveClean", False)),
        "reopened": bool(_get(tool, "Reopened", False)),
        "reopenedMateParametersMatch": bool(
            _get(tool, "ReopenedMateParametersMatch", False)
        ),
        "componentSemanticsMatch": bool(
            _get(tool, "ComponentSemanticsMatch", False)
        ),
        "nonprototypeInitialPoseGatePassed": passed,
        "durationSeconds": evidence.get("durationSeconds"),
        "outputAssemblyPath": evidence.get("outputAssemblyPath"),
        "outputAssemblySha256": evidence.get("outputAssemblySha256"),
    }


def recommended_dependency_replacement(target: str, context: str, passed: bool) -> str:
    key = (target.upper(), context.upper())
    if passed:
        if key in {("A300", "A600"), ("A200", "A600")}:
            return (
                "Remove the redundant top-level case anchor from the durable graph, "
                "then rerun this step and every downstream checkpoint."
            )
        return "Keep the already anchor-free durable installation graph."
    return {
        ("A800", "A600"): (
            "Add the missing longitudinal installation datum: preferably the vendor "
            "A600/A800 XYZ offset, a locating stop, or an equivalent third datum."
        ),
        ("A180", "A600"): (
            "Add a scanner-bracket in-plane locator and orientation datum, then validate "
            "the optical axis against the barcode target and working-distance interval."
        ),
        ("A700", "A600"): (
            "Add top-level operation-side/service-zone locators. Keep the two internal "
            "static-state anchors as a separate dependency until named mechanism states exist."
        ),
        ("T401", "A600"): (
            "Add the remaining mounting-position datum and a hose/maintenance direction "
            "constraint; the current coincident-plus-distance bundle is insufficient."
        ),
        ("T401", "A200"): (
            "One distance relation cannot determine a rigid-body pose. Add a mounting plane, "
            "axis or hole pattern, and in-plane location/orientation datums."
        ),
    }.get(key, "Add independent mechanical datums until the CAD solver accepts the target state.")

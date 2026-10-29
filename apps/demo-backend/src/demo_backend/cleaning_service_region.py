"""Rule-driven cleaning service-region screening, not an engineering release.

Native-role occupancy supplies an approximate Demo region. Prototype poses are
only coordinate bridges; placement follows the target region and datum normals.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from . import role_station_geometry as geometry
from .cross_project_module_substitution import (
    build_module_role_overlay,
    resolve_module_reference,
)


DEFAULT_RULE = "data/assembly_stations/cleaning-gn00-aa00-v1.json"
DEFAULT_GLOBAL_MODULE_CATALOG = (
    "demo/global_assembly_catalog/v1/global_module_catalog.json"
)

# Both values mean that the box was built from the complete captured leaf
# subtree.  The newer isolated N000 capture uses the singular form while the
# older project-wide inventories use the plural form.  Neither value denotes
# a hand-authored or partial proxy.
COMPLETE_SERVICE_SUBTREE_SOURCES = {
    "leaf-subtree-unions",
    "complete-leaf-subtree-union",
}

# These are review prompts, not equivalence rules.  They deliberately do not
# contribute to exact capability coverage until engineering semantics are
# confirmed in a separate, versioned decision.
CAPABILITY_REVIEW_NEAR_MATCHES = {
    "inspection": {"vision_alignment"},
}


def _capability_profile(
    catalog: dict[str, Any], overlay: dict[str, Any], reference: str
) -> dict[str, Any]:
    """Resolve one reviewed role/capability profile from an exact module reference."""

    if "::" in reference:
        project_id, module_token = reference.split("::", 1)
        resolved_reference: str | dict[str, str] = {
            "projectId": project_id,
            "moduleToken": module_token,
        }
    else:
        resolved_reference = reference
    definition = resolve_module_reference(catalog, resolved_reference)
    matches = [
        row
        for row in overlay.get("modules") or []
        if row.get("moduleDefinitionId") == definition.get("moduleDefinitionId")
    ]
    if len(matches) != 1:
        raise ValueError(f"module capability profile is missing or ambiguous: {reference}")
    profile = matches[0]
    capabilities = profile.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or any(not isinstance(value, str) or not value for value in capabilities)
        or len(capabilities) != len(set(capabilities))
    ):
        raise ValueError(f"module capability profile is invalid: {reference}")
    return {
        "requestedReference": reference,
        "moduleDefinitionId": definition["moduleDefinitionId"],
        "primaryRole": profile.get("primaryRole"),
        "displayRole": profile.get("displayRole"),
        "capabilities": sorted(capabilities),
        "roleReviewStatus": profile.get("roleReviewStatus"),
    }


def discover_target_project_capability_providers(
    workspace: Path,
    source_module_definition_id: str,
    target_base_definition_id: str,
    *,
    module_catalog_path: str = DEFAULT_GLOBAL_MODULE_CATALOG,
) -> dict[str, Any]:
    """Discover reviewed target-project providers for one composite service module.

    Discovery is deliberately limited to exact role labels that have already
    been accepted in the global catalog overlay.  It does not infer capability
    synonyms (for example ``inspection`` == ``vision_alignment``), mechanical
    compatibility or a usable station.  The result is therefore suitable for
    completing the semantic pre-screen, but never for starting CAD.
    """

    if "::" not in target_base_definition_id:
        raise ValueError("target base must be an explicit project::token reference")
    target_project_id, _ = target_base_definition_id.split("::", 1)
    root = Path(workspace).resolve()
    catalog_path = Path(module_catalog_path)
    catalog_path = catalog_path if catalog_path.is_absolute() else root / catalog_path
    if not catalog_path.is_file():
        raise ValueError("module catalog is missing")
    catalog = geometry._read(catalog_path)
    overlay = build_module_role_overlay(catalog)
    source = _capability_profile(
        catalog, overlay, source_module_definition_id
    )
    if source.get("primaryRole") != "CleaningWeighing":
        raise ValueError("source module must have the CleaningWeighing role")
    required = set(source["capabilities"])

    providers: list[dict[str, Any]] = []
    near_match_providers: list[dict[str, Any]] = []
    for definition in catalog.get("moduleDefinitions") or []:
        aliases = [
            alias
            for alias in definition.get("projectAliases") or []
            if str(alias.get("projectId") or "").casefold()
            == target_project_id.casefold()
            and alias.get("isBaseModule") is not True
        ]
        if not aliases:
            continue
        profile = _capability_profile(
            catalog, overlay, definition["moduleDefinitionId"]
        )
        relevant = sorted(required.intersection(profile["capabilities"]))
        base_row = {
            "moduleDefinitionId": definition["moduleDefinitionId"],
            "projectModuleTokens": sorted(
                {str(alias.get("moduleToken") or "") for alias in aliases}
            ),
            "primaryRole": profile["primaryRole"],
            "displayRole": profile["displayRole"],
            "roleReviewStatus": profile["roleReviewStatus"],
        }
        if relevant:
            providers.append(
                {**base_row, "providedRequiredCapabilities": relevant}
            )
            continue
        offered = set(profile["capabilities"])
        review_for = sorted(
            capability
            for capability in required
            if offered.intersection(
                CAPABILITY_REVIEW_NEAR_MATCHES.get(capability, set())
            )
        )
        if review_for:
            near_match_providers.append(
                {
                    **base_row,
                    "offeredCapabilities": sorted(offered),
                    "reviewForRequiredCapabilities": review_for,
                    "countsAsCoverage": False,
                }
            )
    providers.sort(
        key=lambda row: (row["projectModuleTokens"], row["moduleDefinitionId"])
    )
    near_match_providers.sort(
        key=lambda row: (row["projectModuleTokens"], row["moduleDefinitionId"])
    )
    references = [row["moduleDefinitionId"] for row in providers]
    provided = {
        capability
        for row in providers
        for capability in row["providedRequiredCapabilities"]
    }
    unresolved = sorted(required - provided)
    return {
        "schemaVersion": "cleaning-capability-provider-discovery/v1",
        "sourceModuleDefinitionId": source_module_definition_id,
        "targetBaseDefinitionId": target_base_definition_id,
        "targetProjectId": target_project_id,
        "sourceRequiredCapabilities": sorted(required),
        "providerModuleDefinitionIds": references,
        "providers": providers,
        "nearMatchProvidersRequiringEngineeringDecision": near_match_providers,
        "providedRequiredCapabilities": sorted(provided),
        "unresolvedCapabilities": unresolved,
        "cadStarted": False,
        "boundary": (
            "Catalog-role discovery only. Capability synonyms, station geometry, "
            "mechanical compatibility and process performance are not inferred."
        ),
        "evidence": {
            "path": str(catalog_path),
            "sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        },
    }


def build_discovered_cleaning_service_capability_audit(
    workspace: Path,
    source_module_definition_id: str,
    target_base_definition_id: str,
    *,
    module_catalog_path: str = DEFAULT_GLOBAL_MODULE_CATALOG,
) -> dict[str, Any]:
    """Build one capability audit from exact target-project role labels."""

    discovery = discover_target_project_capability_providers(
        workspace,
        source_module_definition_id,
        target_base_definition_id,
        module_catalog_path=module_catalog_path,
    )
    report = build_cleaning_service_capability_audit(
        workspace,
        source_module_definition_id,
        target_base_definition_id,
        discovery["providerModuleDefinitionIds"],
        module_catalog_path=module_catalog_path,
    )
    report["providerDiscovery"] = discovery
    core = {key: value for key, value in report.items() if key != "auditDigest"}
    report["auditDigest"] = hashlib.sha256(
        json.dumps(
            core,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return report


def build_cleaning_capability_semantic_decision_request(
    workspace: Path,
    capability_index_path: str,
) -> dict[str, Any]:
    """Deduplicate capability near matches into project-level decisions."""

    root = Path(workspace).resolve()
    index_path = Path(capability_index_path)
    index_path = index_path if index_path.is_absolute() else root / index_path
    if not index_path.is_file():
        raise ValueError("capability index is missing")
    index = geometry._read(index_path)
    if index.get("schemaVersion") != "cleaning-service-capability-coverage-index/v1":
        raise ValueError("unsupported capability index")

    grouped: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    evidence = [{
        "path": str(index_path),
        "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
    }]
    for entry in index.get("entries") or []:
        report_path = Path(entry.get("reportPath") or "")
        report_path = report_path if report_path.is_absolute() else root / report_path
        if (
            not report_path.is_file()
            or hashlib.sha256(report_path.read_bytes()).hexdigest()
            != entry.get("reportSha256")
        ):
            raise ValueError("capability audit evidence changed")
        report = geometry._read(report_path)
        if report.get("auditDigest") != entry.get("auditDigest"):
            raise ValueError("capability audit digest changed")
        discovery = report.get("providerDiscovery") or {}
        for provider in discovery.get(
            "nearMatchProvidersRequiringEngineeringDecision"
        ) or []:
            offered = tuple(provider.get("offeredCapabilities") or [])
            for required in provider.get("reviewForRequiredCapabilities") or []:
                key = (discovery.get("targetProjectId"), required, offered)
                row = grouped.setdefault(
                    key,
                    {
                        "targetProjectId": discovery.get("targetProjectId"),
                        "requiredCapability": required,
                        "offeredCapabilities": list(offered),
                        "candidateProviders": [],
                        "affectedPairs": [],
                        "confirmed": False,
                        "decision": None,
                        "status": "engineering_confirmation_required",
                    },
                )
                candidate = {
                    "moduleDefinitionId": provider["moduleDefinitionId"],
                    "projectModuleTokens": provider["projectModuleTokens"],
                    "displayRole": provider["displayRole"],
                }
                if candidate not in row["candidateProviders"]:
                    row["candidateProviders"].append(candidate)
                pair = {
                    "sourceModuleDefinitionId": entry[
                        "sourceModuleDefinitionId"
                    ],
                    "targetBaseDefinitionId": entry["targetBaseDefinitionId"],
                }
                if pair not in row["affectedPairs"]:
                    row["affectedPairs"].append(pair)
        evidence.append({
            "path": str(report_path),
            "sha256": entry["reportSha256"],
        })
    decisions = []
    for key in sorted(grouped):
        row = grouped[key]
        row["candidateProviders"].sort(
            key=lambda item: (item["projectModuleTokens"], item["moduleDefinitionId"])
        )
        row["affectedPairs"].sort(
            key=lambda item: (
                item["sourceModuleDefinitionId"],
                item["targetBaseDefinitionId"],
            )
        )
        row["decisionId"] = (
            f"{row['targetProjectId']}::{row['requiredCapability']}::"
            f"{'-'.join(row['offeredCapabilities'])}"
        )
        row["question"] = (
            f"Can {', '.join(row['offeredCapabilities'])} satisfy the "
            f"{row['requiredCapability']} service semantics for the listed "
            "cleaning/weighing station contexts?"
        )
        decisions.append(row)
    return {
        "schemaVersion": "cleaning-capability-semantic-decision-request/v1",
        "decisions": decisions,
        "summary": {
            "decisionCount": len(decisions),
            "affectedPairCount": len(
                {
                    (pair["sourceModuleDefinitionId"], pair["targetBaseDefinitionId"])
                    for row in decisions
                    for pair in row["affectedPairs"]
                }
            ),
            "confirmedCount": 0,
        },
        "cadStarted": False,
        "evidence": evidence,
        "boundary": (
            "A decision is required before capability coverage can pass. This "
            "request does not authorize station geometry or CAD execution."
        ),
    }


def build_cleaning_service_capability_audit(
    workspace: Path,
    source_module_definition_id: str,
    target_base_definition_id: str,
    target_capability_module_definition_ids: list[str],
    *,
    module_catalog_path: str = DEFAULT_GLOBAL_MODULE_CATALOG,
) -> dict[str, Any]:
    """Build a catalog-only semantic capability audit for one exact pair.

    This deliberately does not inspect placement geometry, start CAD or infer
    that similarly named capabilities are equivalent.  It is the lightweight
    first gate before a cleaning/weighing station rule may consume geometry.
    """

    if not isinstance(source_module_definition_id, str) or not source_module_definition_id:
        raise ValueError("source module definition id must be a nonempty string")
    if not isinstance(target_base_definition_id, str) or not target_base_definition_id:
        raise ValueError("target base definition id must be a nonempty string")
    if (
        not isinstance(target_capability_module_definition_ids, list)
        or not target_capability_module_definition_ids
        or any(not isinstance(value, str) or not value for value in target_capability_module_definition_ids)
        or len(target_capability_module_definition_ids)
        != len(set(target_capability_module_definition_ids))
    ):
        raise ValueError("target capability providers must be a nonempty unique list")

    root = Path(workspace).resolve()
    catalog_path = Path(module_catalog_path)
    catalog_path = catalog_path if catalog_path.is_absolute() else root / catalog_path
    if not catalog_path.is_file():
        raise ValueError("module catalog is missing")
    catalog = geometry._read(catalog_path)
    role_overlay = build_module_role_overlay(catalog)
    source_profile = _capability_profile(
        catalog, role_overlay, source_module_definition_id
    )
    if source_profile.get("primaryRole") != "CleaningWeighing":
        raise ValueError("source module must have the CleaningWeighing role")
    target_profiles = [
        _capability_profile(catalog, role_overlay, reference)
        for reference in target_capability_module_definition_ids
    ]
    required = set(source_profile["capabilities"])
    provided = {
        capability
        for profile in target_profiles
        for capability in profile["capabilities"]
    }
    missing = sorted(required - provided)
    coverage = {
        "passed": not missing,
        "sourceProfile": source_profile,
        "targetProviderProfiles": target_profiles,
        "sourceRequiredCapabilities": sorted(required),
        "targetProvidedCapabilities": sorted(provided),
        "missingCapabilities": missing,
        "method": "reviewed_global_module_role_overlay_set_coverage",
        "claimBoundary": (
            "Capability labels screen semantic completeness only. No synonym, "
            "geometry, process, fastening or collision equivalence is inferred."
        ),
    }
    evidence = {
        "path": str(catalog_path),
        "sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
    }
    report = {
        "schemaVersion": "cleaning-service-capability-audit/v1",
        "source": source_module_definition_id,
        "target": target_base_definition_id,
        "role": "CleaningWeighing",
        "targetCapabilityModuleDefinitionIds": target_capability_module_definition_ids,
        "capabilityCoverage": coverage,
        "cadStarted": False,
        "stationReady": False,
        "evidence": [evidence],
        "boundary": (
            "This report is a semantic pre-screen. A passing result would still "
            "require station geometry, nonprototype CAD and saved-reopen checks."
        ),
    }
    report["auditDigest"] = hashlib.sha256(
        json.dumps(
            report,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return report


def _target_token_matches(raw: Any, *tokens: str) -> bool:
    """Coarse token check; exact CAD source identity is verified afterwards."""
    if not isinstance(raw, str) or not raw:
        return False
    normalized = raw.upper()
    return any(normalized.endswith(str(token).upper()) for token in tokens if token)


def _native_instance(graph: dict, token: str, instance_name: str | None, capture: dict) -> dict:
    if instance_name is None:
        return geometry._module(graph, token)
    if not isinstance(instance_name, str) or not instance_name or instance_name != capture.get("componentName"):
        raise ValueError("native instance selection must match occupancy capture identity")
    rows = [row for row in graph["Modules"] if str(row["ModuleToken"]).upper().endswith(token)
            and row.get("Name") == instance_name]
    if len(rows) != 1:
        raise ValueError("selected native instance is missing or ambiguous")
    return rows[0]


def build_cleaning_service_region_audit(
    workspace: Path, rule: dict[str, Any], cad_result_path: Path | None = None,
    saved_state_path: Path | None = None,
) -> dict[str, Any]:
    """Suggest a support-position Demo, or screen a hash-bound saved CAD result.

    This never compiles a job, starts CAD, expands a region to fit, or promotes
    native occupancy into an engineering-approved allowable service boundary.
    """
    root = workspace.resolve()
    required_identity = ("ruleId", "sourceModuleDefinitionId", "targetBaseDefinitionId", "nativeRoleModuleDefinitionId")
    if not isinstance(rule, dict) or any(not isinstance(rule.get(key), str) or not rule[key] for key in required_identity):
        raise ValueError("cleaning rule requires explicit rule/source/base/native-role identities")
    if rule.get("schemaVersion") != "cleaning-service-region-rule/v1":
        raise ValueError("unsupported cleaning service-region rule schema")
    if rule.get("sourceRole") != "CleaningWeighing":
        raise ValueError("cleaning rule sourceRole must be CleaningWeighing")
    tokens = rule.get("moduleTokens") or {}
    if any(not isinstance(tokens.get(key), str) or not tokens[key] for key in ("source", "targetBase", "nativeRole")):
        raise ValueError("cleaning rule requires explicit source/base/native-role module tokens")
    source_token, base_token, native_role_token = (tokens[key] for key in ("source", "targetBase", "nativeRole"))
    if source_token == base_token:
        raise ValueError("moving module and base must be different identities")
    service_subtrees, excluded_subtrees = rule.get("serviceSubtrees"), rule.get("excludedSubtrees", [])
    if (not isinstance(service_subtrees, list) or not service_subtrees or not isinstance(excluded_subtrees, list)
            or any(not isinstance(value, str) or not value for value in [*service_subtrees, *excluded_subtrees])
            or len(set(service_subtrees + excluded_subtrees)) != len(service_subtrees + excluded_subtrees)):
        raise ValueError("service and explicitly excluded subtree groups must be nonempty/unique/disjoint names")
    if type(rule.get("initialPlacementVariant", 3)) is not int or rule.get("initialPlacementVariant", 3) < 0:
        raise ValueError("cleaning rule initial placement variant must be a nonnegative integer")
    if not isinstance(rule.get("inputs"), dict):
        raise ValueError("cleaning rule is missing required geometry input paths")
    inputs = dict(rule["inputs"])
    inputs.setdefault("datumGraph", rule.get("datumGraph") or (
        str(Path(rule["datumCase"]) / "effective-mate-graph.json") if rule.get("datumCase") else None))
    required_inputs = ("movingOccupancy", "targetOccupancy", "movingNativeGraph", "targetNativeGraph", "datumGraph", "movingFaces", "baseFaces")
    if any(not isinstance(inputs.get(key), str) or not inputs[key] for key in required_inputs):
        raise ValueError("cleaning rule is missing required geometry input paths")
    if any(not isinstance(path, str) or not path for path in inputs.values()):
        raise ValueError("cleaning geometry input paths must be nonempty strings")
    source_paths = {key: (Path(path) if Path(path).is_absolute() else root / path) for key, path in inputs.items()}
    catalog_value = rule.get("moduleCatalogPath", DEFAULT_GLOBAL_MODULE_CATALOG)
    if not isinstance(catalog_value, str) or not catalog_value:
        raise ValueError("cleaning rule moduleCatalogPath must be a nonempty string")
    catalog_path = Path(catalog_value)
    catalog_path = catalog_path if catalog_path.is_absolute() else root / catalog_path
    source_paths["moduleCatalog"] = catalog_path
    missing = [key for key, path in source_paths.items() if not path.is_file()]
    if missing:
        raise ValueError("missing cleaning service inputs: " + ", ".join(missing))
    state_path = saved_state_path
    sources = {key: geometry._read(path) for key, path in source_paths.items()}
    catalog = sources["moduleCatalog"]
    role_overlay = build_module_role_overlay(catalog)
    source_capability = _capability_profile(
        catalog, role_overlay, rule["sourceModuleDefinitionId"]
    )
    target_capability_references = rule.get(
        "targetCapabilityModuleDefinitionIds",
        [rule["nativeRoleModuleDefinitionId"]],
    )
    if (
        not isinstance(target_capability_references, list)
        or not target_capability_references
        or any(
            not isinstance(value, str) or not value
            for value in target_capability_references
        )
        or len(target_capability_references)
        != len(set(target_capability_references))
    ):
        raise ValueError(
            "targetCapabilityModuleDefinitionIds must be a nonempty unique list"
        )
    if rule["nativeRoleModuleDefinitionId"] not in target_capability_references:
        raise ValueError(
            "target capability providers must include the native role module"
        )
    target_capability_profiles = [
        _capability_profile(catalog, role_overlay, reference)
        for reference in target_capability_references
    ]
    required_capabilities = set(source_capability["capabilities"])
    provided_capabilities = {
        capability
        for profile in target_capability_profiles
        for capability in profile["capabilities"]
    }
    missing_capabilities = sorted(required_capabilities - provided_capabilities)
    capability_coverage = {
        "passed": not missing_capabilities,
        "sourceProfile": source_capability,
        "targetProviderProfiles": target_capability_profiles,
        "sourceRequiredCapabilities": sorted(required_capabilities),
        "targetProvidedCapabilities": sorted(provided_capabilities),
        "missingCapabilities": missing_capabilities,
        "method": "reviewed_global_module_role_overlay_set_coverage",
        "claimBoundary": (
            "Capability labels screen semantic completeness only; they do not "
            "prove geometry, process performance, fastening or collision safety."
        ),
    }
    moving_occ, target_occ = sources["movingOccupancy"], sources["targetOccupancy"]
    try:
        moving, native_role = moving_occ["modules"][source_token], target_occ["modules"][native_role_token]
    except KeyError as error:
        raise ValueError("configured source/native-role occupancy is missing") from error
    source_frame = geometry._frame_transform(moving_occ["installationFrame"])
    target_frame = geometry._frame_transform(target_occ["installationFrame"])
    selections = rule.get("nativeGraphInstances") or {}
    if not isinstance(selections, dict):
        raise ValueError("nativeGraphInstances must be an explicit instance mapping")
    native_module = _native_instance(sources["movingNativeGraph"], source_token, selections.get("source"), moving)
    native_role_module = _native_instance(sources["targetNativeGraph"], native_role_token, selections.get("nativeRole"), native_role)
    datum_graph = sources["datumGraph"]
    moving_module, base_module = geometry._module(datum_graph, source_token), geometry._module(datum_graph, base_token)
    moving_graph_token, base_graph_token = moving_module["ModuleToken"], base_module["ModuleToken"]
    native_pose = geometry._transform(native_module["SourceTransform"])
    native_base_pose = geometry._transform(base_module["SourceTransform"])
    if not (moving.get("leafCoverageComplete") is True and native_role.get("leafCoverageComplete") is True):
        raise ValueError("service-region screening requires complete captured leaf occupancy")
    if not (geometry._same_path(moving["filePath"], moving_module["Path"])
            and geometry._same_path(native_module["Path"], moving_module["Path"])
            and geometry._same_path(native_role["filePath"], native_role_module["Path"])
            and geometry._same_path(target_occ["modules"][base_token]["filePath"], base_module["Path"])):
        raise ValueError("service-region source/target module identity mismatch")
    for capture, module, frame in ((moving, native_module, source_frame), (native_role, native_role_module, target_frame)):
        anchor = geometry._point(geometry._transform(module["SourceTransform"])[9:12], frame, inverse=True)
        captured_anchor = capture.get("prototypeAnchorInstallationMeters")
        if not isinstance(captured_anchor, dict) or any(key not in captured_anchor for key in "uvn"):
            raise ValueError("service occupancy capture-frame anchor is missing; bind the original capture frame before reuse")
        # Do not fill absent historical capture data from the graph being checked:
        # doing so would turn an independent frame comparison into a tautology.
        captured_vector = geometry._vector([captured_anchor[key] for key in "uvn"])
        if max(abs(anchor[i] - captured_vector[i]) for i in range(3)) > 1e-8:
            raise ValueError("service occupancy and native graph coordinate frames disagree")
    role_region = native_role["topLevelBoundsInstallationMeters"]
    geometry._corners(role_region)
    mates = {}
    for role in ("LONGITUDINAL", "LATERAL", "SUPPORT"):
        exact_name = (rule.get("datumMateNames") or {}).get(role)
        rows = [row for row in datum_graph["Mates"] if (row["MateName"] == exact_name if exact_name else row["MateName"].endswith("_" + role))]
        if len(rows) != 1 or rows[0].get("Alignment") not in (0, 1):
            raise ValueError(f"registered datum role is not unique: {role}")
        mate = rows[0]
        if {ep["ModuleToken"] for ep in mate["Endpoints"]} != {moving_graph_token, base_graph_token} or len(mate["Endpoints"]) != 2:
            raise ValueError("datum endpoints do not bind the configured source/base pair")
        mates[role] = {"mate": mate, **{ep["ModuleToken"]: ep for ep in mate["Endpoints"]}}
    local_normals, target_normals = [], []
    local_centers = {}
    for role, row in mates.items():
        local_normals.append(geometry._direction(geometry._vector(row[moving_graph_token]["FaceNormalWorld"]), native_pose, inverse=True))
        sign = -1 if row["mate"]["Alignment"] == 1 else 1
        target_normals.append([sign * value for value in geometry._vector(row[base_graph_token]["FaceNormalWorld"])])
        local_centers[role] = geometry._point(geometry._vector(row[moving_graph_token]["FaceCenterWorld"]), native_pose, inverse=True)
    if any(abs(geometry._dot(normals[i], normals[j]) - (1 if i == j else 0)) > 1e-8
           for normals in (local_normals, target_normals) for i in range(3) for j in range(3)):
        raise ValueError("registered three-plane datum frame is not orthonormal")
    # R maps each measured module-local datum normal onto the target datum normal.
    rotation = geometry._transform([
        *(sum(target_normals[k][i] * local_normals[k][j] for k in range(3)) for j in range(3) for i in range(3)),
        0, 0, 0, 1, 0, 0, 0,
    ])

    def root_local(corner: list[float]) -> list[float]:
        return geometry._point(geometry._point(corner, source_frame), native_pose, inverse=True)

    zero_bounds = geometry._bounds([geometry._point(geometry._point(root_local(point), rotation), target_frame, inverse=True)
                                   for point in geometry._corners(moving["topLevelBoundsInstallationMeters"])])
    support_target = geometry._point(geometry._vector(mates["SUPPORT"][base_graph_token]["FaceCenterWorld"]), target_frame, inverse=True)
    support_zero = geometry._point(geometry._point(local_centers["SUPPORT"], rotation), target_frame, inverse=True)
    if abs(abs(geometry._dot(geometry._vector(mates["SUPPORT"][base_graph_token]["FaceNormalWorld"]), target_frame[6:9])) - 1) > 1e-8:
        raise ValueError("native support plane is not the installation frame's height datum")
    shift = [(role_region["min" + axis] + role_region["max" + axis] - zero_bounds["min" + axis] - zero_bounds["max" + axis]) / 2
             for axis in "UV"] + [support_target[2] - support_zero[2]]
    proposed_pose = rotation[:]
    proposed_pose[9:12] = geometry._direction(shift, target_frame)
    parameters = {"supportGap": 0.0}
    for role in ("LONGITUDINAL", "LATERAL"):
        point = geometry._point(local_centers[role], proposed_pose)
        base = mates[role][base_graph_token]
        signed = geometry._dot([point[i] - base["FaceCenterWorld"][i] for i in range(3)], geometry._vector(base["FaceNormalWorld"]))
        if signed < 0:
            raise ValueError("native-service candidate requires an unsupported negative datum distance branch")
        parameters[role.lower()] = signed

    pose, current_base_pose = proposed_pose, native_base_pose
    current_components = []
    cad_binding = None
    if state_path is not None and cad_result_path is None:
        raise ValueError("a live state requires its matching saved CAD result")
    if cad_result_path is not None:
        if state_path is None:
            raise ValueError("saved CAD service-region review requires a readonly state with actual base pose")
        cad_path = Path(cad_result_path)
        cad_path = cad_path if cad_path.is_absolute() else root / cad_path
        cad = geometry._read(cad_path)
        graph_path = Path(cad.get("executionEffectiveGraphPath") or cad["effectiveGraphPath"])
        expected_graph_hash = cad.get("executionEffectiveGraphSha256") or cad.get("effectiveGraphSha256")
        output_path = Path(cad["outputAssemblyPath"])
        tool = cad["toolResult"]
        if (not all(value is True for value in (cad.get("success"), tool.get("Success"), tool.get("Reopened"),
                tool.get("ReopenedMateParametersMatch"), tool.get("TargetFullyConstrained"), tool.get("MateSolveClean")))
                or geometry._sha256(graph_path) != expected_graph_hash
                or geometry._sha256(output_path) != cad.get("outputAssemblySha256")
                or not _target_token_matches(
                    tool.get("TargetModuleToken"), source_token, moving_graph_token
                )):
            raise ValueError("saved CAD result/graph/output binding failed")
        current_graph = geometry._read(graph_path)
        for token, expected in ((source_token, moving_module), (base_token, base_module)):
            if not geometry._same_path(geometry._module(current_graph, token)["Path"], expected["Path"]):
                raise ValueError("saved CAD module identity differs from service-region sources")
        state_file = Path(state_path)
        state_file = state_file if state_file.is_absolute() else root / state_file
        state = geometry._read(state_file)
        if (state.get("success") is not True or state.get("observed", {}).get("readOnly") is not True
                or not state.get("checks") or not all(value is True for value in state["checks"].values())
                or not geometry._same_path(str(state.get("assemblyPath", "")), str(output_path))
                or state.get("assemblySha256") != cad["outputAssemblySha256"]):
            raise ValueError("readonly state does not bind the saved CAD output")
        current_components = state["observed"].get("components", [])
        bound = {}
        for token, expected in ((source_token, moving_module), (base_token, base_module)):
            rows = [row for row in current_components if geometry._same_path(str(row.get("sourcePath", "")), expected["Path"])]
            if len(rows) != 1 or rows[0].get("name") != expected["Name"] or not rows[0].get("configuration"):
                raise ValueError(f"readonly state component identity/configuration mismatch: {token}")
            bound[token] = rows[0]
        pose = geometry._transform(bound[source_token]["transform"])
        if max(abs(a - b) for a, b in zip(pose, geometry._transform(tool["ReopenedTargetRootTransform"]), strict=True)) > 1e-8:
            raise ValueError("readonly state moving-module pose differs from reopened CAD result")
        current_base_pose = geometry._transform(bound[base_token]["transform"])
        source_paths.update(cadResult=cad_path, executionGraph=graph_path, savedCad=output_path, readonlyState=state_file)
        cad_binding = {"cadResultPath": str(cad_path), "cadResultSha256": geometry._sha256(cad_path),
                       "effectiveGraphSha256": expected_graph_hash, "outputAssemblySha256": cad["outputAssemblySha256"],
                       "readonlyStatePath": str(state_file), "readonlyStateSha256": geometry._sha256(state_file),
                       "actualBaseRootTransform": current_base_pose, "actualTargetRootTransform": pose}

    def world_in_installation(world: list[float]) -> list[float]:
        native_world = geometry._point(geometry._point(world, current_base_pose, inverse=True), native_base_pose)
        return geometry._point(native_world, target_frame, inverse=True)

    def installation_point(local: list[float]) -> list[float]:
        return world_in_installation(geometry._point(local, pose))

    def projected(bounds: dict[str, float]) -> dict[str, float]:
        return geometry._bounds([installation_point(root_local(point)) for point in geometry._corners(bounds)])

    whole = projected(moving["topLevelBoundsInstallationMeters"])
    if {row["subtree"] for row in moving["occupancyBoxes"]} != {*service_subtrees, *excluded_subtrees}:
        raise ValueError("service subtree grouping changed; explicit proxy scope requires review")
    groups = []
    for name in service_subtrees:
        rows = [row for row in moving["occupancyBoxes"] if row["subtree"] == name]
        if (
            len(rows) != 1
            or rows[0].get("source") not in COMPLETE_SERVICE_SUBTREE_SOURCES
        ):
            raise ValueError(f"service subtree has no unique captured geometry: {name}")
        footprint = projected(rows[0]["installationBoundsMeters"])
        groups.append({"subtree": name, "footprintInstallationMeters": footprint,
                       "nativeRoleEnvelopeRelation": geometry.planar_relation(footprint, role_region)})
    for catalog_key, expected, expected_pose in (("movingFaces", moving_module, native_pose), ("baseFaces", base_module, native_base_pose)):
        catalog_modules = [row for row in sources[catalog_key]["Modules"]
                           if geometry._same_path(row["Path"], expected["Path"]) and row["HierarchyPath"] == expected["HierarchyPath"]]
        if len(catalog_modules) != 1 or max(abs(a - b) for a, b in zip(
                geometry._transform(catalog_modules[0]["SourceTransform"]), expected_pose, strict=True)) > 1e-8:
            raise ValueError("support face catalog module identity/coordinate pose mismatch")
    support = mates["SUPPORT"][base_graph_token]
    support_leaf = geometry._leaf_transform(sources["baseFaces"], support)
    moving_support = mates["SUPPORT"][moving_graph_token]
    moving_leaf = geometry._leaf_transform(sources["movingFaces"], moving_support)

    def face_corners(endpoint: dict[str, Any]) -> list[list[float]]:
        box = geometry._vector(endpoint["FaceBoxLocal"], 6)
        return [list(point) for point in itertools.product(*[(box[i], box[i + 3]) for i in range(3)])]

    support_bounds = geometry._bounds([geometry._point(geometry._point(point, support_leaf), target_frame, inverse=True)
                                      for point in face_corners(support)])
    contact_bounds = geometry._bounds([installation_point(geometry._point(geometry._point(point, moving_leaf), native_pose, inverse=True))
                                      for point in face_corners(moving_support)])
    contact = geometry.planar_relation(contact_bounds, support_bounds)
    service_passed = all(row["nativeRoleEnvelopeRelation"]["envelopeContained"] for row in groups)
    whole_relation = geometry.planar_relation(whole, role_region)
    support_relation = geometry.planar_relation(whole, support_bounds)
    transport_rule = rule.get("transportContext")
    transport = {"passed": None, "status": "not_evaluated", "method": "current_transport_identity_pose_and_bounds_binding",
                 "reason": "No exact configured current Transport instance is bound to this prediction/pair.", "collisionPassed": None}
    if transport_rule is not None:
        if (not isinstance(transport_rule, dict) or not transport_rule.get("moduleDefinitionId") or not transport_rule.get("moduleToken")
                or transport_rule.get("occupancyInput") not in sources or transport_rule.get("nativeGraphInput") not in sources):
            raise ValueError("configured transport requires identity, token and available occupancy/native-graph inputs")
    if current_components and transport_rule:
        transport_token = transport_rule["moduleToken"]
        transport_occ = sources[transport_rule["occupancyInput"]]
        try:
            transport_capture = transport_occ["modules"][transport_token]
        except KeyError as error:
            raise ValueError("configured transport occupancy is missing") from error
        transport_module = geometry._module(sources[transport_rule["nativeGraphInput"]], transport_token)
        transport_rows = [row for row in current_components if row.get("name") == transport_module["Name"]
                          or geometry._same_path(str(row.get("sourcePath", "")), transport_module["Path"])]
        if transport_rows:
            if (len(transport_rows) != 1 or transport_rows[0].get("name") != transport_module["Name"]
                    or not geometry._same_path(str(transport_rows[0].get("sourcePath", "")), transport_module["Path"])
                    or not geometry._same_path(transport_capture["filePath"], transport_module["Path"]) or not transport_rows[0].get("configuration")):
                raise ValueError("current transport identity/configuration mismatch")
            transport_row = transport_rows[0]
            transport_pose = geometry._transform(transport_row["transform"])
            if transport_row.get("boundingBoxWorld") is not None:
                box = geometry._vector(transport_row["boundingBoxWorld"], 6)
                if any(box[i] > box[i + 3] for i in range(3)):
                    raise ValueError("current transport bounding box is reversed")
                world_corners = [list(point) for point in itertools.product(*[(box[i], box[i + 3]) for i in range(3)])]
                bounds_source = "current_readonly_snapshot_world_aabb"
            else:
                if transport_capture.get("leafCoverageComplete") is not True:
                    raise ValueError("transport proxy projection requires complete captured leaf occupancy")
                transport_native = geometry._transform(transport_module["SourceTransform"])
                transport_frame = geometry._frame_transform(transport_occ["installationFrame"])
                world_corners = [geometry._point(geometry._point(geometry._point(point, transport_frame), transport_native, inverse=True), transport_pose)
                                 for point in geometry._corners(transport_capture["topLevelBoundsInstallationMeters"])]
                bounds_source = "prototype_local_occupancy_projected_by_current_transport_pose_demo_proxy"
            transport_bounds = geometry._bounds([world_in_installation(point) for point in world_corners])
            relations = []
            for group in groups:
                footprint = group["footprintInstallationMeters"]
                separation = {axis: max(0.0, footprint["min" + axis] - transport_bounds["max" + axis],
                                        transport_bounds["min" + axis] - footprint["max" + axis]) for axis in "UVN"}
                relations.append({"subtree": group["subtree"], "axisSeparationMeters": separation,
                    "signedAboveTransportGapMeters": footprint["minN"] - transport_bounds["maxN"],
                    "signedServiceSideGapMeters": footprint["minV"] - transport_bounds["maxV"],
                    "aabbOverlapsOnAllAxes": all(value <= 1e-8 for value in separation.values()),
                    "planarOverlapAreaSquareMeters": geometry.planar_relation(footprint, transport_bounds)["overlapAreaSquareMeters"]})
            transport = {"passed": True, "status": "passed", "method": "current_transport_identity_pose_and_bounds_binding",
                "moduleDefinitionId": transport_rule["moduleDefinitionId"],
                "component": {"name": transport_row["name"], "sourcePath": transport_row["sourcePath"], "configuration": transport_row["configuration"],
                              "rootTransform": transport_pose}, "boundsSource": bounds_source, "boundsInstallationMeters": transport_bounds,
                "serviceSubtreeRelations": relations, "collisionPassed": None,
                "claimBoundary": "True binds the exact configured current Transport context only; AABB distances/overlaps are Demo measurements, not noncollision or process certification."}
    report = {
        "schemaVersion": "cleaning-service-region-audit/v1", "source": rule["sourceModuleDefinitionId"], "target": rule["targetBaseDefinitionId"],
        "nativeRole": rule["nativeRoleModuleDefinitionId"], "sourceRole": rule["sourceRole"], "readOnly": True, "cadStarted": False,
        "ruleId": rule["ruleId"], "ruleDigest": hashlib.sha256(json.dumps(rule, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "evaluationMode": "saved_cad_reopen_geometry" if cad_binding else "analytical_candidate_prediction_only",
        "cadBinding": cad_binding, "evidence": geometry._evidence(*source_paths.values()),
        "serviceRegion": {"sourceKind": "native_role_occupancy_demo_proxy", "installationFrame": target_occ["installationFrame"],
            "boundsInstallationMeters": role_region, "nativeRoleSourcePath": native_role["filePath"],
            "engineeringApproved": False, "boundaryExpandedToFitCandidate": False,
            "reason": "The configured native role's measured complete occupancy is a target-side Demo reference, not a registered allowed work/service envelope."},
        "candidateSuggestion": {"strategy": "support_position_demo", "source": "target_native_role_envelope_center_and_registered_datum_normals",
            "positionParameters": parameters, "initialPlacementMode": "deterministic", "initialPlacementVariant": rule.get("initialPlacementVariant", 3),
            "prototypePoseUsedForPlacement": False, "copySourceWorldPose": False,
            "predictedRootTransformMeasurementOnly": proposed_pose,
            "physicalFasteningVerified": False, "actualFixingMethod": "not_verified"},
        "serviceSubtreeProxy": {"selection": "explicit_non_common_subtree_groups_not_verified_functional_faces", "groups": groups,
            "withinNativeRoleEnvelope": service_passed, "engineeringServiceRegionPassed": None},
        "capabilityCoverage": capability_coverage,
        "fullEnvelope": {"footprintInstallationMeters": whole, "nativeRoleEnvelopeRelation": whole_relation,
            "supportFaceOuterBoundRelation": support_relation, "fullEnvelopeContainmentPolicyRegistered": False},
        "selectedSupportContact": {"footprintInstallationMeters": contact_bounds, "supportBoundsInstallationMeters": support_bounds,
            "outerBoundRelation": contact, "trimmedContactAndOtherFeetVerified": None},
        "serviceRegionDemoPassed": service_passed, "serviceRegionEngineeringPassed": None,
        "slotMembership": None, "transportContext": transport["passed"], "transportContextCheck": transport,
        "stationReady": False, "cadExecutionAuthorized": False,
        "requiredReview": ([{
            "code": "TARGET_SERVICE_CAPABILITIES_INCOMPLETE",
            "message": "Target service providers do not cover all source-module capabilities.",
            "missingCapabilities": missing_capabilities,
        }] if missing_capabilities else []) + ["Moving-module whole-envelope transverse excess must not be silently accepted",
            "Explicit service-function points/faces and allowable service envelope remain unregistered",
            "Selected contact-face AABB is not trimmed contact, every foot or a cantilever approval",
            "Current Transport instance/pose requires separate context-bound verification"],
    }
    report["auditDigest"] = hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return report


def build_gn00_aa00_service_region_audit(
    workspace: Path, *, cad_result_path: Path | None = None, state_path: Path | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper; all combination-specific geometry lives in data."""
    rule_path = workspace.resolve() / DEFAULT_RULE
    report = build_cleaning_service_region_audit(workspace, geometry._read(rule_path), cad_result_path, state_path)
    report["evidence"].extend(geometry._evidence(rule_path))
    report["auditDigest"] = hashlib.sha256(json.dumps({key: value for key, value in report.items() if key != "auditDigest"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return report

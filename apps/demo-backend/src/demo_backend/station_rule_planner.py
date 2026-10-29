"""Resolve registered target stations using the existing geometry builders.

This is the planning phase of the ordinary staged-chain entry, not a second
executor. Geometry-derived parameters produce new validation candidates; old
release authority is never silently applied to those changed parameters.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import Path
from time import perf_counter

from .station_rule_registry import (
    DEFAULT_REGISTRY, StationRuleError, bind_rule_instances, digest,
    load_station_registry, read, revalidate_rule_binding, scope_identity,
    select_station_rule, sha, workspace_file,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def confirmed_identity(selection):
    if not isinstance(selection, dict) or selection.get("confirmed") is not True:
        raise StationRuleError("CONFIRMED_MODULE_SELECTION_REQUIRED")
    if not selection.get("projectId") or not selection.get("moduleToken"):
        raise StationRuleError("PROJECT_AND_MODULE_REQUIRED")
    return f"{selection['projectId']}::{selection['moduleToken']}"


def rule_requires_datum_fallback_authorization(workspace, binding):
    """Return whether this station will actually execute a datum recipe.

    A native cleaning role uses its immutable direct mechanical release; its
    measured service region is only a postcheck.  Treating that case as a
    datum fallback forces callers to authorize a mode that is never executed.
    The deeper authority checks in ``plan_station_stage`` remain mandatory.
    """

    rule = binding["rule"]
    if (rule.get("placement") or {}).get("strategy") == "released_recipe":
        return False
    if (rule.get("evaluator") or {}).get("kind") == "cleaning_service_region":
        config = read(workspace_file(workspace, rule["evaluator"]["inputPath"]))
        if rule.get("sourceModuleDefinitionId") == config.get(
            "nativeRoleModuleDefinitionId"
        ):
            return False
    return True


def parameters(value):
    if (not isinstance(value, dict) or set(value) != {"longitudinal", "lateral", "supportGap"}
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in value.values())):
        raise StationRuleError("POSITION_REQUIRES_THREE_FINITE_NONNEGATIVE_METRE_VALUES")
    return dict(value)


def cup_distance_flips(geometry):
    directions = geometry["stationSuggestion"]["mateParameters"]
    flips = {row["parameter"]: row["suggestedDistanceFlipDimension"] for row in directions}
    if len(directions) != 2 or set(flips) != {"longitudinal", "lateral"} or any(type(v) is not bool for v in flips.values()):
        raise StationRuleError("CUP_DISTANCE_DIRECTION_MISSING_OR_AMBIGUOUS")
    return {**flips, "supportGap": False}


def transport_position_postcheck_status(plan_geometry):
    """Keep CAD datum closure separate from transport work-area acceptance."""

    authorization = (plan_geometry or {}).get("candidateAuthorization") or {}
    if (
        authorization.get("kind")
        == "target_native_station_nonprototype_cad_trial"
        and authorization.get("trackAndWorkAreaFitConfirmed") is False
    ):
        return {
            "proxyGeometryPassed": False,
            "publicationBlockedReasonCode": (
                "TRANSPORT_TRACK_AND_WORK_AREA_POSTCHECK_REQUIRED"
            ),
        }
    return {
        "proxyGeometryPassed": True,
        "publicationBlockedReasonCode": None,
    }


def resolve_parameter_recipe(workspace, binding, effective):
    """Select an exact parameter variant without replacing the default recipe."""
    registry = read(workspace_file(workspace, binding["registryPath"]))
    rows = [r for r in registry.get("parameterRecipes", [])
            if r.get("ruleId") == binding["rule"]["ruleId"]
            and _same_geometry(parameters(r.get("positionParametersMeters")), effective)]
    if not rows:
        return None, []
    if len(rows) != 1:
        raise StationRuleError("PARAMETER_RECIPE_AMBIGUOUS")
    row = rows[0]
    paths = {k: workspace_file(workspace, row[k]) for k in
             ("planPath", "cadResultPath", "savedStatePath", "releaseManifestPath")}
    plan = read(paths["planPath"])
    strip_validation = lambda rule: {k: v for k, v in rule.items() if k != "validation"}
    if (strip_validation(plan["ruleBinding"]["rule"]) != strip_validation(binding["rule"])
            or not _same_geometry(plan.get("effectivePositionParametersMeters"), effective)):
        raise StationRuleError("PARAMETER_RECIPE_RULE_OR_PARAMETERS_CHANGED")
    result = verify_station_stage(workspace, plan, cad_result_path=paths["cadResultPath"],
                                  saved_state_path=paths["savedStatePath"])
    if result.get("targetStationValidated") is not True:
        raise StationRuleError("PARAMETER_RECIPE_CURRENT_POSTCHECK_FAILED")
    from .global_relation_catalog_release import load_relation_catalog_release
    _, release = load_relation_catalog_release(paths["releaseManifestPath"], workspace_root=Path(workspace))
    metadata = release.get("releaseMetadata") or {}
    pair = metadata.get("parameterizedDatumPairBinding") or {}
    if (metadata.get("relationExecutionMode") != "datum_placement_demo"
            or pair.get("moduleDefinitionId") != binding["rule"]["sourceModuleDefinitionId"]
            or pair.get("slotDefinitionId") != binding["rule"]["targetBaseDefinitionId"]
            or pair.get("cadResultSha256") != sha(paths["cadResultPath"])):
        raise StationRuleError("PARAMETER_RECIPE_RELEASE_MISMATCH")
    return {"releaseManifestPath": str(paths["releaseManifestPath"]),
            "releaseManifestSha256": sha(paths["releaseManifestPath"]),
            "relationExecutionMode": "datum_placement_demo"}, [
                *plan["evidence"], *[{"path": str(p), "sha256": sha(p)} for p in paths.values()]]


def inserted_token_matches(token, definition, verified_source_path):
    """Accept short alias or exact CAD filename identity, never suffix guesses.

    Caller must first resolve verified_source_path against the selected catalog
    module. A different project's same-role filename cannot pass this check.
    """
    return token in {definition.split("::")[1], Path(verified_source_path).name.split(".")[0]}


def plan_digest(plan):
    semantic = deepcopy({k: v for k, v in plan.items() if k not in {"planDigest", "timing"}})
    if isinstance(semantic.get("geometry"), dict):
        for key in ("startedAtUtc", "finishedAtUtc", "durationSeconds"):
            semantic["geometry"].pop(key, None)
    return digest(semantic)


def _same_geometry(a, b):
    if type(a) in (int, float) and type(b) in (int, float):
        return math.isfinite(a) and math.isfinite(b) and abs(a-b) <= 1e-9
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_geometry(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same_geometry(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def bind_executed_candidate_parameters(expected_graph, actual_graph):
    """Match actual mate faces/parameters independently of generated mate names."""
    endpoint_fields = ("ModuleToken", "RelativeLeafHierarchyPath", "LeafComponentPath", "GeometryType",
        "BodyIndex", "FaceIndexInBody", "SurfaceType", "FaceCenterLocal", "FaceNormalLocal", "FaceArea")
    def signature(mate):
        endpoints = [{k: ep.get(k) for k in endpoint_fields} for ep in mate.get("Endpoints") or []]
        endpoints.sort(key=lambda ep: (str(ep["ModuleToken"]), str(ep["RelativeLeafHierarchyPath"])))
        return {"type": mate.get("MateType"), "alignment": mate.get("Alignment"), "distance": mate.get("Distance"),
            "options": mate.get("AdvancedOptions") or {}, "suppressed": mate.get("IsSuppressed", False), "endpoints": endpoints}
    expected, actual = expected_graph.get("Mates") or [], actual_graph.get("Mates") or []
    if not expected or len(expected) != len(actual):
        raise StationRuleError("EXECUTED_STATION_MATE_COUNT_DIFFERS")
    mapping = {}
    for mate in expected:
        matches = [row for row in actual if _same_geometry(signature(row), signature(mate))]
        if len(matches) != 1 or matches[0].get("MateName") in mapping.values():
            raise StationRuleError("EXECUTED_STATION_ENDPOINT_OR_PARAMETER_DIFFERS")
        mapping[mate["MateName"]] = matches[0]["MateName"]
    return mapping


def verify_released_station_graph(workspace, release_path, target_token, actual_graph, *, verified_source_path=None):
    """Compare this packet with hash-bound CAD evidence of the chosen release.

    World transforms and generated names are deliberately not positioning
    authority. The released local endpoints and mate parameters are.
    """
    from .global_relation_catalog_release import load_relation_catalog_release
    root = Path(workspace)
    _, manifest = load_relation_catalog_release(
        workspace_file(root, release_path), workspace_root=root)
    matches = []
    for evidence in manifest.get("validationEvidence") or []:
        path = workspace_file(root, evidence["path"])
        if sha(path) != evidence.get("fileSha256"):
            raise StationRuleError("RELEASED_STATION_CAD_EVIDENCE_CHANGED")
        cad = read(path)
        evidence_token = (cad.get("toolResult") or {}).get("TargetModuleToken")
        allowed_tokens = {target_token}
        if verified_source_path:
            allowed_tokens.add(Path(verified_source_path).name.split(".")[0])
        if evidence_token not in allowed_tokens:
            continue
        prefix = "executionEffectiveGraph" if cad.get("executionEffectiveGraphPath") else "effectiveGraph"
        graph_path = workspace_file(root, cad[prefix + "Path"])
        if sha(graph_path) != cad.get(prefix + "Sha256"):
            raise StationRuleError("RELEASED_STATION_GRAPH_CHANGED")
        try:
            mapping = bind_executed_candidate_parameters(read(graph_path), actual_graph)
        except StationRuleError:
            continue
        matches.append({"referenceGraphPath": str(graph_path),
                        "referenceGraphSha256": sha(graph_path), "mateMapping": mapping})
    if not matches:
        raise StationRuleError("CURRENT_MATES_DIFFER_FROM_RELEASED_STATION")
    return {"status": "current_mates_match_released_target_datums",
            "matchingEvidence": matches, "proxyGeometryPassed": True,
            "sourceWorldPoseCopied": False, "processFunctionVerified": False}


def _released_port_id(catalog, claimed_port_id):
    """Resolve one global id or semantic alias inside an authenticated release."""

    matches = []
    for port in catalog.get("semanticPorts") or []:
        if claimed_port_id == port.get("globalPortId") or claimed_port_id in set(
            port.get("aliases") or []
        ):
            matches.append(port)
    if len(matches) != 1:
        raise StationRuleError("REGISTERED_TARGET_STATION_PORT_NOT_UNIQUE_IN_RELEASE")
    return matches[0]


def _registered_release_recipe(
    workspace, config, authority, *, source_definition_id, base_definition_id
):
    """Authenticate the exact immutable recipe recorded by a station rule.

    A current interface contract can instantiate the same endpoint under an
    alias-level id and with generated mate names.  Registered station evidence
    remains bound to the release catalog itself: its path, endpoint ownership,
    authorized template and full-location claim are all revalidated here.
    """

    from .global_relation_catalog_release import load_relation_catalog_release

    expected_release_path = workspace_file(
        workspace, config["inputs"]["referenceReleasePath"]
    )
    current_direct = bool(
        authority.get("ready") is True
        and authority.get("relationExecutionMode") == "direct_installation"
    )
    explicit_missing_catalog_fallback = bool(
        config.get("allowExplicitImmutableReleaseWhenCurrentCatalogMissing") is True
        and authority.get("ready") is not True
        and ((authority.get("preferredPlan") or {}).get("nativePlan") or {}).get(
            "status"
        )
        in {"module_not_registered", "no_compatible_slot"}
    )
    if current_direct:
        release_path = workspace_file(workspace, authority["releaseManifestPath"])
        if release_path != expected_release_path:
            raise StationRuleError("TARGET_STATION_REFERENCE_RELEASE_CHANGED")
    elif explicit_missing_catalog_fallback:
        release_path = expected_release_path
    else:
        raise StationRuleError("CURRENT_AUTHORITY_DIFFERS_FROM_REGISTERED_TARGET_STATION")

    catalog, manifest = load_relation_catalog_release(
        release_path, workspace_root=workspace
    )
    source_port = _released_port_id(catalog, config.get("sourcePortId"))
    target_port = _released_port_id(catalog, config.get("targetPortId"))
    if (
        source_port.get("moduleDefinitionId") != source_definition_id
        or target_port.get("moduleDefinitionId") != base_definition_id
    ):
        raise StationRuleError("REGISTERED_TARGET_STATION_PORT_OWNER_MISMATCH")

    authorized = set(
        (manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or []
    )
    source_port_id = source_port["globalPortId"]
    target_port_id = target_port["globalPortId"]
    candidates = []
    for template in catalog.get("connectionTemplates") or []:
        if template.get("globalTemplateId") not in authorized:
            continue
        side_a = set(template.get("candidatePortIdsA") or [])
        side_b = set(template.get("candidatePortIdsB") or [])
        if not (
            (source_port_id in side_a and target_port_id in side_b)
            or (source_port_id in side_b and target_port_id in side_a)
        ):
            continue
        if (
            template.get("constraintEffect", {}).get("fullyLocatesAddedComponent")
            is not True
        ):
            continue
        candidates.append(template)

    expected_template_id = config.get("expectedGlobalTemplateId")
    if expected_template_id:
        candidates = [
            template
            for template in candidates
            if template.get("globalTemplateId") == expected_template_id
        ]
    if len(candidates) != 1:
        raise StationRuleError(
            "REGISTERED_TARGET_STATION_RELEASED_RECIPE_NOT_UNIQUE"
        )
    if explicit_missing_catalog_fallback:
        from .global_interface_contract_planner import (
            _released_template_safety_blockers,
        )

        if _released_template_safety_blockers(
            workspace, {candidates[0]["globalTemplateId"]}
        ):
            raise StationRuleError(
                "REGISTERED_TARGET_STATION_RELEASED_RECIPE_REVOKED"
            )
    return release_path, candidates[0]


def plan_station_stage(workspace, binding, instance_binding, *, position_override=None,
                       prepare_candidate=False):
    started, clock = now(), perf_counter()
    workspace = Path(workspace)
    revalidate_rule_binding(workspace, binding)
    core = {k: v for k, v in instance_binding.items() if k != "contextDigest"}
    if (digest(core) != instance_binding.get("contextDigest")
            or core.get("ruleDigest") != binding["review"]["ruleDigest"]
            or core.get("registrySha256") != binding["registrySha256"]):
        raise StationRuleError("STATION_INSTANCE_BINDING_CHANGED")
    rule = binding["rule"]
    config_path = workspace_file(workspace, rule["evaluator"]["inputPath"])
    config = read(config_path)
    kind = rule["evaluator"]["kind"]
    calculated, geometry, evidence = None, None, []
    distance_flips = None
    registered_direct_authority = None
    if kind == "cleaning_service_region":
        from .cleaning_service_region import build_cleaning_service_region_audit
        geometry = build_cleaning_service_region_audit(workspace, config)
        if (geometry.get("capabilityCoverage") or {}).get("passed") is not True:
            raise StationRuleError("TARGET_SERVICE_CAPABILITIES_INCOMPLETE")
        if geometry.get("serviceRegionDemoPassed") is not True:
            raise StationRuleError("PREDICTED_CLEANING_SERVICE_REGION_FAILED")
        calculated = parameters(geometry["candidateSuggestion"]["positionParameters"])
        evidence = geometry["evidence"]
    elif kind == "bounded_role_station":
        from .bounded_role_station import build_bounded_role_station_candidate

        geometry = build_bounded_role_station_candidate(workspace, config)
        if (
            (geometry.get("nativeRoleStationContainment") or {}).get("passed") is not True
            or (geometry.get("finiteSupportGate") or {}).get("passed") is not True
            or geometry.get("normalReleasedExecutionAllowed") is not False
        ):
            raise StationRuleError("BOUNDED_ROLE_STATION_CANDIDATE_INVALID")
        calculated = parameters(geometry["positionParametersMeters"])
        distance_flips = geometry["distanceFlipDimensions"]
        evidence = [
            geometry["roleStationAudit"],
            {
                "path": geometry["endpointReuse"]["referenceReleasePath"],
                "sha256": geometry["endpointReuse"]["referenceReleaseSha256"],
            },
        ]
    elif kind == "cup_projection":
        from .cup_function_point import build_cup_function_point_report
        geometry = build_cup_function_point_report(workspace_file(workspace, config["inputs"]["geometryRequestPath"]))
        source = read(workspace_file(workspace, config["inputs"]["geometryRequestPath"]))
        if (source["source"]["moduleDefinitionId"] != rule["sourceModuleDefinitionId"]
                or source["stationSuggestion"]["baseToken"] != rule["targetBaseDefinitionId"].split("::")[1]
                or source["native"]["moduleDefinitionId"] != config["nativeRoleModuleDefinitionId"]):
            raise StationRuleError("CUP_FUNCTION_POINT_IDENTITY_MISMATCH")
        if geometry.get("allRequestedCatalogsHaveMouthEvidence") is not True:
            raise StationRuleError("CUP_MOUTH_GEOMETRY_MISSING")
        calculated = parameters(geometry["stationSuggestion"]["positionParametersMeters"])
        distance_flips = cup_distance_flips(geometry)
        evidence = geometry["evidence"]
    elif kind == "transport_position_parameters":
        expected = config.get("positionParametersMeters")
        if not isinstance(expected, dict) or set(expected) != {
            "longitudinal", "lateral", "supportGap"
        }:
            raise StationRuleError("TRANSPORT_POSITION_PARAMETERS_INCOMPLETE")
        calculated = parameters(expected)
        confirmation = config.get("engineeringConfirmation") or {}
        candidate_authorization = config.get("candidateAuthorization") or {}
        native_authorization = config.get("nativeStationAuthorization") or {}
        native_authorized = bool(
            native_authorization.get("authorized") is True
            and native_authorization.get("kind")
            == "exact_native_role_station_identity"
            and native_authorization.get("sourceModuleDefinitionId")
            == rule["sourceModuleDefinitionId"]
            and native_authorization.get("targetBaseDefinitionId")
            == rule["targetBaseDefinitionId"]
            and config.get("nativeRoleModuleDefinitionId")
            == rule["sourceModuleDefinitionId"]
            and rule["sourceModuleDefinitionId"].split("::", 1)[0]
            == rule["targetBaseDefinitionId"].split("::", 1)[0]
            and len(str(native_authorization.get("nativeStationEvidenceDigest") or ""))
            == 64
            and str(native_authorization.get("source") or "").strip()
        )
        engineering_confirmed = bool(
            confirmation.get("confirmed") is True
            and all(str(confirmation.get(key) or "").strip()
                    for key in ("source", "confirmedBy", "confirmedAt"))
        )
        trial_authorized = bool(
            candidate_authorization.get("authorized") is True
            and candidate_authorization.get("kind")
            == "target_native_station_nonprototype_cad_trial"
            and candidate_authorization.get("targetStationReuseConfirmed") is True
            and candidate_authorization.get("trackAndWorkAreaFitConfirmed") is False
            and candidate_authorization.get("authorizationScope")
            == "nonprototype_cad_trial_only"
            and all(
                str(candidate_authorization.get(key) or "").strip()
                for key in ("source", "authorizedBy", "authorizedAt")
            )
            and len(str(candidate_authorization.get("decisionPacketDigest") or ""))
            == 64
            and len(
                str(candidate_authorization.get("nativeStationEvidenceDigest") or "")
            )
            == 64
        )
        if not engineering_confirmed and not native_authorized and not trial_authorized:
            raise StationRuleError(
                "TRANSPORT_STATION_ENGINEERING_OR_NATIVE_AUTHORIZATION_MISSING"
            )
        geometry = {
            "status": (
                "native_transport_target_station_requires_current_cad"
                if native_authorized
                else "target_native_station_trial_requires_current_cad_and_work_area_postcheck"
                if trial_authorized
                else "confirmed_transport_target_station_requires_current_cad"
            ),
            "positionParametersMeters": calculated,
            "engineeringConfirmation": confirmation if engineering_confirmed else None,
            "candidateAuthorization": (
                candidate_authorization if trial_authorized else None
            ),
            "nativeStationAuthorization": (
                native_authorization if native_authorized else None
            ),
            "trackAndWorkAreaFit": (
                "requires_current_cad_and_work_area_postcheck"
                if trial_authorized
                else "accepted_for_demo_only"
            ),
            "proxyGeometryPassed": None,
            "sourceWorldPoseCopied": False,
        }
    elif kind in {"scanner_target", "scanner_point_pair"}:
        # No synthetic current state: the scanner rule is evaluated after real
        # CAD insertion against its explicitly bound transport instance.
        geometry = {"status": "requires_current_saved_cad_state", "proxyGeometryPassed": None,
                    "transportInstance": instance_binding["instances"]["Transport"],
                    "sourceWorldPoseCopied": False}
    elif kind in {"released_mate_parameters", "native_cup_station", "native_cleaning_station"}:
        from .global_interface_contract_planner import resolve_preferred_released_interface_authority
        scope = read(workspace_file(workspace, binding["scopePath"]))
        source_id = scope_identity(scope, rule["sourceModuleDefinitionId"])["cadModuleDefinitionId"]
        base_id = scope_identity(scope, rule["targetBaseDefinitionId"], base=True)["cadModuleDefinitionId"]
        authority = resolve_preferred_released_interface_authority(workspace, source_id, selected_slot_definition_id=base_id)
        if config.get("expectedGlobalTemplateId"):
            release_path, template = _registered_release_recipe(
                workspace,
                config,
                authority,
                source_definition_id=source_id,
                base_definition_id=base_id,
            )
        else:
            # Legacy configs predate explicit immutable template ids.  Preserve
            # their existing unique current-contract selection; do not guess
            # among multiple authorized templates in a historical release.
            native = (authority.get("preferredPlan") or {}).get("nativePlan") or {}
            template = native.get("instantiatedTemplate") or {}
            if (
                authority.get("ready") is not True
                or authority.get("relationExecutionMode") != "direct_installation"
                or template.get("modulePortId") != config.get("sourcePortId")
                or template.get("slotPortId") != config.get("targetPortId")
                or template.get("constraintEffect", {}).get(
                    "fullyLocatesAddedComponent"
                )
                is not True
            ):
                raise StationRuleError(
                    "CURRENT_AUTHORITY_DIFFERS_FROM_REGISTERED_TARGET_STATION"
                )
            release_path = workspace_file(workspace, authority["releaseManifestPath"])
            from .global_relation_catalog_release import load_relation_catalog_release

            load_relation_catalog_release(release_path, workspace_root=workspace)
            if release_path != workspace_file(
                workspace, config["inputs"]["referenceReleasePath"]
            ):
                raise StationRuleError("TARGET_STATION_REFERENCE_RELEASE_CHANGED")
        registered_direct_authority = authority
        geometry = {"status": "registered_target_mounting_datums_not_current_cad",
            "authority": authority, "targetPortId": config["targetPortId"],
            "mateRecipe": template, "proxyGeometryPassed": None,
            "currentMatePostcheckRequired": True, "sourceWorldPoseCopied": False}
        evidence = [{"path": str(release_path), "sha256": sha(release_path)}]
        if kind == "native_cup_station":
            from .native_cup_station import build_native_cup_station
            geometry["cupStation"] = build_native_cup_station(workspace, config)
            evidence.extend(geometry["cupStation"]["evidence"])
        elif kind == "native_cleaning_station":
            from .native_cleaning_station import build_native_cleaning_station
            geometry["cleaningStation"] = build_native_cleaning_station(workspace, config)
            evidence.extend(geometry["cleaningStation"]["evidence"])
    else:
        raise StationRuleError("UNSUPPORTED_RULE_EVALUATOR")
    if position_override is not None and calculated is None:
        raise StationRuleError("POSITION_OVERRIDE_REQUIRES_PARAMETERIZED_STATION")
    effective = parameters(position_override) if position_override is not None else calculated
    package = None
    reusable_authority = registered_direct_authority
    native_direct_authority = registered_direct_authority
    # A native role on its own native base is already positioned by the
    # released mechanical recipe.  The measured station parameters are a
    # postcheck expectation, not a request to mint a second datum-placement
    # recipe.  Cross-role and cross-base substitutions remain on the normal
    # parameterized release path below.
    if (kind == "cleaning_service_region"
            and rule["sourceModuleDefinitionId"] == config.get("nativeRoleModuleDefinitionId")):
        from .global_interface_contract_planner import resolve_preferred_released_interface_authority
        scope = read(workspace_file(workspace, binding["scopePath"]))
        source_id = scope_identity(scope, rule["sourceModuleDefinitionId"])["cadModuleDefinitionId"]
        base_id = scope_identity(scope, rule["targetBaseDefinitionId"], base=True)["cadModuleDefinitionId"]
        authority = resolve_preferred_released_interface_authority(
            workspace, source_id, selected_slot_definition_id=base_id)
        native = (authority.get("preferredPlan") or {}).get("nativePlan") or {}
        template = native.get("instantiatedTemplate") or {}
        if (authority.get("ready") is not True
                or authority.get("relationExecutionMode") != "direct_installation"
                or template.get("constraintEffect", {}).get("fullyLocatesAddedComponent") is not True):
            raise StationRuleError("NATIVE_STATION_DIRECT_AUTHORITY_UNAVAILABLE")
        release_path = workspace_file(workspace, authority["releaseManifestPath"])
        from .global_relation_catalog_release import load_relation_catalog_release
        load_relation_catalog_release(release_path, workspace_root=workspace)
        native_direct_authority = authority
        evidence.append({"path": str(release_path), "sha256": sha(release_path)})
    if effective is not None:
        if prepare_candidate and native_direct_authority is None:
            from .parameterized_datum_placement import compile_parameterized_datum_validation_package
            package = compile_parameterized_datum_validation_package(workspace,
                rule["sourceModuleDefinitionId"], rule["targetBaseDefinitionId"],
                initial_placement_variant=config.get("initialPlacementVariant", 3),
                position_parameters=effective,
                **({"distance_flip_dimensions": distance_flips} if distance_flips is not None else {}),
                **({"bounded_role_station_candidate": geometry} if kind == "bounded_role_station" else {}))
        status = "new_datum_candidate_requires_cad_validation_and_release"
        if native_direct_authority is not None:
            reusable_authority = native_direct_authority
            status = "released_native_station_recipe_requires_current_context_postcheck"
        elif binding["review"].get("releasedExecutionAuthority"):
            verified = read(workspace_file(workspace, rule["validation"]["planPath"]))
            if _same_geometry(effective, verified.get("effectivePositionParametersMeters")):
                reusable_authority = binding["review"]["releasedExecutionAuthority"]
                status = "released_station_recipe_requires_current_context_postcheck"
        if reusable_authority is None:
            reusable_authority, recipe_evidence = resolve_parameter_recipe(workspace, binding, effective)
            evidence.extend(recipe_evidence)
            if reusable_authority:
                status = "released_parameter_variant_requires_current_context_postcheck"
    else:
        status = "released_placement_requires_current_context_postcheck"
    evidence_by_path = {}
    for row in [*binding["review"]["evidence"], *evidence]:
        path = Path(row["path"])
        # CAD source evidence may live outside the repository. It is read-only
        # and supplied by the existing bounded geometry builders, not a writer.
        if not path.is_absolute():
            path = workspace / path
        path = path.resolve()
        if sha(path) != row["sha256"]:
            raise StationRuleError("STATION_GEOMETRY_EVIDENCE_CHANGED")
        evidence_by_path[str(path)] = {"path": str(path), "sha256": row["sha256"]}
    result = {
        "schemaVersion": "target-station-stage-plan/v1", "ruleId": rule["ruleId"],
        "sourceModuleDefinitionId": rule["sourceModuleDefinitionId"],
        "targetBaseDefinitionId": rule["targetBaseDefinitionId"], "role": rule["role"],
        "status": status, "ruleBinding": binding, "instanceBinding": instance_binding,
        "derivedPositionParametersMeters": calculated, "effectivePositionParametersMeters": effective,
        "explicitPositionOverride": position_override is not None,
        "coordinateSystem": "registered_target_datum_planes" if effective is not None else "released_mate_recipe",
        "geometry": geometry, "evidence": sorted(evidence_by_path.values(), key=lambda row: row["path"]),
        "validationPackage": package, "requiresFreshCadValidation": effective is not None and reusable_authority is None,
        "reusableExecutionAuthority": reusable_authority,
        "executionUsesReleasedNativeRecipe": native_direct_authority is not None,
        "requiresCurrentSavedStatePostcheck": True, "cadLaunchAllowed": False,
        "newCadExecuted": False, "targetStationValidated": False,
        "mechanicalCompatibilityPromoted": False, "sourceWorldPoseCopied": False,
        "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified",
    }
    # Exclude incidental timings from the semantic identity.
    result["planDigest"] = plan_digest(result)
    result["timing"] = {"startedAtUtc": started, "finishedAtUtc": now(), "durationSeconds": perf_counter()-clock}
    return result


def scanner_dependency_selector(root, plan, config, state, scope, catalog, dependency_states=None):
    """Bind the planned logical transport to a current CAD instance, never first-match."""
    bound = plan["instanceBinding"]["instances"]["Transport"]
    if bound["moduleDefinitionId"] != config["transportModuleDefinitionId"]:
        raise StationRuleError("SCANNER_PLANNED_TRANSPORT_DIFFERS_FROM_RULE")
    canonical = scope_identity(scope, bound["moduleDefinitionId"])["cadModuleDefinitionId"]
    definitions = [r for r in catalog["moduleDefinitions"] if r["moduleDefinitionId"] == canonical]
    if len(definitions) != 1:
        raise StationRuleError("SCANNER_TRANSPORT_CATALOG_IDENTITY_MISSING")
    paths = {str(Path(r["path"]).resolve()).casefold() for r in definitions[0]["cadSources"]}
    matches = [r for r in state["observed"]["components"]
               if str(Path(r["sourcePath"]).resolve()).casefold() in paths]
    proof = (dependency_states or {}).get(bound["instanceId"])
    if proof is not None:
        path = Path(root) / proof["savedStatePath"]
        if sha(path) != proof["savedStateSha256"]:
            raise StationRuleError("SCANNER_DEPENDENCY_STATE_CHANGED")
        previous = read(path)
        if previous.get("success") is not True or previous.get("observed", {}).get("readOnly") is not True:
            raise StationRuleError("SCANNER_DEPENDENCY_STATE_NOT_VERIFIED")
        if sha(Path(root) / previous["assemblyPath"]) != previous["assemblySha256"]:
            raise StationRuleError("SCANNER_DEPENDENCY_ASSEMBLY_CHANGED")
        prior = [r for r in previous["observed"]["components"] if r.get("name") == proof["componentName"]]
        if len(prior) != 1 or str(Path(prior[0]["sourcePath"]).resolve()).casefold() not in paths:
            raise StationRuleError("SCANNER_DEPENDENCY_INSTANCE_IDENTITY_MISMATCH")
        matches = [r for r in matches if r.get("name") == prior[0]["name"]
                   and r.get("configuration") == prior[0].get("configuration")]
    if len(matches) != 1:
        raise StationRuleError("SCANNER_CURRENT_TRANSPORT_INSTANCE_AMBIGUOUS_OR_MISSING")
    return {"transport": matches[0]["name"]}


def verify_station_stage(workspace, plan, *, cad_result_path, saved_state_path, dependency_states=None):
    """Replay the same rule against saved REAL output; never connect to CAD.

The existing closure verifies nonprototype insertion, live mates, reopen and
context preservation. Rule geometry is additional evidence, not a substitute.
"""
    from .functional_chain_closure import build_functional_chain_closure
    started, clock = now(), perf_counter()
    root = Path(workspace)
    if plan_digest(plan) != plan.get("planDigest"):
        raise StationRuleError("STATION_PLAN_CHANGED")
    revalidate_rule_binding(root, plan["ruleBinding"])
    for row in plan["evidence"]:
        if sha(row["path"]) != row["sha256"]:
            raise StationRuleError("STATION_GEOMETRY_EVIDENCE_CHANGED")
    closure = build_functional_chain_closure(root, stages=[{
        "stageId": plan["ruleId"], "cadResultPath": str(cad_result_path), "afterStatePath": str(saved_state_path)
    }], required_roles=[])
    if closure.get("cadPassed") is not True:
        raise StationRuleError("STATION_CURRENT_CAD_CLOSURE_FAILED:"+str(closure["stages"]))
    cad = read(root / cad_result_path)
    raw_token = (cad.get("toolResult") or {}).get("TargetModuleToken")
    if not isinstance(raw_token, str) or not raw_token.endswith(plan["sourceModuleDefinitionId"].split("::")[1]):
        raise StationRuleError("CAD_INSERTED_TARGET_DIFFERS_FROM_STATION_PLAN")
    # Suffix is only an early rejection; exact catalog/file identity below is
    # mandatory and never replaced by this coarse filter.
    graph = read(cad.get("executionEffectiveGraphPath") or cad["effectiveGraphPath"])
    state = read(root / saved_state_path)
    if sum(r.get("isFixed") is True for r in state["observed"]["components"]) != 1:
        raise StationRuleError("STATION_REQUIRES_EXACTLY_ONE_FIXED_BASE")
    scope = read(plan["ruleBinding"]["scopePath"])
    catalog = read(workspace_file(root, "demo/global_assembly_catalog/v1/global_module_catalog.json"))
    selected = {}
    for label, definition, is_base in (("source", plan["sourceModuleDefinitionId"], False),
                                       ("base", plan["targetBaseDefinitionId"], True)):
        canonical = scope_identity(scope, definition, base=is_base)["cadModuleDefinitionId"]
        rows = [r for r in catalog["moduleDefinitions"] if r["moduleDefinitionId"] == canonical]
        if len(rows) != 1:
            raise StationRuleError("STATION_CURRENT_MODULE_IDENTITY_MISSING")
        paths = {str(Path(r["path"]).resolve()).casefold() for r in rows[0]["cadSources"]}
        found = [r for r in state["observed"]["components"] if str(Path(r["sourcePath"]).resolve()).casefold() in paths]
        if len(found) != 1 or found[0].get("isFixed") is not is_base:
            raise StationRuleError("STATION_CURRENT_MODULE_INSTANCE_AMBIGUOUS_OR_FIXED")
        selected[label] = found[0]
    if not inserted_token_matches((cad.get("toolResult") or {}).get("TargetModuleToken"),
                                  plan["sourceModuleDefinitionId"], selected["source"]["sourcePath"]):
        raise StationRuleError("CAD_INSERTED_TARGET_DIFFERS_FROM_STATION_PLAN")
    rule = plan["ruleBinding"]["rule"]
    config = read(workspace_file(root, rule["evaluator"]["inputPath"]))
    kind = rule["evaluator"]["kind"]
    package = plan.get("validationPackage")
    if (package is None and plan.get("effectivePositionParametersMeters") is not None
            and plan.get("executionUsesReleasedNativeRecipe") is not True):
        from .parameterized_datum_placement import compile_parameterized_datum_validation_package
        package = compile_parameterized_datum_validation_package(root,
            plan["sourceModuleDefinitionId"], plan["targetBaseDefinitionId"],
            initial_placement_variant=config.get("initialPlacementVariant", 3),
            position_parameters=plan["effectivePositionParametersMeters"],
            **({"distance_flip_dimensions": cup_distance_flips(plan["geometry"])} if kind == "cup_projection" else {}))
    mate_mapping = None
    if package:
        # Binding to exact executed geometric endpoints and recipe parameters
        # prevents a different graph at a similar pose masquerading as this plan.
        mate_mapping = bind_executed_candidate_parameters(package["effectiveGraph"], graph)
    if kind == "cleaning_service_region":
        from .cleaning_service_region import build_cleaning_service_region_audit
        geometry = build_cleaning_service_region_audit(root, config,
            cad_result_path=root / cad_result_path, saved_state_path=root / saved_state_path)
        if (geometry.get("capabilityCoverage") or {}).get("passed") is not True:
            raise StationRuleError("TARGET_SERVICE_CAPABILITIES_INCOMPLETE")
        proxy = geometry.get("serviceRegionDemoPassed") is True
        if plan.get("executionUsesReleasedNativeRecipe") is True:
            authority = plan.get("reusableExecutionAuthority") or {}
            released = verify_released_station_graph(
                root, authority["releaseManifestPath"],
                plan["sourceModuleDefinitionId"].split("::")[1], graph,
                verified_source_path=selected["source"]["sourcePath"])
            geometry["releasedNativeRecipe"] = released
            proxy = proxy and released["proxyGeometryPassed"] is True
    elif kind == "bounded_role_station":
        if package is None or mate_mapping is None:
            raise StationRuleError("BOUNDED_ROLE_STATION_EXECUTION_PACKAGE_MISSING")
        from .bounded_role_station import build_bounded_role_station_candidate

        geometry = build_bounded_role_station_candidate(root, config)
        if package.get("boundedRoleStationCandidate", {}).get("candidateDigest") != geometry.get(
            "candidateDigest"
        ):
            raise StationRuleError("BOUNDED_ROLE_STATION_CANDIDATE_CHANGED")
        geometry = {
            **geometry,
            "executedMateMapping": mate_mapping,
            "currentSavedOutputVerified": True,
        }
        proxy = bool(
            geometry["nativeRoleStationContainment"]["passed"]
            and geometry["finiteSupportGate"]["passed"]
        )
    elif kind == "cup_projection":
        from .cup_function_point import verify_saved_cup_projection
        names = None
        if package:
            steps = package["instantiatedTemplate"]["mateSteps"]
            names = {}
            for parameter in ("longitudinal", "lateral"):
                rows = [s for s in steps if s.get("endpointRoleA") == parameter+"_datum" and s.get("endpointRoleB") == parameter+"_datum"]
                if len(rows) != 1:
                    raise StationRuleError("CUP_CANDIDATE_PARAMETER_ROLE_AMBIGUOUS")
                names[parameter] = mate_mapping[rows[0]["mateName"]]
        acceptance = config["acceptance"]
        geometry = verify_saved_cup_projection(geometry_report=plan["geometry"],
            cad_result_path=root / cad_result_path, saved_state_path=root / saved_state_path,
            parameter_mate_names=names, projection_tolerance_meters=acceptance["mouthProjectionToleranceMeters"],
            angular_tolerance_degrees=acceptance["openingAngularToleranceDegrees"])
        proxy = geometry["targetCupProjectionPassed"] is True
        if acceptance.get("equalMouthHeightRequired") is True:
            proxy = proxy and geometry["threeDimensionalCupMouthAlignmentPassed"] is True
    elif kind == "transport_position_parameters":
        if package is None or mate_mapping is None:
            raise StationRuleError("TRANSPORT_POSITION_EXECUTION_PACKAGE_MISSING")
        postcheck_status = transport_position_postcheck_status(plan["geometry"])
        geometry = {
            **plan["geometry"],
            "executedMateMapping": mate_mapping,
            "targetStationParameterMatch": True,
            "currentSavedOutputVerified": True,
            "publicationBlockedReasonCode": postcheck_status[
                "publicationBlockedReasonCode"
            ],
        }
        proxy = postcheck_status["proxyGeometryPassed"]
    elif kind == "scanner_target":
        from .scanner_target_rule import build_current_scanner_target
        geometry = build_current_scanner_target(state_path=saved_state_path, rule=config,
            authorize_prototype_estimate=plan["ruleBinding"]["prototypeEstimateAuthorized"], repository_root=root,
            instance_selectors={"scanner": selected["source"]["name"], "targetBase": selected["base"]["name"],
                **scanner_dependency_selector(root, plan, config, state, scope, catalog, dependency_states)})
        proxy = geometry["evaluation"]["processProxyValidationPassed"] is True
    elif kind == "scanner_point_pair":
        from .scanner_point_pair_binding import (
            evaluate_scanner_point_pair_in_saved_context,
        )

        transport_selector = scanner_dependency_selector(
            root, plan, config, state, scope, catalog, dependency_states
        )
        measurement = read(
            workspace_file(root, config["inputs"]["measurementPath"])
        )
        assembly_path = Path(state.get("assemblyPath") or "").resolve()
        if not assembly_path.is_file():
            raise StationRuleError("SCANNER_POINT_PAIR_ASSEMBLY_MISSING")
        geometry = evaluate_scanner_point_pair_in_saved_context(
            rule=config,
            measurement=measurement,
            saved_state=state,
            state_path=str((root / saved_state_path).resolve()),
            state_sha256=sha(root / saved_state_path),
            assembly_sha256=sha(assembly_path),
            instance_selectors={
                "scanner": selected["source"]["name"],
                "targetBase": selected["base"]["name"],
                **transport_selector,
            },
        )
        proxy = geometry["processProxyValidationPassed"] is True
    elif kind in {"released_mate_parameters", "native_cup_station", "native_cleaning_station"}:
        geometry = verify_released_station_graph(root, config["inputs"]["referenceReleasePath"],
            plan["sourceModuleDefinitionId"].split("::")[1], graph,
            verified_source_path=selected["source"]["sourcePath"])
        proxy = geometry["proxyGeometryPassed"]
        if kind == "native_cup_station":
            from .native_cup_station import build_native_cup_station
            geometry["cupStation"] = build_native_cup_station(root, config, state)
            proxy = proxy and geometry["cupStation"]["proxyGeometryPassed"] is True
        elif kind == "native_cleaning_station":
            from .native_cleaning_station import build_native_cleaning_station
            geometry["cleaningStation"] = build_native_cleaning_station(root, config, state)
            proxy = proxy and geometry["cleaningStation"]["proxyGeometryPassed"] is True
    else:
        raise StationRuleError("UNSUPPORTED_RULE_EVALUATOR")
    return {"schemaVersion": "target-station-current-postcheck/v1", "ruleId": plan["ruleId"],
        "planDigest": plan["planDigest"], "cadPassed": True, "proxyGeometryPassed": proxy,
        "functionalPassed": None, "targetStationValidated": proxy, "cadClosure": closure,
        "geometry": geometry, "sourceInstance": selected["source"], "baseInstance": selected["base"],
        "newCadExecutedByThisVerifier": False, "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified",
        "timing": {"startedAtUtc": started, "finishedAtUtc": now(), "durationSeconds": perf_counter()-clock}}


def plan_station_chain(workspace, request, *, prepare_candidates=False):
    """Plan the SAME ordered request used by compile/run/resume; launch no CAD."""
    started, clock = now(), perf_counter()
    loaded = load_station_registry(workspace, request.get("stationRegistryPath", DEFAULT_REGISTRY))
    base_id = confirmed_identity(request.get("baseSelection"))
    base = scope_identity(loaded["scope"], base_id, base=True)
    base_instance = request.get("baseInstanceId", "base")
    steps = request.get("steps") or []
    ids = [step.get("stageId") for step in steps]
    instance_ids = [step.get("instanceId", step.get("stageId")) for step in steps]
    if (not steps or any(not isinstance(v, str) or not v for v in [base_instance, *ids, *instance_ids])
            or len(set(ids)) != len(ids) or len(set([base_instance, *instance_ids])) != len(instance_ids)+1):
        raise StationRuleError("STAGE_OR_INSTANCE_IDS_MISSING_OR_DUPLICATE")
    context = [{"instanceId": base_instance, "moduleDefinitionId": base_id, "role": base["role"]}]
    results = []
    for step, instance_id in zip(steps, instance_ids, strict=True):
        row = {"stageId": step["stageId"], "instanceId": instance_id, "planned": False,
               "cadLaunchAllowed": False, "blockingReasonCodes": []}
        try:
            source = confirmed_identity(step.get("moduleSelection"))
            definition = scope_identity(loaded["scope"], source)
            target = confirmed_identity(step.get("slotSelection") or request["baseSelection"])
            if target != base_id:
                raise StationRuleError("TARGET_BASE_NOT_IN_CURRENT_CHAIN")
            instance = {"instanceId": instance_id, "moduleDefinitionId": source, "role": definition["role"]}
            row.update(sourceModuleDefinitionId=source, targetBaseDefinitionId=target, role=definition["role"])
            binding = select_station_rule(loaded, source=source, target_base=target,
                rule_id=step.get("stationRuleId"),
                allow_prototype_estimate=step.get("allowPrototypeEstimate", request.get("allowPrototypeEstimate")) is True)
            bound = bind_rule_instances(binding, [*context, instance], source_instance_id=instance_id,
                base_instance_id=base_instance, dependency_selections=step.get("dependencySelections"))
            if (rule_requires_datum_fallback_authorization(workspace, binding)
                    and step.get("allowDatumFallback") is not True):
                raise StationRuleError("DATUM_FALLBACK_AUTHORIZATION_REQUIRED")
            plan = plan_station_stage(workspace, binding, bound,
                position_override=step.get("positionParametersMeters"), prepare_candidate=prepare_candidates)
            row.update(planned=True, plan=plan)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row["blockingReasonCodes"].append(str(exc))
        # Keep the declared order even when a prior station is missing; these
        # are proposed identities, never a claim they already exist in CAD.
        if row.get("sourceModuleDefinitionId"):
            context.append({"instanceId": instance_id, "moduleDefinitionId": row["sourceModuleDefinitionId"], "role": row["role"]})
        results.append(row)
    return {"schemaVersion": "target-station-chain-plan/v1", "chainId": request.get("chainId"),
            "registryPath": loaded["registryPath"], "registrySha256": loaded["registrySha256"],
            "scopePath": loaded["scopePath"], "scopeSha256": loaded["scopeSha256"],
            "stages": results, "planningComplete": all(r["planned"] for r in results),
            "plannedStageCount": sum(r["planned"] for r in results), "requestedStageCount": len(results),
            "contextKind": "proposed_ordered_instances_not_observed_cad",
            "cadLaunchAllowed": False, "newCadExecuted": False, "targetStationValidated": False,
            "startedAtUtc": started, "finishedAtUtc": now(), "durationSeconds": perf_counter()-clock}

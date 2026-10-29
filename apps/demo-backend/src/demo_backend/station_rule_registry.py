"""Small data registry for target-station rules, not another CAD executor.

Configured data, measured Demo geometry, and executable release authority are
independent facts. Selection never invents a station or picks the first match.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = "data/assembly_stations/station-rules-v1.json"
DEFAULT_SCOPE = "data/assembly_stations/scope-v1.json"
KINDS = {"cleaning_service_region", "bounded_role_station", "cup_projection", "scanner_target", "scanner_point_pair", "transport_position_parameters", "released_mate_parameters", "native_cup_station", "native_cleaning_station"}
SCHEMAS = {"native_cup_station": "native-cup-station-rule/v1", "native_cleaning_station": "native-cleaning-station-rule/v1",
           "cleaning_service_region": "cleaning-service-region-rule/v1",
           "bounded_role_station": "bounded-role-station-config/v1",
           "cup_projection": "cup-projection-rule/v1", "scanner_target": "scanner-target-rule/v1",
           "scanner_point_pair": "scanner-local-point-pair-rule/v1",
           "transport_position_parameters": "transport-position-parameters-rule/v1",
           "released_mate_parameters": "released-station-parameters-rule/v1"}


class StationRuleError(ValueError):
    pass


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def scope_identity(scope, identity, *, base=False):
    rows = scope["bases" if base else "movingModules"]
    matches = [r for r in rows if identity in {r["moduleDefinitionId"], r["cadModuleDefinitionId"]}]
    if len(matches) != 1:
        raise StationRuleError(f"MODULE_OUTSIDE_OR_AMBIGUOUS_SCOPE:{identity}")
    return matches[0]


def workspace_file(workspace, value):
    if not isinstance(value, (str, Path)) or not str(value):
        raise StationRuleError("MISSING_RULE_EVIDENCE_PATH")
    root = Path(workspace).resolve()
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StationRuleError("RULE_INPUT_OUTSIDE_WORKSPACE") from exc
    if not path.is_file():
        raise StationRuleError(f"RULE_INPUT_MISSING:{path}")
    return path


def _evidence(workspace, rule, config_path, config):
    paths = {str(config_path): sha(config_path)}
    # Each evaluator's input JSON carries the relevant underlying source files.
    # Recursive CAD dependencies stay the responsibility of its existing loader.
    for key, value in (config.get("inputs") or {}).items():
        if isinstance(value, str):
            path = workspace_file(workspace, value)
            actual = sha(path)
            expected = (config.get("inputSha256") or {}).get(key)
            if expected is not None and expected != actual:
                raise StationRuleError(f"RULE_CONFIG_INPUT_CHANGED:{key}")
            paths[str(path)] = actual
    for row in rule.get("evidence") or []:
        path = workspace_file(workspace, row["path"])
        actual = sha(path)
        if actual != row.get("sha256"):
            raise StationRuleError(f"RULE_EVIDENCE_CHANGED:{path}")
        paths[str(path)] = actual
    for key in ("planPath", "cadResultPath", "savedStatePath", "releaseManifestPath"):
        value = (rule.get("validation") or {}).get(key)
        if value:
            path = workspace_file(workspace, value)
            paths[str(path)] = sha(path)
    return [{"path": path, "sha256": value} for path, value in sorted(paths.items())]


def _verified_experimental_closure(workspace, rule, scope):
    """Recompute the exact planned rule, not just a historical role's success."""
    validation = rule.get("validation") or {}
    # Historical geometric success is not evidence for a newly edited rule.
    # A rule-aware postcheck must bind the same config before it can be reused.
    config_path = workspace_file(workspace, rule["evaluator"]["inputPath"])
    if validation.get("configurationSha256") != sha(config_path):
        raise StationRuleError("STATION_VALIDATION_RULE_NOT_BOUND")
    if validation.get("kind") != "station_plan_current_postcheck":
        return False
    plan = read(workspace_file(workspace, validation.get("planPath")))
    planned_rule = plan["ruleBinding"]["rule"]
    planned_scope = read(workspace_file(workspace, plan["ruleBinding"]["scopePath"]))
    for identity, base in ((rule["sourceModuleDefinitionId"], False), (rule["targetBaseDefinitionId"], True)):
        if scope_identity(scope, identity, base=base) != scope_identity(planned_scope, identity, base=base):
            raise StationRuleError("STATION_VALIDATION_SCOPE_IDENTITY_CHANGED")
    if planned_rule.get("validation", {}).get("status") != "candidate":
        raise StationRuleError("STATION_VALIDATION_RECURSIVE_OR_NONCANDIDATE_PLAN")
    if {k: v for k, v in rule.items() if k != "validation"} != {
            k: v for k, v in planned_rule.items() if k != "validation"}:
        raise StationRuleError("STATION_VALIDATION_RULE_CHANGED")
    from .station_rule_planner import verify_station_stage
    report = verify_station_stage(workspace, plan,
        cad_result_path=workspace_file(workspace, validation.get("cadResultPath")),
        saved_state_path=workspace_file(workspace, validation.get("savedStatePath")))
    if report.get("cadPassed") is not True or report.get("proxyGeometryPassed") is not True:
        raise StationRuleError("STATION_RULE_CURRENT_POSTCHECK_NOT_PASSED")
    return True


def validate_rule(workspace, rule, scope):
    result = {"ruleId": rule.get("ruleId"), "configuredStationRule": False,
              "validatedStationRule": False, "experimentalEvidenceOnly": False,
              "blockingReasonCodes": [], "evidence": [], "ruleDigest": digest(rule),
              "cadLaunchAllowed": False, "mechanicalCompatibilityPromoted": False}
    try:
        if not isinstance(rule.get("ruleId"), str) or not rule["ruleId"]:
            raise StationRuleError("RULE_ID_MISSING")
        source = scope_identity(scope, rule.get("sourceModuleDefinitionId"))
        scope_identity(scope, rule.get("targetBaseDefinitionId"), base=True)
        if source["role"] != rule.get("role"):
            raise StationRuleError("RULE_ROLE_DIFFERS_FROM_SCOPE")
        evaluator = rule.get("evaluator") or {}
        if evaluator.get("kind") not in KINDS:
            raise StationRuleError("UNSUPPORTED_RULE_EVALUATOR")
        config_path = workspace_file(workspace, evaluator.get("inputPath"))
        config = read(config_path)
        if config.get("schemaVersion") != SCHEMAS[evaluator["kind"]] or config.get("ruleId") != rule["ruleId"]:
            raise StationRuleError("RULE_CONFIG_SCHEMA_OR_ID_MISMATCH")
        for key in ("sourceModuleDefinitionId", "targetBaseDefinitionId"):
            if config.get(key) != rule.get(key):
                raise StationRuleError(f"RULE_CONFIG_IDENTITY_MISMATCH:{key}")
        if (rule.get("placement") or {}).get("strategy") not in {"target_role_region", "target_function_points", "released_recipe"}:
            raise StationRuleError("UNSUPPORTED_PLACEMENT_STRATEGY")
        if evaluator["kind"] in {"scanner_target", "scanner_point_pair"} and rule.get("dependencies") != [
            {"role": "Transport", "moduleDefinitionId": config.get("transportModuleDefinitionId")}
        ]:
            raise StationRuleError("SCANNER_TRANSPORT_DEPENDENCY_MISMATCH")
        validation = rule.get("validation") or {}
        if validation.get("status") not in {"candidate", "experimental_cad_verified", "released_demo"}:
            raise StationRuleError("UNKNOWN_RULE_VALIDATION_STATUS")
        result["evidence"] = _evidence(workspace, rule, config_path, config)
        result["configuredStationRule"] = True
        if validation["status"] != "candidate":
            result["validatedStationRule"] = _verified_experimental_closure(workspace, rule, scope)
            result["experimentalEvidenceOnly"] = result["validatedStationRule"]
            if not result["validatedStationRule"]:
                result["blockingReasonCodes"].append("VALIDATED_LABEL_WITHOUT_SUPPORTED_RUNTIME_EVIDENCE")
            elif validation["status"] == "released_demo":
                from .global_relation_catalog_release import load_relation_catalog_release
                release_path = workspace_file(workspace, validation.get("releaseManifestPath"))
                _, release = load_relation_catalog_release(release_path, workspace_root=Path(workspace))
                metadata = release.get("releaseMetadata") or {}
                pair = metadata.get("parameterizedDatumPairBinding") or {}
                if (metadata.get("relationExecutionMode") != "datum_placement_demo"
                        or pair.get("moduleDefinitionId") != rule["sourceModuleDefinitionId"]
                        or pair.get("slotDefinitionId") != rule["targetBaseDefinitionId"]
                        or pair.get("cadResultSha256") != sha(workspace_file(workspace, validation["cadResultPath"]))):
                    raise StationRuleError("STATION_RELEASE_DOES_NOT_BIND_VALIDATED_PAIR")
                result["experimentalEvidenceOnly"] = False
                result["releasedExecutionAuthority"] = {"releaseManifestPath": str(release_path),
                    "releaseManifestSha256": sha(release_path), "relationExecutionMode": "datum_placement_demo"}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result["validatedStationRule"] = False
        result["experimentalEvidenceOnly"] = False
        result.pop("releasedExecutionAuthority", None)
        result["blockingReasonCodes"].append(str(exc))
    return result


def stage_candidate_rule(workspace, base_registry, candidate_registry, *, rule_id):
    """Add one configured candidate to a new in-memory registry.

    This is deliberately weaker than CAD evidence registration: the candidate
    remains ``validation.status=candidate``, cannot launch CAD by itself and
    cannot replace an existing pair silently.  The caller owns writing the
    returned registry to a new immutable path.
    """
    if base_registry.get("schemaVersion") != "target-station-rule-registry/v1":
        raise StationRuleError("UNSUPPORTED_BASE_STATION_REGISTRY_SCHEMA")
    if candidate_registry.get("schemaVersion") != "target-station-rule-registry/v1":
        raise StationRuleError("UNSUPPORTED_CANDIDATE_STATION_REGISTRY_SCHEMA")
    if base_registry.get("scopePath", DEFAULT_SCOPE) != candidate_registry.get(
        "scopePath", DEFAULT_SCOPE
    ):
        raise StationRuleError("CANDIDATE_SCOPE_DIFFERS_FROM_BASE_REGISTRY")
    matches = [
        row for row in candidate_registry.get("rules") or []
        if row.get("ruleId") == rule_id
    ]
    if len(matches) != 1:
        raise StationRuleError("CANDIDATE_RULE_NOT_UNIQUE")
    candidate = deepcopy(matches[0])
    if (candidate.get("validation") or {}).get("status") != "candidate":
        raise StationRuleError("ONLY_UNVALIDATED_CANDIDATE_MAY_BE_STAGED")
    scope = read(workspace_file(workspace, base_registry.get("scopePath", DEFAULT_SCOPE)))
    review = validate_rule(workspace, candidate, scope)
    if not review["configuredStationRule"] or review["blockingReasonCodes"]:
        raise StationRuleError("CANDIDATE_RULE_INVALID:" + str(review["blockingReasonCodes"]))
    if review["validatedStationRule"] or review["cadLaunchAllowed"]:
        raise StationRuleError("CANDIDATE_CANNOT_CARRY_CAD_AUTHORITY")
    existing_by_id = [
        row for row in base_registry.get("rules") or []
        if row.get("ruleId") == rule_id
    ]
    if existing_by_id:
        if len(existing_by_id) != 1 or existing_by_id[0] != candidate:
            raise StationRuleError("CANDIDATE_RULE_ID_CONFLICT")
        return deepcopy(base_registry), {
            "status": "candidate_already_present",
            "ruleId": rule_id,
            "review": review,
            "cadLaunchAllowed": False,
        }
    pair_conflicts = [
        row for row in base_registry.get("rules") or []
        if row.get("sourceModuleDefinitionId") == candidate["sourceModuleDefinitionId"]
        and row.get("targetBaseDefinitionId") == candidate["targetBaseDefinitionId"]
    ]
    if pair_conflicts:
        raise StationRuleError("CANDIDATE_PAIR_ALREADY_HAS_DIFFERENT_RULE")
    merged = deepcopy(base_registry)
    merged.setdefault("rules", []).append(candidate)
    return merged, {
        "status": "candidate_staged_for_cad_validation",
        "ruleId": rule_id,
        "review": review,
        "cadLaunchAllowed": False,
    }


def load_station_registry(workspace, path=DEFAULT_REGISTRY):
    registry_path = workspace_file(workspace, path)
    registry = read(registry_path)
    if registry.get("schemaVersion") != "target-station-rule-registry/v1":
        raise StationRuleError("UNSUPPORTED_STATION_REGISTRY_SCHEMA")
    scope_path = workspace_file(workspace, registry.get("scopePath", DEFAULT_SCOPE))
    scope = read(scope_path)
    rules = registry.get("rules") or []
    ids = [r.get("ruleId") for r in rules]
    if not ids or not all(ids) or len(set(ids)) != len(ids):
        raise StationRuleError("RULE_IDS_EMPTY_OR_DUPLICATE")
    reviews = [validate_rule(workspace, rule, scope) for rule in rules]
    return {"registryPath": str(registry_path), "registrySha256": sha(registry_path),
            "scopePath": str(scope_path), "scopeSha256": sha(scope_path),
            "rules": rules, "reviews": reviews, "scope": scope}


def select_station_rule(loaded, *, source, target_base, rule_id=None, allow_prototype_estimate=False):
    source = scope_identity(loaded["scope"], source)["moduleDefinitionId"]
    target_base = scope_identity(loaded["scope"], target_base, base=True)["moduleDefinitionId"]
    matches = [(rule, review) for rule, review in zip(loaded["rules"], loaded["reviews"], strict=True)
               if rule["sourceModuleDefinitionId"] == source and rule["targetBaseDefinitionId"] == target_base
               and (rule_id is None or rule["ruleId"] == rule_id)]
    if len(matches) != 1:
        raise StationRuleError("TARGET_STATION_RULE_MISSING" if not matches else "TARGET_STATION_RULE_AMBIGUOUS")
    rule, review = matches[0]
    if not review["configuredStationRule"] or review["blockingReasonCodes"]:
        raise StationRuleError("TARGET_STATION_RULE_INVALID:"+str(review["blockingReasonCodes"]))
    if rule.get("requiresPrototypeEstimateAuthorization", False) and not allow_prototype_estimate:
        raise StationRuleError("PROTOTYPE_ESTIMATE_AUTHORIZATION_REQUIRED")
    return {"rule": rule, "review": review, "registryPath": loaded["registryPath"],
            "registrySha256": loaded["registrySha256"], "scopePath": loaded["scopePath"],
            "scopeSha256": loaded["scopeSha256"], "prototypeEstimateAuthorized": allow_prototype_estimate,
            "cadLaunchAllowed": False, "releaseAuthorityStillRequired": True}


def bind_rule_instances(binding, instances, *, source_instance_id, base_instance_id, dependency_selections=None):
    """Use exact instance ids; role-only dependencies require a unique match."""
    rule = binding["rule"]
    identifiers = [r.get("instanceId") for r in instances]
    if not all(identifiers) or len(set(identifiers)) != len(identifiers):
        raise StationRuleError("INSTANCE_IDS_MISSING_OR_DUPLICATE")
    by_id = {r["instanceId"]: r for r in instances}
    selected = {}
    for label, instance_id, definition in (("source", source_instance_id, rule["sourceModuleDefinitionId"]),
                                            ("base", base_instance_id, rule["targetBaseDefinitionId"])):
        row = by_id.get(instance_id)
        if not row or row.get("moduleDefinitionId") != definition:
            raise StationRuleError(f"INSTANCE_SELECTION_IDENTITY_MISMATCH:{label}")
        selected[label] = row
    for dependency in rule.get("dependencies") or []:
        role = dependency["role"]
        matches = [r for r in instances if r.get("role") == role and
                   (not dependency.get("moduleDefinitionId") or r.get("moduleDefinitionId") == dependency["moduleDefinitionId"])]
        explicit = (dependency_selections or {}).get(role)
        if explicit:
            matches = [r for r in matches if r["instanceId"] == explicit]
        if len(matches) != 1:
            raise StationRuleError(f"DEPENDENCY_{'MISSING' if not matches else 'AMBIGUOUS'}:{role}")
        selected[role] = matches[0]
    core = {"ruleId": rule["ruleId"], "ruleDigest": binding["review"]["ruleDigest"],
            "registrySha256": binding["registrySha256"], "instances": selected,
            "cadLaunchAllowed": False}
    return {**core, "contextDigest": digest(core)}


def revalidate_rule_binding(workspace, binding):
    for path_key, hash_key in (("registryPath", "registrySha256"), ("scopePath", "scopeSha256")):
        if sha(workspace_file(workspace, binding[path_key])) != binding[hash_key]:
            raise StationRuleError("RULE_BINDING_CATALOG_CHANGED")
    if digest(binding["rule"]) != binding["review"]["ruleDigest"]:
        raise StationRuleError("RULE_BINDING_CHANGED")
    registered = read(workspace_file(workspace, binding["registryPath"]))
    rows = [r for r in registered.get("rules") or [] if r.get("ruleId") == binding["rule"].get("ruleId")]
    if len(rows) != 1 or rows[0] != binding["rule"]:
        raise StationRuleError("RULE_BINDING_DIFFERS_FROM_REGISTERED_RULE")
    for row in binding["review"]["evidence"]:
        if sha(workspace_file(workspace, row["path"])) != row["sha256"]:
            raise StationRuleError("RULE_BINDING_SOURCE_EVIDENCE_CHANGED")
    scope = read(workspace_file(workspace, binding["scopePath"]))
    review = validate_rule(workspace, binding["rule"], scope)
    if not review["configuredStationRule"] or review["blockingReasonCodes"]:
        raise StationRuleError("RULE_BINDING_INVALIDATED:"+str(review["blockingReasonCodes"]))
    if review != binding["review"]:
        raise StationRuleError("RULE_BINDING_REVIEW_CHANGED")
    return review

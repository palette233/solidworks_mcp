"""Thin batch preparation over existing station rules and interface authorities.

No CAD, no release promotion, no source-world-pose fallback. Generated rules are
candidates; missing functional geometry remains a named data requirement.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from datetime import datetime, timezone

from .station_rule_registry import read, sha, validate_rule, workspace_file
from .global_interface_contract_planner import resolve_preferred_released_interface_authority

PRIORITY = {"WasteCup": 0, "Calibration": 1, "CleaningWeighing": 2, "Transport": 3, "Scanner": 4}
REQUIRED = {
    "WasteCup": ["source_cup_mouth_local_point_and_direction", "target_native_cup_station", "target_datum_frame"],
    "Calibration": ["target_calibration_station", "source_installation_datums", "exact_pair_recipe"],
    "CleaningWeighing": ["source_service_subtrees", "target_native_service_region", "occupancy_frame_binding", "exact_pair_datum_graph"],
    "Transport": ["target_transport_station", "source_installation_datums", "track_and_work_area_description"],
    "Scanner": ["source_optical_frame", "actual_transport_instance", "transport_barcode_target_region", "working_distance_evidence"],
}
DEFAULT_CAPABILITY_INDEX = (
    "data/assembly_stations/cleaning-service-capability-coverage-index-v3.json"
)
DEFAULT_FUNCTIONAL_SCREENING_INDEX = (
    "data/assembly_stations/station-functional-screening-index-v1.json"
)
DEFAULT_CANDIDATE_DECISION_INDEX = (
    "data/assembly_stations/station-candidate-decision-index-v1.json"
)
DEFAULT_TRANSPORT_WORK_AREA_REVIEW_INDEX = (
    "data/assembly_stations/transport-work-area-review-index-v1.json"
)


def _json_digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _released_pair_cad_history(
    root, *, authority, source_module_definition_id, target_base_definition_id
):
    """Recover authenticated pair-only CAD evidence from a released manifest.

    The mechanical contract catalog intentionally stores only the immutable
    release id/digest.  Older releases nevertheless bind their successful CAD
    result in ``validationEvidence``.  Gap preparation must not lose that
    evidence merely because it was not duplicated into the contract catalog.

    Only a pair-only, non-prototype, saved/reopened and fully constrained result
    is eligible.  Multi-module context results are left for the current-context
    chain path instead of being silently treated as a pair output.
    """

    release_value = (authority or {}).get("releaseManifestPath")
    if not release_value:
        return {}
    manifest_path = workspace_file(root, release_value)
    manifest = read(manifest_path)
    pair = (authority or {}).get("pairReleaseEvidence") or {}
    if pair.get("releaseId") and manifest.get("releaseId") != pair["releaseId"]:
        raise ValueError("released pair evidence id differs from manifest")
    if pair.get("releaseDigest") and manifest.get("releaseDigest") != pair["releaseDigest"]:
        raise ValueError("released pair evidence digest differs from manifest")

    source_token = source_module_definition_id.split("::", 1)[1]
    base_token = target_base_definition_id.split("::", 1)[1]
    eligible = []
    for binding in manifest.get("validationEvidence") or []:
        if (
            binding.get("passed") is not True
            or binding.get("drivingInitialPoseIndependent") is not True
            or not binding.get("path")
        ):
            continue
        result_path = workspace_file(root, binding["path"])
        if binding.get("fileSha256") and sha(result_path) != binding["fileSha256"]:
            raise ValueError("released CAD validation evidence changed")
        result = read(result_path)
        tool = result.get("toolResult") or {}
        required_flags = (
            "Success",
            "IndependentComponentInserted",
            "Reopened",
            "ReopenedMateParametersMatch",
            "MateSolveClean",
            "TargetFullyConstrained",
        )
        if result.get("success") is not True or any(
            tool.get(key) is not True for key in required_flags
        ):
            continue
        if tool.get("TargetCaseAnchored") not in (False, 0, None):
            continue
        if int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) != 0:
            continue
        if tool.get("TargetModuleToken") != source_token:
            continue

        graph_value = result.get("executionEffectiveGraphPath")
        graph_digest = result.get("executionEffectiveGraphSha256")
        assembly_value = result.get("outputAssemblyPath")
        assembly_digest = result.get("outputAssemblySha256")
        if not all((graph_value, graph_digest, assembly_value, assembly_digest)):
            continue
        graph_path = workspace_file(root, graph_value)
        assembly_path = workspace_file(root, assembly_value)
        if sha(graph_path) != graph_digest or sha(assembly_path) != assembly_digest:
            raise ValueError("released CAD output or execution graph changed")
        graph = read(graph_path)
        tokens = [str(row.get("ModuleToken") or "") for row in graph.get("Modules") or []]
        if len(tokens) != 2 or set(tokens) != {source_token, base_token}:
            continue
        if tokens.count(source_token) != 1 or tokens.count(base_token) != 1:
            continue
        eligible.append(
            {
                "effectiveGraphPath": str(graph_path),
                "effectiveGraphSha256": graph_digest,
                "cadResultPath": str(result_path),
                "cadResultSha256": sha(result_path),
                "outputAssemblyPath": str(assembly_path),
                "outputAssemblySha256": assembly_digest,
                "catalogResolution": pair.get("catalogResolution"),
                "evidenceSource": "released_manifest_validation_evidence",
            }
        )
    if len(eligible) > 1:
        raise ValueError("released pair has ambiguous eligible CAD validation evidence")
    return eligible[0] if eligible else {}


def _work_class(category):
    """Map a precise gap reason to the next executable kind of work."""

    if category in {
        "cad_validation_pending",
        "station_candidate_ready_for_cad_validation",
        "nonprototype_cad_validation_required_after_confirmation",
        "native_transport_station_nonprototype_cad_validation_required",
        "native_service_nonprototype_cad_validation_required",
    }:
        return "cad_validation"
    if category in {
        "target_station_postcheck_required_from_existing_saved_output",
        "native_transport_station_postcheck_required_from_existing_saved_output",
        "native_service_binding_ready_for_station_postcheck",
        "wastecup_mapping_selected_requires_station_candidate",
    }:
        return "saved_output_postcheck_or_candidate_materialization"
    if category in {
        "scanner_exact_point_pair_candidate_requires_current_context",
        "scanner_composed_rule_candidate_requires_current_context",
        "scanner_exact_chain_instance_binding_required",
        "scanner_saved_context_geometry_evaluation_required",
        "scanner_new_cumulative_chain_context_required",
    }:
        return "current_context_chain_and_postcheck"
    if category in {
        "scanner_independent_point_pair_or_measurement_required",
        "measurement_or_label_missing",
        "target_station_geometry_inventory_missing",
    }:
        return "measurement_or_role_selection"
    if category in {
        "mechanical_interface_authority_revoked_requires_new_binding",
        "mechanical_interface_authority_missing",
    }:
        return "mechanical_binding"
    if category in {
        "target_functional_geometry_mismatch",
        "target_function_point_height_decision_required",
        "target_function_point_height_and_interface_review_required",
        "target_station_engineering_confirmation_required",
        "target_service_capability_incomplete",
        "target_service_capability_semantic_mapping_decision_required",
        "transport_work_area_context_and_policy_required",
        "topology_specific_station_candidate_review_required",
        "scanner_role_selection_from_candidate_catalog_required",
    }:
        return "engineering_decision"
    if category in {
        "reusable_measurement_needs_semantic_binding",
        "reusable_measurement_needs_rule_compilation",
        "cleaning_service_semantic_binding_required",
        "wastecup_source_function_mapping_required",
        "topology_specific_station_derivation_required",
        "station_candidate_projection_failed",
    }:
        return "reusable_data_rule_derivation"
    return "data_or_rule_derivation"


def classify_gap(row):
    """Classify the next missing fact without claiming CAD or engineering success."""
    row["pairClass"] = ("native_pair" if row["sourceModuleDefinitionId"].split("::")[0]
                        == row["targetBaseDefinitionId"].split("::")[0] else "cross_project_pair")
    capability = row.get("serviceCapabilityCoverage")
    functional_screening = row.get("functionalGeometryScreening")
    candidate = row.get("stationCandidateDecision")
    candidate_status = str((candidate or {}).get("candidateStatus") or "")
    scanner_readiness = row.get("scannerRuleReadiness") or {}
    scanner_status = str(scanner_readiness.get("status") or "")
    if scanner_status == "exact_point_pair_candidate_available":
        category = "scanner_exact_point_pair_candidate_requires_current_context"
    elif scanner_status == "composition_candidate_ready":
        category = "scanner_composed_rule_candidate_requires_current_context"
    elif scanner_status == "independent_point_pair_or_measurement_required":
        required = list(scanner_readiness.get("requiredNextEvidence") or [])
        if required and all(
            str(value).endswith("_selection_from_candidate_catalog")
            for value in required
        ):
            category = "scanner_role_selection_from_candidate_catalog_required"
        else:
            category = "scanner_independent_point_pair_or_measurement_required"
    elif candidate_status == "planar_candidate_requires_height_decision":
        category = "target_function_point_height_decision_required"
    elif "_requires_height_and_" in candidate_status:
        category = "target_function_point_height_and_interface_review_required"
    elif candidate_status.endswith("_ready_for_engineering_review"):
        category = "topology_specific_station_candidate_review_required"
    elif candidate_status == "recommendation_pending_engineering_confirmation":
        category = "target_station_engineering_confirmation_required"
    elif candidate_status == (
        "engineering_confirmation_recorded_requires_target_station_postcheck"
    ):
        history = row.get("historicalPairEvidence") or {}
        if history.get("cadResultPath") and history.get("effectiveGraphPath"):
            category = "target_station_postcheck_required_from_existing_saved_output"
        else:
            category = "nonprototype_cad_validation_required_after_confirmation"
    elif candidate_status == (
        "native_station_requires_current_saved_output_station_postcheck"
    ):
        history = row.get("historicalPairEvidence") or {}
        if history.get("cadResultPath") and history.get("effectiveGraphPath"):
            category = "native_transport_station_postcheck_required_from_existing_saved_output"
        else:
            category = "native_transport_station_nonprototype_cad_validation_required"
    elif candidate_status == "ready_for_exact_chain_instance_selection":
        category = "scanner_exact_chain_instance_binding_required"
    elif candidate_status == (
        "exact_saved_context_available_requires_geometry_evaluation"
    ):
        category = "scanner_saved_context_geometry_evaluation_required"
    elif candidate_status == "new_cumulative_chain_context_required":
        category = "scanner_new_cumulative_chain_context_required"
    elif candidate_status == "current_context_point_pair_geometry_mismatch":
        category = "target_functional_geometry_mismatch"
    elif candidate_status == "current_context_proxy_passed_requires_station_registration":
        category = "station_candidate_ready_for_cad_validation"
    elif candidate_status == (
        "wastecup_mapping_selected_requires_saved_base_pose_and_station_candidate"
    ):
        category = "wastecup_mapping_selected_requires_station_candidate"
    elif candidate_status == (
        "native_service_identity_binding_ready_for_station_rule_and_readonly_postcheck"
    ):
        history = row.get("historicalPairEvidence") or {}
        category = (
            "native_service_binding_ready_for_station_postcheck"
            if history.get("cadResultPath") and history.get("effectiveGraphPath")
            else "native_service_nonprototype_cad_validation_required"
        )
    elif candidate_status in {
        "two_axis_stations_miss_target_function_point",
        "flexible_slot_candidates_miss_target_function_point",
    }:
        category = "target_functional_geometry_mismatch"
    elif candidate_status in {
        "target_two_axis_station_inventory_missing",
        "target_flexible_slot_inventory_or_offset_missing",
    }:
        category = "target_station_geometry_inventory_missing"
    elif candidate_status.startswith("topology_specific_"):
        category = "topology_specific_station_derivation_required"
    elif candidate_status == "ready_for_nonprototype_cad_validation":
        category = "station_candidate_ready_for_cad_validation"
    elif candidate_status == "function_point_projection_candidate_failed":
        category = "station_candidate_projection_failed"
    elif functional_screening is not None and functional_screening.get("passed") is False:
        category = "target_functional_geometry_mismatch"
    elif capability is not None and capability.get("passed") is False:
        missing = set(capability.get("missingCapabilities") or [])
        near_match = set(capability.get("nearMatchRequiredCapabilities") or [])
        category = (
            "target_service_capability_semantic_mapping_decision_required"
            if missing and missing.issubset(near_match)
            else "target_service_capability_incomplete"
        )
    elif (
        row.get("transportWorkAreaReview") is not None
        and row["transportWorkAreaReview"].get("publicationAllowed") is False
    ):
        category = "transport_work_area_context_and_policy_required"
    elif (row.get("executionAuthorityMissing")
          and (row.get("authority") or {}).get("status")
          == "released_driving_template_revoked"):
        category = "mechanical_interface_authority_revoked_requires_new_binding"
    elif row.get("status") == "existing_rule_validation_pending":
        history = row.get("historicalPairEvidence") or {}
        category = (
            "target_station_postcheck_required_from_existing_saved_output"
            if history.get("cadResultPath") and history.get("effectiveGraphPath")
            else "cad_validation_pending"
        )
    elif row.get("status") == "generated_installation_rule_candidate":
        category = "cad_validation_pending"
    elif row.get("executionAuthorityMissing"):
        category = "mechanical_interface_authority_missing"
    elif (row.get("role") == "WasteCup"
          and row.get("reusableTargetConfigs")
          and not row.get("reusableSourceConfigs")):
        category = "wastecup_source_function_mapping_required"
    elif (row.get("role") == "CleaningWeighing"
          and any(
              "bind_source_service_subtrees_to_target_service_station"
              in (asset.get("stillRequired") or [])
              for asset in row.get("targetMeasurementAssets") or []
          )):
        category = "cleaning_service_semantic_binding_required"
    elif row.get("targetMeasurementAssets"):
        required = {value for asset in row["targetMeasurementAssets"] for value in asset.get("stillRequired", [])}
        semantic_markers = (
            "label", "mapping", "binding", "bind_", "confirm", "resolve",
            "selected_transport_instance", "optical_axis_sign",
        )
        if any(any(marker in value.lower() for marker in semantic_markers) for value in required):
            category = "reusable_measurement_needs_semantic_binding"
        else:
            category = "reusable_measurement_needs_rule_compilation"
    elif row.get("reusableTargetConfigs"):
        # A target-side functional rule is real reusable station data, but a
        # different source model still needs an explicit local-function-point
        # mapping.  Do not report this as either no data or ready to compile.
        category = "reusable_measurement_needs_semantic_binding"
    else:
        category = "measurement_or_label_missing"
    row["gapCategory"] = category
    row["workClass"] = _work_class(category)
    return row


def direct_rule_candidate(scope, pair, authority):
    """Reuse only a fully locating exact mechanical recipe, not a datum pose."""
    if pair["role"] not in {"Calibration", "Transport"} or authority.get("ready") is not True:
        return None
    if authority.get("relationExecutionMode") != "direct_installation":
        return None
    template = (authority.get("preferredPlan", {}).get("nativePlan", {}).get("instantiatedTemplate") or {})
    if template.get("constraintEffect", {}).get("fullyLocatesAddedComponent") is not True:
        return None
    source_port, slot_port = template.get("modulePortId"), template.get("slotPortId")
    if not source_port or not slot_port or not authority.get("releaseManifestPath"):
        return None
    # Identify which same-role native station the target port names. Never assume
    # that an arbitrary compatible port is a target-role station.
    target_project = pair["targetBaseDefinitionId"].split("::")[0]
    natives = [m for m in scope["movingModules"] if m["role"] == pair["role"]
        and m["moduleDefinitionId"].split("::")[0] == target_project
        and re.search(r"(^|[._])" + re.escape(m["moduleDefinitionId"].split("::")[1]) + r"([._]|$)", slot_port, re.I)]
    if len(natives) != 1:
        return None
    source, base = pair["sourceModuleDefinitionId"], pair["targetBaseDefinitionId"]
    rid = "batch-" + source.replace("::", "-") + "-to-" + base.replace("::", "-") + "-v1"
    config = {"schemaVersion": "released-station-parameters-rule/v1", "ruleId": rid,
        "sourceModuleDefinitionId": source, "targetBaseDefinitionId": base,
        "nativeRoleModuleDefinitionId": natives[0]["moduleDefinitionId"],
        "sourcePortId": source_port, "targetPortId": slot_port,
        "inputs": {"referenceReleasePath": authority["releaseManifestPath"]},
        "coordinateSystem": "target_registered_native_role_installation_datums",
        "interpretationLimits": ["Registered installation parameters only; functional reach and fastening are not verified.",
                                 "Candidate generated from existing exact interface evidence; new station CAD validation is pending."]}
    rule = {"ruleId": rid, "role": pair["role"], "sourceModuleDefinitionId": source,
            "targetBaseDefinitionId": base, "evaluator": {"kind": "released_mate_parameters"},
            "placement": {"strategy": "released_recipe"}, "validation": {"status": "candidate"}}
    return rule, config


def prepare_station_gap_batch(workspace, coverage_path, registry_path, output,
                              authority_resolver=resolve_preferred_released_interface_authority,
                              *, measurement_index_path=None, capability_index_path=None,
                              functional_screening_index_path=None,
                              candidate_decision_index_path=None,
                              transport_work_area_review_index_path=None,
                              scanner_rule_readiness_index_path=None):
    root, output = Path(workspace).resolve(), Path(output).resolve()
    output.relative_to(root)
    if output.exists():
        raise FileExistsError(output)
    started, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    coverage, registry = read(root / coverage_path), read(root / registry_path)
    measurement_path = (workspace_file(root, measurement_index_path) if measurement_index_path is not None
                        else root / "data/assembly_stations/measurement-reuse-index-v1.json")
    measurements = read(measurement_path)["entries"] if measurement_path.is_file() else []
    for item in measurements:
        item["fileEvidence"] = [{"path": p, "exists": (root/p).is_file(),
                                 "sha256": sha(root/p) if (root/p).is_file() else None} for p in item["paths"]]
    capability_path = (
        workspace_file(root, capability_index_path)
        if capability_index_path is not None
        else (root / DEFAULT_CAPABILITY_INDEX).resolve()
    )
    capability_entries = []
    if capability_path.is_file():
        capability_index = read(capability_path)
        if capability_index.get("schemaVersion") != "cleaning-service-capability-coverage-index/v1":
            raise ValueError("unsupported cleaning service capability index")
        capability_entries = list(capability_index.get("entries") or [])
        pair_keys = []
        for item in capability_entries:
            key = (
                item.get("sourceModuleDefinitionId"),
                item.get("targetBaseDefinitionId"),
                item.get("role"),
            )
            pair_keys.append(key)
            report_path = workspace_file(root, item.get("reportPath"))
            if not report_path.is_file() or sha(report_path) != item.get("reportSha256"):
                raise ValueError(f"capability audit evidence changed: {key}")
            report = read(report_path)
            service_coverage = report.get("capabilityCoverage") or {}
            if (
                report.get("source") != key[0]
                or report.get("target") != key[1]
                or report.get("auditDigest") != item.get("auditDigest")
                or service_coverage.get("passed") is not item.get("passed")
                or sorted(service_coverage.get("missingCapabilities") or [])
                != sorted(item.get("missingCapabilities") or [])
            ):
                raise ValueError(f"capability audit index binding changed: {key}")
        if len(pair_keys) != len(set(pair_keys)):
            raise ValueError("duplicate cleaning service capability pair")
    functional_path = (
        workspace_file(root, functional_screening_index_path)
        if functional_screening_index_path is not None
        else (root / DEFAULT_FUNCTIONAL_SCREENING_INDEX).resolve()
    )
    functional_entries = []
    if functional_path.is_file():
        functional_index = read(functional_path)
        if functional_index.get("schemaVersion") != "station-functional-screening-index/v1":
            raise ValueError("unsupported station functional screening index")
        keys = []
        for item in functional_index.get("entries") or []:
            key = (item.get("sourceModuleDefinitionId"), item.get("targetBaseDefinitionId"), item.get("role"))
            keys.append(key)
            report_path = workspace_file(root, item.get("reportPath"))
            if not report_path.is_file() or sha(report_path) != item.get("reportSha256"):
                raise ValueError(f"functional screening evidence changed: {key}")
            report = read(report_path)
            screening = report.get("screening") or {}
            if (report.get("sourceModuleDefinitionId") != key[0]
                    or report.get("targetBaseDefinitionId") != key[1]
                    or report.get("role") != key[2]
                    or screening.get("passed") is not item.get("passed")
                    or screening.get("status") != item.get("status")):
                raise ValueError(f"functional screening index binding changed: {key}")
            functional_entries.append(item)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate station functional screening pair")
    candidate_path = (
        workspace_file(root, candidate_decision_index_path)
        if candidate_decision_index_path is not None
        else (root / DEFAULT_CANDIDATE_DECISION_INDEX).resolve()
    )
    candidate_entries = []
    if candidate_path.is_file():
        candidate_index = read(candidate_path)
        if candidate_index.get("schemaVersion") != "station-candidate-decision-index/v1":
            raise ValueError("unsupported station candidate decision index")
        report_cache = {}
        keys = []
        for item in candidate_index.get("entries") or []:
            key = (item.get("sourceModuleDefinitionId"), item.get("targetBaseDefinitionId"), item.get("role"))
            keys.append(key)
            report_path = workspace_file(root, item.get("reportPath"))
            if not report_path.is_file() or sha(report_path) != item.get("reportSha256"):
                raise ValueError(f"station candidate decision evidence changed: {key}")
            report = report_cache.setdefault(str(report_path), read(report_path))
            matches = [row for row in report.get("candidates") or []
                       if row.get("sourceModuleDefinitionId") == key[0]
                       and row.get("targetBaseDefinitionId") == key[1]]
            if (len(matches) != 1
                    or matches[0].get("status") != item.get("candidateStatus")
                    or matches[0].get("interfaceTopology") != item.get("interfaceTopology")
                    or (matches[0].get("readyForCadValidation") is True)
                    is not item.get("readyForCadValidation")):
                raise ValueError(f"station candidate decision index binding changed: {key}")
            candidate_entries.append(item)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate station candidate decision pair")
    transport_review_path = (
        workspace_file(root, transport_work_area_review_index_path)
        if transport_work_area_review_index_path is not None
        else (root / DEFAULT_TRANSPORT_WORK_AREA_REVIEW_INDEX).resolve()
    )
    transport_review_entries = []
    if transport_review_path.is_file():
        transport_index = read(transport_review_path)
        if transport_index.get("schemaVersion") != "transport-work-area-review-index/v1":
            raise ValueError("unsupported transport work-area review index")
        report_cache = {}
        keys = []
        for item in transport_index.get("entries") or []:
            key = (
                item.get("sourceModuleDefinitionId"),
                item.get("targetBaseDefinitionId"),
                item.get("role"),
            )
            keys.append(key)
            if key[2] != "Transport":
                raise ValueError(f"transport work-area review has wrong role: {key}")
            report_path = workspace_file(root, item.get("reportPath"))
            if not report_path.is_file() or sha(report_path) != item.get("reportSha256"):
                raise ValueError(f"transport work-area review evidence changed: {key}")
            report = report_cache.setdefault(str(report_path), read(report_path))
            matches = [
                row for row in report.get("comparisons") or []
                if row.get("sourceTransportModuleDefinitionId") == key[0]
                and row.get("targetBaseDefinitionId") == key[1]
            ]
            if (
                len(matches) != 1
                or matches[0].get("comparisonDigest") != item.get("comparisonDigest")
                or matches[0].get("status") != item.get("status")
                or matches[0].get("publicationAllowed")
                is not item.get("publicationAllowed")
                or sorted(matches[0].get("blockingReasonCodes") or [])
                != sorted(item.get("blockingReasonCodes") or [])
            ):
                raise ValueError(f"transport work-area review index binding changed: {key}")
            transport_review_entries.append(item)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate transport work-area review pair")
    scanner_readiness_path = (
        workspace_file(root, scanner_rule_readiness_index_path)
        if scanner_rule_readiness_index_path is not None
        else None
    )
    scanner_readiness_entries = []
    if scanner_readiness_path is not None:
        if not scanner_readiness_path.is_file():
            raise ValueError(f"RULE_INPUT_MISSING: {scanner_readiness_path}")
        scanner_index = read(scanner_readiness_path)
        if scanner_index.get("schemaVersion") != "scanner-target-rule-composition-batch/v1":
            raise ValueError("unsupported scanner rule readiness index")
        body = dict(scanner_index)
        expected_digest = body.pop("batchDigest", None)
        if expected_digest != _json_digest(body):
            raise ValueError("scanner rule readiness digest changed")
        for evidence in scanner_index.get("evidence") or []:
            evidence_path = workspace_file(root, evidence.get("path"))
            if not evidence_path.is_file() or sha(evidence_path) != evidence.get("sha256"):
                raise ValueError("scanner rule readiness evidence changed")
        keys = []
        allowed = {
            "exact_point_pair_candidate_available",
            "composition_candidate_ready",
            "independent_point_pair_or_measurement_required",
        }
        for item in scanner_index.get("rows") or []:
            key = (
                item.get("sourceModuleDefinitionId"),
                item.get("targetBaseDefinitionId"),
            )
            keys.append(key)
            if item.get("status") not in allowed:
                raise ValueError(f"unsupported scanner rule readiness status: {key}")
            if not item.get("transportModuleDefinitionId"):
                raise ValueError(f"scanner readiness transport is missing: {key}")
            scanner_readiness_entries.append(item)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate scanner rule readiness pair")
    scope = coverage["scope"]
    identities = {r["moduleDefinitionId"]: r["cadModuleDefinitionId"] for r in scope["bases"]+scope["movingModules"]}
    library = []
    for rule in registry["rules"]:
        path = root / rule["evaluator"]["inputPath"]
        config = read(path)
        library.append({"source": rule["sourceModuleDefinitionId"], "base": rule["targetBaseDefinitionId"],
                        "role": rule["role"], "kind": rule["evaluator"]["kind"],
                        "configPath": str(path), "sha256": sha(path),
                        "inputs": config.get("inputs", {}), "nativeRole": config.get("nativeRoleModuleDefinitionId")})
    queue, generated = [], []
    output.mkdir(parents=True)
    from json import dumps
    def save(path, value):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    pending = [p for p in coverage["pairs"] if not p["validatedStationRule"]]
    pending.sort(key=lambda p: (PRIORITY[p["role"]], p["targetBaseDefinitionId"] not in {"project02::A600", "project05::A000"}, p["sourceModuleDefinitionId"], p["targetBaseDefinitionId"]))
    for pair in pending:
        source, base = pair["sourceModuleDefinitionId"], pair["targetBaseDefinitionId"]
        row = {"sourceModuleDefinitionId": source, "targetBaseDefinitionId": base, "role": pair["role"],
               "historicalMissingData": pair["missingData"], "cadLaunchAllowed": False,
               "validatedStationRule": False, "requiredData": REQUIRED[pair["role"]],
               "reusableSourceConfigs": [r for r in library if r["source"] == source],
               "reusableTargetConfigs": [r for r in library if r["base"] == base and r["role"] == pair["role"]]}
        row["targetMeasurementAssets"] = [r for r in measurements
            if r["targetBaseDefinitionId"] == base and r["role"] == pair["role"]]
        capability_matches = [
            r
            for r in capability_entries
            if r["sourceModuleDefinitionId"] == source
            and r["targetBaseDefinitionId"] == base
            and r["role"] == pair["role"]
        ]
        if len(capability_matches) > 1:
            raise ValueError("ambiguous cleaning service capability coverage")
        if capability_matches:
            row["serviceCapabilityCoverage"] = capability_matches[0]
        functional_matches = [r for r in functional_entries
            if r["sourceModuleDefinitionId"] == source
            and r["targetBaseDefinitionId"] == base
            and r["role"] == pair["role"]]
        if len(functional_matches) > 1:
            raise ValueError("ambiguous station functional geometry screening")
        if functional_matches:
            row["functionalGeometryScreening"] = functional_matches[0]
        candidate_matches = [r for r in candidate_entries
            if r["sourceModuleDefinitionId"] == source
            and r["targetBaseDefinitionId"] == base
            and r["role"] == pair["role"]]
        if len(candidate_matches) > 1:
            raise ValueError("ambiguous station candidate decision")
        if candidate_matches:
            row["stationCandidateDecision"] = candidate_matches[0]
        transport_review_matches = [
            r for r in transport_review_entries
            if r["sourceModuleDefinitionId"] == source
            and r["targetBaseDefinitionId"] == base
            and r["role"] == pair["role"]
        ]
        if len(transport_review_matches) > 1:
            raise ValueError("ambiguous transport work-area review")
        if transport_review_matches:
            row["transportWorkAreaReview"] = transport_review_matches[0]
        scanner_readiness_matches = [
            r
            for r in scanner_readiness_entries
            if r["sourceModuleDefinitionId"] == source
            and r["targetBaseDefinitionId"] == base
        ]
        if len(scanner_readiness_matches) > 1:
            raise ValueError("ambiguous scanner rule readiness")
        if scanner_readiness_matches:
            if pair["role"] != "Scanner":
                raise ValueError("scanner readiness was bound to a non-scanner pair")
            row["scannerRuleReadiness"] = scanner_readiness_matches[0]
        try:
            authority = authority_resolver(root, identities[source], selected_slot_definition_id=identities[base], allow_datum_fallback=True)
            row["authority"] = {k: authority.get(k) for k in ("ready", "status", "relationExecutionMode", "releaseManifestPath")}
            pair_evidence = authority.get("pairReleaseEvidence") or {}
            row["historicalPairEvidence"] = {k: pair_evidence.get(k) for k in
                ("effectiveGraphPath", "effectiveGraphSha256", "cadResultPath", "cadResultSha256", "catalogResolution")}
            if not (
                row["historicalPairEvidence"].get("cadResultPath")
                and row["historicalPairEvidence"].get("effectiveGraphPath")
            ):
                recovered_history = _released_pair_cad_history(
                    root,
                    authority=authority,
                    source_module_definition_id=source,
                    target_base_definition_id=base,
                )
                if recovered_history:
                    row["historicalPairEvidence"] = recovered_history
            if pair["configuredStationRule"]:
                row["status"] = "existing_rule_validation_pending"
            else:
                candidate = direct_rule_candidate(scope, pair, authority)
                if candidate is not None:
                    rule, config = candidate
                    config["inputSha256"] = {"referenceReleasePath": sha(root / config["inputs"]["referenceReleasePath"])}
                    path = output / (rule["ruleId"] + ".json")
                    save(path, config)
                    rule["evaluator"]["inputPath"] = str(path.relative_to(root)).replace("\\", "/")
                    review = validate_rule(root, rule, scope)
                    if not review["configuredStationRule"] or review["blockingReasonCodes"]:
                        raise ValueError("Generated candidate invalid: " + str(review))
                    generated.append(rule)
                    row.update(status="generated_installation_rule_candidate", ruleId=rule["ruleId"],
                               configurationPath=str(path), review=review)
                else:
                    row["status"] = "functional_geometry_or_station_binding_required"
            if authority.get("ready") is not True:
                row["executionAuthorityMissing"] = True
        except (ValueError, OSError, KeyError) as exc:
            row.update(status="authority_or_data_review_required", error=str(exc))
        queue.append(classify_gap(row))
    merged = deepcopy(registry)
    merged["rules"].extend(generated)
    save(output / "station-rules.json", merged)
    report = {"schemaVersion": "station-gap-batch-preparation/v1", "queue": queue,
              "summary": {"pendingPairCount": len(queue), "generatedCandidateCount": len(generated),
                          "statusCounts": dict(Counter(r["status"] for r in queue)),
                          "gapCategoryCounts": dict(Counter(r["gapCategory"] for r in queue)),
                          "workClassCounts": dict(Counter(r["workClass"] for r in queue)),
                          "pairClassCounts": dict(Counter(r["pairClass"] for r in queue)),
                          "byRole": dict(Counter(r["role"] for r in queue))},
              "sourceFiles": [{"path": str(root/p), "sha256": sha(root/p)} for p in (coverage_path, registry_path)],
              "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
              "durationSeconds": perf_counter()-clock, "cadExecuted": False,
              "boundary": "Configuration candidates only; not new CAD evidence or automatic mechanical compatibility."}
    if measurement_path.is_file():
        report["sourceFiles"].append({"path": str(measurement_path), "sha256": sha(measurement_path)})
    if capability_path.is_file():
        report["sourceFiles"].append({"path": str(capability_path), "sha256": sha(capability_path)})
    if functional_path.is_file():
        report["sourceFiles"].append({"path": str(functional_path), "sha256": sha(functional_path)})
    if candidate_path.is_file():
        report["sourceFiles"].append({"path": str(candidate_path), "sha256": sha(candidate_path)})
    if transport_review_path.is_file():
        report["sourceFiles"].append({
            "path": str(transport_review_path),
            "sha256": sha(transport_review_path),
        })
    if scanner_readiness_path is not None:
        report["sourceFiles"].append({
            "path": str(scanner_readiness_path),
            "sha256": sha(scanner_readiness_path),
        })
    save(output / "gap-queue.json", report)
    lines = ["# 批量工位缺口队列", "", "候选配置不等于工位已验证。所列数据要求不是断言历史仓库中完全没有这些数据。", "",
             "|来源|目标基座|角色|配对类别|缺口类别|处理结果|", "|---|---|---|---|---|---|"]
    lines += [f"|{r['sourceModuleDefinitionId']}|{r['targetBaseDefinitionId']}|{r['role']}|{r['pairClass']}|{r['gapCategory']}|{r['status']}|" for r in queue]
    (output / "README-CN.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return report

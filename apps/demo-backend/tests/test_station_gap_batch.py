from copy import deepcopy
import pytest
from demo_backend.station_gap_batch import (
    _released_pair_cad_history,
    _work_class,
    classify_gap,
    direct_rule_candidate,
)


def example():
    scope = {"movingModules": [{"moduleDefinitionId": "p2::CAL", "role": "Calibration"}]}
    pair = {"sourceModuleDefinitionId": "p1::OTHER", "targetBaseDefinitionId": "p2::BASE", "role": "Calibration"}
    authority = {"ready": True, "relationExecutionMode": "direct_installation", "releaseManifestPath": "release.json",
                 "preferredPlan": {"nativePlan": {"instantiatedTemplate": {
                     "modulePortId": "OTHER.mount", "slotPortId": "BASE.cal_installation",
                     "constraintEffect": {"fullyLocatesAddedComponent": True}}}}}
    return scope, pair, authority


def test_generated_rule_is_candidate_and_uses_target_native_station():
    scope, pair, authority = example()
    original = deepcopy(authority)
    rule, config = direct_rule_candidate(scope, pair, authority)
    assert rule["validation"] == {"status": "candidate"}
    assert config["nativeRoleModuleDefinitionId"] == "p2::CAL"
    assert config["inputs"]["referenceReleasePath"] == "release.json"
    assert authority == original
    assert "SourceTransform" not in str(config)


@pytest.mark.parametrize("failure", ["datum", "not_ready", "partial", "unknown_slot", "duplicate", "scanner", "waste", "cleaning"])
def test_cannot_promote_parameter_pose_or_unknown_functional_station(failure):
    scope, pair, authority = example()
    template = authority["preferredPlan"]["nativePlan"]["instantiatedTemplate"]
    if failure == "datum": authority["relationExecutionMode"] = "datum_placement_demo"
    if failure == "not_ready": authority["ready"] = False
    if failure == "partial": template["constraintEffect"]["fullyLocatesAddedComponent"] = False
    if failure == "unknown_slot": template["slotPortId"] = "BASE.generic_plane"
    if failure == "duplicate": scope["movingModules"].append(deepcopy(scope["movingModules"][0]))
    if failure in {"scanner", "waste", "cleaning"}: pair["role"] = {"scanner": "Scanner", "waste": "WasteCup", "cleaning": "CleaningWeighing"}[failure]
    assert direct_rule_candidate(scope, pair, authority) is None


@pytest.mark.parametrize("missing_index", [False, True])
def test_explicit_measurement_index_is_bound_and_missing_is_not_silent(tmp_path, missing_index):
    import json
    from demo_backend.station_gap_batch import prepare_station_gap_batch
    from demo_backend.station_rule_registry import sha
    def save(name, value):
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    save("coverage.json", {"scope": {"bases": [], "movingModules": []}, "pairs": []})
    save("registry.json", {"rules": []})
    if not missing_index: save("index.json", {"entries": []})
    kwargs = dict(measurement_index_path="index.json")
    if missing_index:
        with pytest.raises(ValueError, match="RULE_INPUT_MISSING"):
            prepare_station_gap_batch(tmp_path, "coverage.json", "registry.json", tmp_path / "output", **kwargs)
        assert not (tmp_path / "output").exists()
    else:
        result = prepare_station_gap_batch(tmp_path, "coverage.json", "registry.json", tmp_path / "output", **kwargs)
        assert {"path": str(tmp_path / "index.json"), "sha256": sha(tmp_path / "index.json")} in result["sourceFiles"]
        assert result["summary"]["pendingPairCount"] == 0
        assert result["cadExecuted"] is False


def test_explicit_capability_index_is_authenticated_without_shadowing_coverage(tmp_path):
    import hashlib
    import json
    from demo_backend.station_gap_batch import prepare_station_gap_batch
    from demo_backend.station_rule_registry import sha

    def save(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    save("coverage.json", {"scope": {"bases": [], "movingModules": []}, "pairs": []})
    save("registry.json", {"rules": []})
    report = {
        "source": "project01::GN00",
        "target": "project05::A000",
        "capabilityCoverage": {
            "passed": False,
            "missingCapabilities": ["weighing"],
        },
    }
    report["auditDigest"] = hashlib.sha256(b"audit").hexdigest()
    report_path = save("audit.json", report)
    index = {
        "schemaVersion": "cleaning-service-capability-coverage-index/v1",
        "entries": [{
            "sourceModuleDefinitionId": report["source"],
            "targetBaseDefinitionId": report["target"],
            "role": "CleaningWeighing",
            "reportPath": "audit.json",
            "reportSha256": sha(report_path),
            "auditDigest": report["auditDigest"],
            "passed": False,
            "missingCapabilities": ["weighing"],
        }],
    }
    index_path = save("capability-index.json", index)
    result = prepare_station_gap_batch(
        tmp_path,
        "coverage.json",
        "registry.json",
        tmp_path / "output",
        capability_index_path="capability-index.json",
    )
    assert {"path": str(index_path), "sha256": sha(index_path)} in result["sourceFiles"]
    assert result["summary"]["pendingPairCount"] == 0


def test_explicit_functional_screening_index_is_authenticated(tmp_path):
    import json
    from demo_backend.station_gap_batch import prepare_station_gap_batch
    from demo_backend.station_rule_registry import sha

    def save(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    pair = {
        "sourceModuleDefinitionId": "project02::A300",
        "targetBaseDefinitionId": "project05::A000",
        "role": "WasteCup",
    }
    save("coverage.json", {"scope": {"bases": [], "movingModules": []}, "pairs": []})
    save("registry.json", {"rules": []})
    report = {
        **pair,
        "screening": {
            "passed": False,
            "status": "published_orientation_cannot_reach_target_by_translation",
        },
    }
    report_path = save("screen.json", report)
    index = {
        "schemaVersion": "station-functional-screening-index/v1",
        "entries": [{
            **pair,
            "reportPath": "screen.json",
            "reportSha256": sha(report_path),
            "passed": False,
            "status": report["screening"]["status"],
        }],
    }
    index_path = save("screen-index.json", index)
    result = prepare_station_gap_batch(
        tmp_path,
        "coverage.json",
        "registry.json",
        tmp_path / "output",
        functional_screening_index_path="screen-index.json",
    )
    assert {"path": str(index_path), "sha256": sha(index_path)} in result["sourceFiles"]

    report["screening"]["passed"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        prepare_station_gap_batch(
            tmp_path,
            "coverage.json",
            "registry.json",
            tmp_path / "tampered-output",
            functional_screening_index_path="screen-index.json",
        )


def test_transport_work_area_review_index_refines_cad_pending_and_is_tamper_evident(tmp_path):
    import json
    from demo_backend.station_gap_batch import prepare_station_gap_batch
    from demo_backend.station_rule_registry import sha

    def save(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    pair = {
        "sourceModuleDefinitionId": "project01::SS00",
        "targetBaseDefinitionId": "project05::A000",
        "role": "Transport",
    }
    coverage_pair = {
        **pair,
        "validatedStationRule": False,
        "configuredStationRule": True,
        "missingData": ["TARGET_STATION_VALIDATION_PENDING"],
    }
    save("coverage.json", {
        "scope": {
            "bases": [{
                "moduleDefinitionId": "project05::A000",
                "cadModuleDefinitionId": "cad-base",
            }],
            "movingModules": [{
                "moduleDefinitionId": "project01::SS00",
                "cadModuleDefinitionId": "cad-transport",
                "role": "Transport",
            }],
        },
        "pairs": [coverage_pair],
    })
    config_path = save("transport-config.json", {
        "inputs": {}, "nativeRoleModuleDefinitionId": "project05::D000",
    })
    save("registry.json", {"rules": [{
        **pair,
        "ruleId": "candidate",
        "evaluator": {"kind": "transport_position_parameters", "inputPath": "transport-config.json"},
    }]})
    comparison = {
        "sourceTransportModuleDefinitionId": pair["sourceModuleDefinitionId"],
        "targetBaseDefinitionId": pair["targetBaseDefinitionId"],
        "comparisonDigest": "c" * 64,
        "status": "requires_engineering_threshold_or_context_selection",
        "publicationAllowed": False,
        "blockingReasonCodes": [
            "WORK_POSITION_CONTEXT_SELECTION_REQUIRED",
            "CURRENT_CAD_WORK_POSITION_REPROJECTION_REQUIRED",
        ],
    }
    report_path = save("work-area-report.json", {"comparisons": [comparison]})
    index_path = save("work-area-index.json", {
        "schemaVersion": "transport-work-area-review-index/v1",
        "entries": [{
            **pair,
            "reportPath": "work-area-report.json",
            "reportSha256": sha(report_path),
            "comparisonDigest": comparison["comparisonDigest"],
            "status": comparison["status"],
            "publicationAllowed": False,
            "blockingReasonCodes": comparison["blockingReasonCodes"],
        }],
    })

    def authority(*args, **kwargs):
        return {
            "ready": False,
            "status": "datum_fallback_requires_explicit_position_parameters",
            "relationExecutionMode": None,
            "releaseManifestPath": None,
        }

    result = prepare_station_gap_batch(
        tmp_path,
        "coverage.json",
        "registry.json",
        tmp_path / "output",
        authority_resolver=authority,
        transport_work_area_review_index_path="work-area-index.json",
    )
    assert result["queue"][0]["gapCategory"] == (
        "transport_work_area_context_and_policy_required"
    )
    assert result["queue"][0]["transportWorkAreaReview"][
        "publicationAllowed"
    ] is False
    assert {"path": str(index_path), "sha256": sha(index_path)} in result[
        "sourceFiles"
    ]

    report_path.write_text(json.dumps({"comparisons": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        prepare_station_gap_batch(
            tmp_path,
            "coverage.json",
            "registry.json",
            tmp_path / "tampered-output",
            authority_resolver=authority,
            transport_work_area_review_index_path="work-area-index.json",
        )


def test_station_candidate_decision_index_is_authenticated_and_tamper_evident(tmp_path):
    import json
    from demo_backend.station_gap_batch import prepare_station_gap_batch
    from demo_backend.station_rule_registry import sha

    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    save("coverage.json", {"scope": {"bases": [], "movingModules": []}, "pairs": []})
    save("registry.json", {"rules": []})
    pair = {
        "sourceModuleDefinitionId": "project02::A500",
        "targetBaseDefinitionId": "project01::JJ00",
    }
    report = {
        "schemaVersion": "calibration-planar-station-candidate-report/v1",
        "candidates": [{
            **pair,
            "status": "planar_candidate_requires_height_decision",
            "interfaceTopology": "three_orthogonal_datum_planes",
            "readyForCadValidation": False,
        }],
    }
    report_path = save("candidates.json", report)
    index = {
        "schemaVersion": "station-candidate-decision-index/v1",
        "entries": [{
            **pair,
            "role": "Calibration",
            "reportPath": "candidates.json",
            "reportSha256": sha(report_path),
            "candidateStatus": "planar_candidate_requires_height_decision",
            "interfaceTopology": "three_orthogonal_datum_planes",
            "readyForCadValidation": False,
        }],
    }
    index_path = save("candidate-index.json", index)
    result = prepare_station_gap_batch(
        tmp_path,
        "coverage.json",
        "registry.json",
        tmp_path / "output",
        candidate_decision_index_path="candidate-index.json",
    )
    assert {"path": str(index_path), "sha256": sha(index_path)} in result["sourceFiles"]

    report["candidates"][0]["status"] = "ready_for_nonprototype_cad_validation"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        prepare_station_gap_batch(
            tmp_path,
            "coverage.json",
            "registry.json",
            tmp_path / "tampered-output",
            candidate_decision_index_path="candidate-index.json",
        )


@pytest.mark.parametrize("status,authority,assets,expected", [
    ("existing_rule_validation_pending", False, [], "cad_validation_pending"),
    ("generated_installation_rule_candidate", False, [], "cad_validation_pending"),
    ("functional_geometry_or_station_binding_required", True, [], "mechanical_interface_authority_missing"),
    ("functional_geometry_or_station_binding_required", False,
     [{"stillRequired": ["service_subtree_labels"]}], "reusable_measurement_needs_semantic_binding"),
    ("functional_geometry_or_station_binding_required", False,
     [{"stillRequired": []}], "reusable_measurement_needs_rule_compilation"),
    ("functional_geometry_or_station_binding_required", False, [], "measurement_or_label_missing"),
])
def test_gap_classification_is_explicit_and_does_not_promote_evidence(status, authority, assets, expected):
    row = {"sourceModuleDefinitionId": "project05::N000", "targetBaseDefinitionId": "project02::A600",
           "status": status, "executionAuthorityMissing": authority, "targetMeasurementAssets": assets}
    assert classify_gap(row)["gapCategory"] == expected
    assert row["pairClass"] == "cross_project_pair"
    assert "validatedStationRule" not in row


def test_transport_work_area_review_precedes_generic_cad_pending():
    row = {
        "sourceModuleDefinitionId": "project01::SS00",
        "targetBaseDefinitionId": "project05::A000",
        "role": "Transport",
        "status": "existing_rule_validation_pending",
        "transportWorkAreaReview": {
            "publicationAllowed": False,
            "blockingReasonCodes": ["WORK_POSITION_CONTEXT_SELECTION_REQUIRED"],
        },
    }
    assert classify_gap(row)["gapCategory"] == (
        "transport_work_area_context_and_policy_required"
    )


def test_revoked_driving_template_requires_new_binding_not_cad_rerun():
    row = {
        "sourceModuleDefinitionId": "project05::G000",
        "targetBaseDefinitionId": "project05::A000",
        "role": "Calibration",
        "status": "existing_rule_validation_pending",
        "executionAuthorityMissing": True,
        "authority": {"ready": False, "status": "released_driving_template_revoked"},
        "targetMeasurementAssets": [],
    }

    assert classify_gap(row)["gapCategory"] == (
        "mechanical_interface_authority_revoked_requires_new_binding"
    )


def test_native_service_postcheck_requires_bound_saved_cad_evidence():
    row = {
        "sourceModuleDefinitionId": "project01::GN00",
        "targetBaseDefinitionId": "project01::JJ00",
        "role": "CleaningWeighing",
        "status": "existing_rule_validation_pending",
        "stationCandidateDecision": {
            "candidateStatus": (
                "native_service_identity_binding_ready_for_station_rule_and_readonly_postcheck"
            )
        },
        "historicalPairEvidence": {},
    }
    assert classify_gap(row)["gapCategory"] == (
        "native_service_nonprototype_cad_validation_required"
    )
    assert row["workClass"] == "cad_validation"


def test_existing_station_rule_prefers_readonly_postcheck_when_exact_cad_exists():
    row = {
        "sourceModuleDefinitionId": "project05::N000",
        "targetBaseDefinitionId": "project01::JJ00",
        "role": "CleaningWeighing",
        "status": "existing_rule_validation_pending",
        "historicalPairEvidence": {
            "cadResultPath": "cad-result.json",
            "effectiveGraphPath": "effective-graph.json",
        },
    }
    assert classify_gap(row)["gapCategory"] == (
        "target_station_postcheck_required_from_existing_saved_output"
    )
    assert row["workClass"] == "saved_output_postcheck_or_candidate_materialization"


def test_real_gn00_release_recovers_pair_only_saved_cad_history():
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    history = _released_pair_cad_history(
        root,
        authority={
            "releaseManifestPath": (
                "demo/global_assembly_catalog/releases/"
                "relation-v65-project01-gn00-base-only-two-hole-driving-20261022/"
                "release-manifest.json"
            ),
            "pairReleaseEvidence": {
                "releaseId": (
                    "relation-v65-project01-gn00-base-only-two-hole-driving-20261022"
                ),
                "releaseDigest": (
                    "e09db96edcff734883fcde87285bfb64e2aace9c431c1da2cde4dc40a939af41"
                ),
            },
        },
        source_module_definition_id="project01::GN00",
        target_base_definition_id="project01::JJ00",
    )
    assert history["evidenceSource"] == "released_manifest_validation_evidence"
    assert history["cadResultPath"].endswith(
        "project01_GN00_base_only_two_hole_checkpoint_v1.result.json"
    )
    assert history["effectiveGraphPath"].endswith(
        "project01_GN00_base_only_two_hole_checkpoint_v1.execution-graph.json"
    )


@pytest.mark.parametrize("requirement", [
    "bind_exact_selected_transport_instance_and_pose_for_each_candidate",
    "confirm_or_explicitly_authorize_beam_role_mapping",
    "resolve_current_context_optical_axis_sign_and_working_distance",
])
def test_scanner_measurement_binding_is_not_misreported_as_ready_to_compile(requirement):
    row = {
        "sourceModuleDefinitionId": "project02::A180",
        "targetBaseDefinitionId": "project05::A000",
        "role": "Scanner",
        "status": "functional_geometry_or_station_binding_required",
        "targetMeasurementAssets": [{"stillRequired": [requirement]}],
    }
    assert classify_gap(row)["gapCategory"] == (
        "reusable_measurement_needs_semantic_binding"
    )


def test_existing_target_function_rule_is_reusable_but_needs_new_source_mapping():
    row = {
        "sourceModuleDefinitionId": "project02::A300",
        "targetBaseDefinitionId": "project01::JJ00",
        "role": "WasteCup",
        "status": "functional_geometry_or_station_binding_required",
        "targetMeasurementAssets": [],
        "reusableTargetConfigs": [{
            "source": "project05::P000",
            "base": "project01::JJ00",
            "role": "WasteCup",
            "kind": "cup_projection",
        }],
    }
    assert classify_gap(row)["gapCategory"] == "wastecup_source_function_mapping_required"


def test_cleaning_native_station_is_not_confused_with_missing_service_binding():
    row = {
        "sourceModuleDefinitionId": "project01::GN00",
        "targetBaseDefinitionId": "project01::JJ00",
        "role": "CleaningWeighing",
        "status": "functional_geometry_or_station_binding_required",
        "targetMeasurementAssets": [{
            "stillRequired": [
                "bind_source_service_subtrees_to_target_service_station",
                "verify_target_capability_coverage",
            ],
        }],
    }
    assert classify_gap(row)["gapCategory"] == (
        "cleaning_service_semantic_binding_required"
    )


def test_incomplete_service_capability_precedes_cad_or_measurement_classification():
    row = {
        "sourceModuleDefinitionId": "project01::GN00",
        "targetBaseDefinitionId": "project05::A000",
        "status": "existing_rule_validation_pending",
        "executionAuthorityMissing": False,
        "targetMeasurementAssets": [{"stillRequired": []}],
        "serviceCapabilityCoverage": {
            "passed": False,
            "missingCapabilities": ["weighing", "waste_collection"],
        },
    }
    assert classify_gap(row)["gapCategory"] == "target_service_capability_incomplete"


def test_service_capability_near_match_is_an_explicit_semantic_decision_not_coverage():
    row = {
        "sourceModuleDefinitionId": "project01::GN00",
        "targetBaseDefinitionId": "project05::A000",
        "status": "existing_rule_validation_pending",
        "executionAuthorityMissing": False,
        "serviceCapabilityCoverage": {
            "passed": False,
            "missingCapabilities": ["inspection"],
            "nearMatchRequiredCapabilities": ["inspection"],
        },
    }
    classified = classify_gap(row)
    assert classified["gapCategory"] == (
        "target_service_capability_semantic_mapping_decision_required"
    )
    assert classified["workClass"] == "engineering_decision"


@pytest.mark.parametrize(
    "category,expected",
    [
        ("cad_validation_pending", "cad_validation"),
        (
            "target_station_postcheck_required_from_existing_saved_output",
            "saved_output_postcheck_or_candidate_materialization",
        ),
        (
            "scanner_exact_point_pair_candidate_requires_current_context",
            "current_context_chain_and_postcheck",
        ),
        (
            "scanner_independent_point_pair_or_measurement_required",
            "measurement_or_role_selection",
        ),
        (
            "scanner_role_selection_from_candidate_catalog_required",
            "engineering_decision",
        ),
        (
            "mechanical_interface_authority_revoked_requires_new_binding",
            "mechanical_binding",
        ),
        ("target_functional_geometry_mismatch", "engineering_decision"),
        (
            "reusable_measurement_needs_semantic_binding",
            "reusable_data_rule_derivation",
        ),
    ],
)
def test_gap_work_class_is_an_actionable_layer_above_precise_reason(category, expected):
    assert _work_class(category) == expected


def test_failed_functional_geometry_screen_precedes_reusable_measurement():
    row = {
        "sourceModuleDefinitionId": "project02::A300",
        "targetBaseDefinitionId": "project05::A000",
        "status": "functional_geometry_or_station_binding_required",
        "executionAuthorityMissing": False,
        "targetMeasurementAssets": [{"stillRequired": []}],
        "functionalGeometryScreening": {
            "passed": False,
            "status": "published_orientation_cannot_reach_target_by_translation",
        },
    }
    assert classify_gap(row)["gapCategory"] == "target_functional_geometry_mismatch"


@pytest.mark.parametrize(
    "candidate_status,expected",
    [
        (
            "planar_candidate_requires_height_decision",
            "target_function_point_height_decision_required",
        ),
        (
            "two_axis_stations_miss_target_function_point",
            "target_functional_geometry_mismatch",
        ),
        (
            "flexible_slot_candidate_requires_height_and_axis_review",
            "target_function_point_height_and_interface_review_required",
        ),
        (
            "ready_for_nonprototype_cad_validation",
            "station_candidate_ready_for_cad_validation",
        ),
        (
            "recommendation_pending_engineering_confirmation",
            "target_station_engineering_confirmation_required",
        ),
        (
            "engineering_confirmation_recorded_requires_target_station_postcheck",
            "nonprototype_cad_validation_required_after_confirmation",
        ),
        (
            "native_station_requires_current_saved_output_station_postcheck",
            "native_transport_station_nonprototype_cad_validation_required",
        ),
        (
            "ready_for_exact_chain_instance_selection",
            "scanner_exact_chain_instance_binding_required",
        ),
        (
            "exact_saved_context_available_requires_geometry_evaluation",
            "scanner_saved_context_geometry_evaluation_required",
        ),
        (
            "new_cumulative_chain_context_required",
            "scanner_new_cumulative_chain_context_required",
        ),
        (
            "current_context_point_pair_geometry_mismatch",
            "target_functional_geometry_mismatch",
        ),
        (
            "current_context_proxy_passed_requires_station_registration",
            "station_candidate_ready_for_cad_validation",
        ),
        (
            "wastecup_mapping_selected_requires_saved_base_pose_and_station_candidate",
            "wastecup_mapping_selected_requires_station_candidate",
        ),
        (
            "native_service_identity_binding_ready_for_station_rule_and_readonly_postcheck",
            "native_service_nonprototype_cad_validation_required",
        ),
    ],
)
def test_authenticated_candidate_decision_refines_old_pose_mismatch(
    candidate_status, expected
):
    row = {
        "sourceModuleDefinitionId": "project02::A500",
        "targetBaseDefinitionId": "project01::JJ00",
        "role": "Calibration",
        "status": "functional_geometry_or_station_binding_required",
        "targetMeasurementAssets": [],
        "functionalGeometryScreening": {"passed": False},
        "stationCandidateDecision": {"candidateStatus": candidate_status},
    }
    assert classify_gap(row)["gapCategory"] == expected


def test_native_pair_classification_uses_project_identity_not_role():
    row = {"sourceModuleDefinitionId": "project05::N000", "targetBaseDefinitionId": "project05::A000",
           "status": "functional_geometry_or_station_binding_required", "targetMeasurementAssets": []}
    assert classify_gap(row)["pairClass"] == "native_pair"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            "exact_point_pair_candidate_available",
            "scanner_exact_point_pair_candidate_requires_current_context",
        ),
        (
            "composition_candidate_ready",
            "scanner_composed_rule_candidate_requires_current_context",
        ),
        (
            "independent_point_pair_or_measurement_required",
            "scanner_independent_point_pair_or_measurement_required",
        ),
    ],
)
def test_scanner_rule_readiness_refines_generic_context_gap(status, expected):
    row = {
        "sourceModuleDefinitionId": "project02::A180",
        "targetBaseDefinitionId": "project01::JJ00",
        "role": "Scanner",
        "status": "existing_rule_validation_pending",
        "targetMeasurementAssets": [],
        "stationCandidateDecision": {
            "candidateStatus": "new_cumulative_chain_context_required"
        },
        "scannerRuleReadiness": {
            "status": status,
            "transportModuleDefinitionId": "project01::SS00",
        },
    }
    assert classify_gap(row)["gapCategory"] == expected


def test_scanner_finite_candidate_selection_is_not_reported_as_missing_measurement():
    row = {
        "sourceModuleDefinitionId": "project05::F000",
        "targetBaseDefinitionId": "project05::A000",
        "role": "Scanner",
        "status": "existing_rule_validation_pending",
        "targetMeasurementAssets": [],
        "scannerRuleReadiness": {
            "status": "independent_point_pair_or_measurement_required",
            "transportModuleDefinitionId": "project05::D000",
            "sourceOpticalCandidateAvailable": True,
            "transportBarcodeTargetCandidateAvailable": True,
            "requiredNextEvidence": [
                "source_scanner_head_role_and_direction_selection_from_candidate_catalog",
                "transport_barcode_target_role_selection_from_candidate_catalog",
            ],
        },
    }
    classified = classify_gap(row)
    assert classified["gapCategory"] == (
        "scanner_role_selection_from_candidate_catalog_required"
    )
    assert classified["workClass"] == "engineering_decision"

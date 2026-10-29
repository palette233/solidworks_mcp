"""Offline/mock-authority tests; none of these tests launch SolidWorks."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from demo_backend import six_role_station_coverage as mod


WORKSPACE = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def inputs():
    return read(WORKSPACE/mod.SCOPE_PATH), read(WORKSPACE/mod.GLOBAL_PATH)


def rule(**updates):
    value = {"ruleId": "test-gn00-aa00", "sourceModuleDefinitionId": "project01::GN00",
             "targetBaseDefinitionId": "project03::AA00", "role": "CleaningWeighing",
             "placement": {"strategy": "target_role_region"}, "evidence": [],
             "validation": {"status": "candidate", "profile": "declared_demo_geometry"}}
    value.update(updates)
    return value


def pair(report, source="project01::GN00", target="project03::AA00"):
    return next(r for r in report["pairs"] if (r["sourceModuleDefinitionId"], r["targetBaseDefinitionId"]) == (source, target))


def test_frozen_scope_is_21_current_modules_and_68_pairs():
    scope, catalog = inputs()
    identities = mod.validate_scope(scope, catalog)
    assert len(identities) == 21
    assert scope["expectedCounts"] == {"baseCount": 4, "movingModuleCount": 17, "exactPairCount": 68}
    assert {r["role"] for r in scope["movingModules"]} == {"Transport", "Scanner", "Calibration", "CleaningWeighing", "WasteCup"}
    assert all("project06" not in key and "A700" not in key for key in identities)


@pytest.mark.parametrize("mutation", ["duplicate", "canonical", "empty", "project", "role", "count", "base_role"])
def test_scope_rejects_identity_or_count_drift(mutation):
    scope, catalog = inputs()
    if mutation == "duplicate": scope["movingModules"].append(deepcopy(scope["movingModules"][0]))
    if mutation == "canonical": scope["movingModules"][0]["cadModuleDefinitionId"] = "cad/changed"
    if mutation == "empty": scope["movingModules"][0]["cadModuleDefinitionId"] = ""
    if mutation == "project": scope["projects"].remove("project01")
    if mutation == "role": scope["movingModules"][0]["role"] = "CCD"
    if mutation == "count": scope["expectedCounts"]["exactPairCount"] = 67
    if mutation == "base_role": scope["bases"][0]["role"] = "Transport"
    with pytest.raises(ValueError): mod.validate_scope(scope, catalog)


def test_68_mock_interface_releases_never_imply_68_validated_stations():
    scope, _ = inputs()
    authorities = {(m["moduleDefinitionId"], b["moduleDefinitionId"]): [
        {"currentAuthorityAvailable": True, "authenticated": True, "runtimeRevoked": False}]
        for m in scope["movingModules"] for b in scope["bases"]}
    report = mod.build_six_role_station_coverage(WORKSPACE, interface_authorities=authorities)
    assert report["summary"]["executableCurrentAuthorityPairCount"] == 68
    assert report["summary"]["validatedStationRulePairCount"] == 0
    assert report["summary"]["crossProjectPairCount"] == 51
    assert report["summary"]["missingDataPairCount"] == 68
    assert report["cadExecuted"] is False
    assert report["cadLaunchAllowed"] is False
    assert report["authorityAudit"]["injectedForTesting"] is True
    assert "68" in mod.render_station_coverage_markdown(report)


@pytest.mark.parametrize("status", ["candidate", "experimental_cad_verified", "released_demo"])
def test_validation_status_alone_never_proves_station(status):
    report = mod.build_six_role_station_coverage(WORKSPACE,
        station_rules=[rule(validation={"status": status})], interface_authorities={})
    result = pair(report)
    assert result["configuredStationRule"] is True
    assert result["validatedStationRule"] is False
    assert result["experimentalEvidenceOnly"] is False
    assert result["executableCurrentAuthority"] is False
    assert result["stationRules"][0]["ruleDigest"]


def test_validator_evidence_is_separate_from_interface_authority(tmp_path):
    evidence = tmp_path/"measured.json"
    evidence.write_text('{"actual": true}', encoding="utf-8")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    def validator(workspace, station_rule, scope):
        assert workspace == WORKSPACE
        assert station_rule["ruleId"] == "test-gn00-aa00"
        return {"configuredStationRule": True, "validatedStationRule": True,
                "experimentalEvidenceOnly": True, "blockingReasonCodes": [],
                "evidence": [{"path": str(evidence), "sha256": digest}]}
    report = mod.build_six_role_station_coverage(WORKSPACE, station_rules=[rule()],
        station_rule_validator=validator, interface_authorities={})
    result = pair(report)
    assert result["validatedStationRule"] is True
    assert result["experimentalEvidenceOnly"] is True
    assert result["executableCurrentAuthority"] is False
    assert str(evidence) in {r["path"] for r in report["sources"]}


def test_tampered_validator_evidence_is_rejected(tmp_path):
    evidence = tmp_path/"measured.json"
    evidence.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed during coverage"):
        mod.build_six_role_station_coverage(WORKSPACE, station_rules=[rule()], interface_authorities={},
            station_rule_validator=lambda *_: {"configuredStationRule": True, "validatedStationRule": True,
                "evidence": [{"path": str(evidence), "sha256": "0"*64}]})


@pytest.mark.parametrize("kwargs", [{"ruleId": ""}, {"role": "WasteCup"},
    {"sourceModuleDefinitionId": "project06::N000"}, {"targetBaseDefinitionId": "project03::AE00"}])
def test_bad_rule_binding_rejected(kwargs):
    with pytest.raises(ValueError):
        mod.build_six_role_station_coverage(WORKSPACE, station_rules=[rule(**kwargs)], interface_authorities={})


def test_duplicate_rule_id_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        mod.build_six_role_station_coverage(WORKSPACE, station_rules=[rule(), rule()], interface_authorities={})


def test_incomplete_rule_and_canonical_identity():
    scope, _ = inputs()
    canonical = next(r["cadModuleDefinitionId"] for r in scope["movingModules"] if r["moduleDefinitionId"] == "project01::GN00")
    report = mod.build_six_role_station_coverage(WORKSPACE,
        station_rules=[rule(sourceModuleDefinitionId=canonical, placement={})], interface_authorities={})
    assert pair(report)["configuredStationRule"] is False


@pytest.mark.parametrize("field,value", [("authenticated", False), ("runtimeRevoked", True), ("currentAuthorityAvailable", False)])
def test_invalid_or_revoked_interface_cannot_be_counted(field, value):
    release = {"currentAuthorityAvailable": True, "authenticated": True, "runtimeRevoked": False}
    release[field] = value
    report = mod.build_six_role_station_coverage(WORKSPACE,
        interface_authorities={("project01::GN00", "project03::AA00"): [release]})
    assert pair(report)["executableCurrentAuthority"] is False


def test_one_run_source_reader_cache_and_hash(tmp_path):
    path = tmp_path/"a.json"
    path.write_text('{"x": 1}', encoding="utf-8")
    reader = mod.SourceReader(tmp_path)
    assert reader.read("a.json") == {"x": 1}
    assert reader.bind(path)["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(reader.sources) == 1


def load_script():
    spec = importlib.util.spec_from_file_location("scope_report_script", WORKSPACE/"scripts/build_six_role_station_coverage.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_cli_never_overwrites_existing_report(tmp_path):
    output = tmp_path/"report"
    output.mkdir()
    with pytest.raises(FileExistsError, match="Refusing"):
        load_script().main(["--output", str(output)])


def test_cli_records_rule_file_digest_without_real_authority_or_cad(tmp_path, monkeypatch):
    script = load_script()
    source = tmp_path/"rules.json"
    source.write_text(json.dumps([rule()]), encoding="utf-8")
    output = tmp_path/"report"
    calls = []
    def offline_builder(workspace, **kwargs):
        calls.append(kwargs)
        assert callable(kwargs["station_rule_validator"])
        return mod.build_six_role_station_coverage(WORKSPACE, interface_authorities={})
    monkeypatch.setattr(script, "build_six_role_station_coverage", offline_builder)
    assert script.main(["--station-rules", str(source), "--output", str(output)]) == 0
    report = read(output/"coverage.json")
    assert calls[0]["station_rules"] == [rule()]
    assert next(r for r in report["sources"] if r["path"] == str(source))["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (output/"coverage-gaps-CN.md").is_file()
    assert report["cadExecuted"] is False


@pytest.mark.parametrize("revoked,template_blocked,pair_blocked,authenticated,exact", [
    (False, False, False, True, True), (True, False, False, True, True),
    (False, True, False, True, True), (False, False, True, True, True),
    (False, False, False, False, True), (False, False, False, True, False)])
def test_discovery_rechecks_runtime_and_exact_binding(tmp_path, monkeypatch, revoked, template_blocked, pair_blocked, authenticated, exact):
    """Mock catalog/auth validator: exercises discovery, not real CAD evidence."""
    scope = {"bases": [{"moduleDefinitionId": "p::base"}], "movingModules": [{"moduleDefinitionId": "q::move"}]}
    identities = {"p::base": {"moduleDefinitionId": "cad/base"}, "q::move": {"moduleDefinitionId": "cad/move"}}
    monkeypatch.setattr(mod, "validate_scope", lambda *_: identities)
    monkeypatch.setattr(mod, "validate_relation_driving_safety_registry", lambda *_: None)
    monkeypatch.setattr(mod, "validate_contract_catalog", lambda *_: None)
    monkeypatch.setattr(mod, "CONTRACT_FOLDERS", ())
    manifest_path = tmp_path/"demo/global_assembly_catalog/releases/release/release-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest = {"releaseId": "r1", "status": "released_for_demo_relation_execution",
        "releasedCatalogRelativePath": "released.json", "scope": {"authorizedDrivingTemplateIds": ["t1"]},
        "releaseMetadata": {"directInterfacePairBinding": {"moduleDefinitionId": "q::move", "slotDefinitionId": "p::base"}} if exact else {}}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    files = {mod.GLOBAL_PATH: {}, mod.DRIVING_SAFETY_PATH: {"templates": [
        {"globalTemplateId": "t1", "status": mod.BLOCKED_STATUS}] if template_blocked else []},
        mod.DATUM_SAFETY_PATH: {"schemaVersion": "parameterized-datum-release-safety-registry/v1", "revokedReleases": [
            {"releaseId": "r1" if revoked else "old", "moduleDefinitionId": "q::move", "slotDefinitionId": "p::base", "blockCandidateReuse": pair_blocked}]},
        "released.json": {"semanticPorts": [{"globalPortId": "a", "moduleDefinitionId": "cad/base"},
            {"globalPortId": "b", "moduleDefinitionId": "cad/move"}],
            "connectionTemplates": [{"globalTemplateId": "t1", "candidatePortIdsA": ["a"], "candidatePortIdsB": ["b"]}]}}
    for name, content in files.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding="utf-8")
    calls = []
    def existing_validator(*args, **kwargs):
        calls.append(args)
        if not authenticated: raise ValueError("Current release digest failed")
        return {}, manifest
    monkeypatch.setattr(mod, "load_relation_catalog_release", existing_validator)
    reader = mod.SourceReader(tmp_path)
    authorities, _ = mod.load_current_interface_authorities(tmp_path, scope, reader=reader)
    result = authorities[("q::move", "p::base")][0]
    assert result["currentAuthorityAvailable"] is (authenticated and exact and not(revoked or template_blocked or pair_blocked))
    assert result["authenticated"] is authenticated
    assert len(calls) == 1
    assert (tmp_path/mod.DATUM_SAFETY_PATH).resolve() in reader.sources

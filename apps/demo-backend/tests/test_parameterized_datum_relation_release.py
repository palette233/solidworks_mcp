from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from demo_backend.global_assembly_compiler import compile_global_assembly_execution_manifest
from demo_backend.global_assembly_context import (
    apply_global_command_preview, create_global_assembly_context, preview_global_assembly_command,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError, match_interface_contracts
from demo_backend.parameterized_datum_placement import (
    compile_parameterized_datum_validation_package, load_parameterized_datum_placement_catalog,
)
from demo_backend.parameterized_datum_relation_release import build_parameterized_datum_catalog_package
import demo_backend.parameterized_datum_relation_release as bridge
import demo_backend.global_relation_catalog_release as releases


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "demo/cross_project_substitution/expanded-project03-v1/relation-v62-project03-expanded-cross-project-chain-driving-20261014.catalog-preview.json"
VALIDATION_ROOT = ROOT / "demo/cross_project_substitution/parameterized-datum-placement-v1"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build(pair="gn00-aa00"):
    release = f"relation-{pair}-parameterized-datum-20261024-v1"
    directory = f"demo/global_assembly_catalog/releases/{release}/semantic-package"
    return build_parameterized_datum_catalog_package(
        base_global_catalog=_read(BASE), validation_dir=VALIDATION_ROOT / f"validation-{pair}-v1",
        semantic_catalog_path=f"{directory}/semantic_port_catalog.json",
        endpoint_catalog_path=f"{directory}/face_endpoint_catalog.json",
        base_graph_path=f"{directory}/base_parameterized_datum_graph.json",
    )


@pytest.mark.parametrize("pair", ["gn00-aa00", "ai00-jj00"])
def test_verified_pair_adapts_to_standard_catalog_without_anchor_or_extra_claim(pair):
    before = _read(BASE)
    package = _build(pair)
    assert _read(BASE) == before
    assert len(package["semanticCatalog"]["ports"]) == 2
    assert package["boundary"]["actualFixationMethod"] == "not_verified"
    assert package["boundary"]["directMechanicalCompatibilityClaim"] is False
    graph = package["baseGraph"]
    assert not graph["TargetLeafPoseAnchors"]
    assert graph["CaseAnchor"] is None
    assert graph["EditPolicy"]["fixedModuleTokens"] == [pair.split("-")[1].upper()]
    target = next(row for row in graph["Modules"] if row["ModuleToken"] == pair.split("-")[0].upper())
    assert target["SourceTransform"][9:12] == [0, 0, 0]


@pytest.mark.parametrize("pair", ["gn00-aa00", "ai00-jj00"])
def test_existing_compiler_accepts_explicit_datum_and_blocks_implicit_fallback(pair):
    package = _build(pair)
    catalog = package["candidateGlobalCatalog"]
    context = create_global_assembly_context("datum-bridge-regression", catalog_digest=catalog["catalogDigest"])
    base = preview_global_assembly_command(catalog, context, {
        "requirement": "请先建立设备基座", "moduleDefinitionId": package["globalSlotDefinitionId"]})
    assert base["status"] == "ready"
    context = apply_global_command_preview(context, base, preview_digest=base["previewDigest"], confirmed=True)
    command = {"requirement": "安装清洁称重模组" if pair == "gn00-aa00" else "安装条码扫描模组",
               "moduleDefinitionId": package["globalModuleDefinitionId"],
               "globalTemplateId": package["globalTemplateId"]}
    blocked = preview_global_assembly_command(catalog, context, command)
    assert blocked["status"] == "blocked"
    ready = preview_global_assembly_command(catalog, context, {**command, "relationExecutionMode": "datum_placement_demo"})
    assert ready["status"] == "ready", ready
    context = apply_global_command_preview(context, ready, preview_digest=ready["previewDigest"], confirmed=True)
    manifest = compile_global_assembly_execution_manifest(ROOT, catalog, context)
    assert manifest["status"] == "ready_for_project_adapter", manifest
    assert manifest["stepCount"] == 1


def test_parameter_edit_creates_unreleased_contract_and_preserves_default():
    original = compile_parameterized_datum_validation_package(ROOT, "project01::GN00", "project03::AA00")
    edited = compile_parameterized_datum_validation_package(ROOT, "project01::GN00", "project03::AA00",
        position_parameters={"longitudinal": .364, "lateral": .2535, "supportGap": 0})
    assert edited["readyForReleasedCadExecution"] is False
    assert edited["validationRequiredBeforeRelease"] is True
    assert edited["positionParametersOverride"]["longitudinal"] == .364
    assert edited["instantiatedTemplate"]["slotContractId"] != original["instantiatedTemplate"]["slotContractId"]
    assert edited["instantiatedTemplate"]["templateId"] != original["instantiatedTemplate"]["templateId"]
    assert edited["effectiveGraph"]["Mates"][0]["Distance"] == .364
    assert original["effectiveGraph"]["Mates"][0]["Distance"] == .354


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, "0.364"])
def test_parameter_override_rejects_nonphysical_numbers(value):
    with pytest.raises(MechanicalInterfaceContractError, match="finite nonnegative"):
        compile_parameterized_datum_validation_package(ROOT, "project01::GN00", "project03::AA00",
            position_parameters={"longitudinal": value, "lateral": .2535, "supportGap": 0})


def test_old_pair_release_cannot_authorize_changed_contract():
    report = load_parameterized_datum_placement_catalog(ROOT)
    evidence = next(row for row in report["releasedPairEvidence"] if row["moduleDefinitionId"] == "project01::GN00")
    module = next(
        row for row in report["contracts"]
        if row.get("side") == "moving_module"
        and row.get("moduleDefinitionId") == evidence["moduleDefinitionId"]
    )
    slot = copy.deepcopy(next(
        row for row in report["contracts"]
        if row.get("side") == "base_slot"
        and row.get("moduleDefinitionId") == evidence["slotDefinitionId"]
        and module.get("moduleRole") in (row.get("acceptedModuleRoles") or [])
    ))
    stale = copy.deepcopy(evidence)
    stale["catalogResolution"]["currentCatalogBindingsMatch"] = False
    slot["contractId"] = "interface-contract/modified-parameter-version"
    match = match_interface_contracts(module, slot, pair_release_evidence=stale)
    assert match["compatible"] is True
    assert match["existingPairReleaseReusable"] is False
    assert match["requiresNewPairCadValidation"] is True


@pytest.mark.parametrize("change", ["distance", "fixed_target", "endpoint_hash", "pair_digest"])
def test_bridge_rejects_stale_parameters_anchors_or_endpoint_evidence(monkeypatch, change):
    read = bridge._read
    def altered(path):
        value = copy.deepcopy(read(path))
        if change == "distance" and path.name == "validation-package.json":
            value["instantiatedTemplate"]["mateSteps"][0]["distanceMeters"] = .364
        if change == "fixed_target" and path.name == "effective-mate-graph.json":
            value["EditPolicy"]["fixedModuleTokens"].append("GN00")
        if change == "endpoint_hash" and path.name == "validation-package.json":
            value["artifacts"]["selectedEndpointCatalog"]["sha256"] = "0" * 64
        if change == "pair_digest" and path.name == "pair-release.json":
            value["releaseDigest"] = "0" * 64
        return value
    monkeypatch.setattr(bridge, "_read", altered)
    with pytest.raises(MechanicalInterfaceContractError):
        _build()


@pytest.mark.parametrize("path_key", ["effectiveGraphPath", "cadResultPath", "outputAssemblyPath"])
def test_relation_release_loader_rechecks_actual_pair_evidence(monkeypatch, path_key):
    path = ROOT / "demo/global_assembly_catalog/releases/relation-gn00-aa00-parameterized-datum-20261024-v1/release-manifest.json"
    manifest = _read(path)
    target = Path(manifest["releaseMetadata"]["parameterizedDatumPairBinding"][path_key]).resolve()
    original_sha = releases._file_sha256
    monkeypatch.setattr(releases, "_file_sha256", lambda evidence: "0" * 64 if evidence.resolve() == target else original_sha(evidence))
    with pytest.raises(releases.GlobalRelationCatalogReleaseError, match="参数化定位证据缺失或已变化"):
        releases.load_relation_catalog_release(path, workspace_root=ROOT)

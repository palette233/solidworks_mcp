"""The generic context gate accepts datum evidence only in explicit Demo mode."""

import json
from pathlib import Path
import shutil
import tempfile

import pytest

from demo_backend import global_interface_contract_planner as planner
from demo_backend import global_natural_language_manifest as nl_manifest
from demo_backend import parameterized_datum_placement as placement
from demo_backend.hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError


ROOT = Path(__file__).resolve().parents[3]


def _cad_id(alias: str) -> str:
    project, token = alias.split("::")
    catalog = json.loads(
        (ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json").read_text(
            encoding="utf-8-sig"
        )
    )
    return next(
        row["moduleDefinitionId"]
        for row in catalog["moduleDefinitions"]
        if {"projectId": project, "moduleToken": token} in row.get("projectAliases", [])
        or any(
            item.get("projectId") == project and item.get("moduleToken") == token
            for item in row.get("projectAliases", [])
        )
    )


def _context(base: str, *modules: str) -> dict:
    return {
        "contextId": "synthetic-explicit-datum-context",
        "instances": [
            {"instanceId": "base", "moduleDefinitionId": _cad_id(base)},
            *[
                {"instanceId": str(i), "moduleDefinitionId": _cad_id(module)}
                for i, module in enumerate(modules)
            ],
        ],
        "connections": [
            {"connectionId": f"edge-{i}", "instanceAId": "base", "instanceBId": str(i)}
            for i, _ in enumerate(modules)
        ],
    }


@pytest.mark.parametrize(
    "module,base",
    [("project03::AI00", "project01::JJ00"), ("project01::GN00", "project03::AA00")],
)
def test_preferred_planner_bridges_actual_cad_ids_for_released_datum_pairs(module, base):
    result = planner.plan_preferred_interface_connection(
        ROOT, _cad_id(module), selected_slot_definition_id=_cad_id(base)
    )
    assert result["status"] == "released_datum_placement_ready"
    assert result["selectedMode"] == "parameterized_datum_placement"
    assert result["readyForReleasedCadExecution"] is True
    assert result["datumFallbackPlan"]["moduleDefinitionId"] == module
    assert result["datumFallbackPlan"]["selectedSlotDefinitionId"] == base


def test_released_authority_resolves_native_pair_to_immutable_manifest():
    result = planner.resolve_preferred_released_interface_authority(
        ROOT,
        _cad_id("project01::SS00"),
        selected_slot_definition_id=_cad_id("project03::AA00"),
    )
    assert result["ready"] is True
    assert result["selectedMode"] == "mechanical_interface"
    assert result["relationExecutionMode"] == "direct_installation"
    assert result["releaseManifestPath"].endswith(
        "relation-v46-project03-aa00-project01-ss00-transport-driving-20261012/release-manifest.json"
    )


def test_released_authority_keeps_datum_fallback_explicit():
    module = _cad_id("project01::GN00")
    base = _cad_id("project03::AA00")
    blocked = planner.resolve_preferred_released_interface_authority(
        ROOT, module, selected_slot_definition_id=base
    )
    assert blocked["ready"] is False
    assert blocked["status"] == "native_interface_unavailable_datum_fallback_disabled"
    released = planner.resolve_preferred_released_interface_authority(
        ROOT,
        module,
        selected_slot_definition_id=base,
        allow_datum_fallback=True,
    )
    assert released["ready"] is True
    assert released["relationExecutionMode"] == "datum_placement_demo"
    assert released["releaseManifestPath"].endswith(
        "relation-gn00-aa00-parameterized-datum-20261024-v1/release-manifest.json"
    )


def test_released_f000_hybrid_pair_becomes_natural_language_authority(
    monkeypatch,
):
    existing = placement._validated_pair_releases(ROOT)
    hybrid = build_f000_hybrid_axis_slot_catalog(ROOT)
    slot = next(
        row
        for row in hybrid["baseSlots"]
        if row["slotDefinitionId"] == "project03::AA00"
    )
    evidence = {
        "schemaVersion": "parameterized-datum-pair-release/v1",
        "releaseId": "synthetic-hybrid-f000-aa00-authority-test",
        "releaseDigest": "b" * 64,
        "moduleDefinitionId": "project05::F000",
        "slotDefinitionId": "project03::AA00",
        "placementMode": "reviewed_hybrid_plane_axis_datum",
        "selectedAxisEndpointId": slot["axisCandidates"][0]["endpointId"],
        "nonPrototypeCadValidated": True,
    }
    monkeypatch.setattr(
        placement,
        "_validated_pair_releases",
        lambda _: [*existing, evidence],
    )
    report = placement.build_parameterized_datum_placement_catalog(ROOT)
    monkeypatch.setattr(
        placement, "load_parameterized_datum_placement_catalog", lambda _: report
    )
    monkeypatch.setattr(
        planner, "load_parameterized_datum_placement_catalog", lambda _: report
    )
    preferred = planner.plan_preferred_interface_connection(
        ROOT,
        "project05::F000",
        selected_slot_definition_id="project03::AA00",
        allow_datum_fallback=True,
    )
    assert preferred["status"] == "released_hybrid_pair_ready"
    assert preferred["selectedMode"] == "parameterized_datum_placement"
    assert preferred["readyForReleasedCadExecution"] is True

    release_root = ROOT / "demo/global_assembly_catalog/releases"
    temporary = Path(
        tempfile.mkdtemp(prefix=".tmp-f000-hybrid-authority-", dir=release_root)
    )
    try:
        manifest = {
            "releaseId": "synthetic-f000-hybrid-relation-authority",
            "releaseDigest": "c" * 64,
            "releaseMetadata": {"parameterizedDatumPairBinding": evidence},
        }
        (temporary / "release-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # This unit test supplies synthetic release discovery data. Authenticate
        # through an explicit test double, not a production loader bypass.
        monkeypatch.setattr(
            planner, "load_relation_catalog_release",
            lambda *args, **kwargs: ({
                "semanticPorts": [
                    {"globalPortId": "source", "moduleDefinitionId": _cad_id("project05::F000")},
                    {"globalPortId": "base", "moduleDefinitionId": _cad_id("project03::AA00")},
                ],
                "connectionTemplates": [{"globalTemplateId": "test-template",
                    "candidatePortIdsA": ["source"], "candidatePortIdsB": ["base"]}],
            }, {**manifest, "scope": {"authorizedDrivingTemplateIds": ["test-template"]}}),
        )
        authority = planner.resolve_preferred_released_interface_authority(
            ROOT,
            "project05::F000",
            selected_slot_definition_id="project03::AA00",
            allow_datum_fallback=True,
        )
        assert authority["ready"] is True
        assert authority["selectedMode"] == "parameterized_datum_placement"
        assert authority["relationExecutionMode"] == "datum_placement_demo"
        assert authority["pairReleaseEvidence"] == evidence
        assert authority["releaseManifestPath"].endswith(
            temporary.name + "/release-manifest.json"
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def test_native_pair_without_exact_driving_authority_is_not_ready(monkeypatch):
    old = json.loads((ROOT / "demo/global_assembly_catalog/releases/relation-v9-project01-driving-independent-20261011/release-manifest.json").read_text(encoding="utf-8-sig"))
    monkeypatch.setattr(planner, "plan_preferred_interface_connection", lambda *a, **k: {
        "selectedMode": "mechanical_interface", "readyForReleasedCadExecution": True,
        "nativePlan": {"selectedMatch": {"pairReleaseEvidence": {
            "releaseId": old["releaseId"], "releaseDigest": old["releaseDigest"]}}},
    })
    result = planner.resolve_preferred_released_interface_authority(
        ROOT, _cad_id("project01::BD00"),
        selected_slot_definition_id=_cad_id("project01::JJ00"),
    )
    assert result["ready"] is False
    assert result["status"] == "released_pair_driving_template_missing"


def test_revoked_g000_release_is_not_returned_as_current_cad_authority():
    result = planner.resolve_preferred_released_interface_authority(
        ROOT,
        _cad_id("project05::G000"),
        selected_slot_definition_id=_cad_id("project05::A000"),
    )

    assert result["ready"] is False
    assert result["status"] == "released_driving_template_revoked"
    assert result["safetyBlockers"][0]["code"] == (
        "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
    )


@pytest.mark.parametrize("authorized,other_base", [(False, False), (True, True)])
def test_authority_requires_authorized_template_for_exact_pair(monkeypatch, authorized, other_base):
    original = planner.load_relation_catalog_release

    def altered(path, **kwargs):
        catalog, manifest = original(path, **kwargs)
        template = "test-template"
        catalog = {"semanticPorts": [
            {"globalPortId": "source", "moduleDefinitionId": _cad_id("project01::SS00")},
            {"globalPortId": "base", "moduleDefinitionId": _cad_id(
                "project01::JJ00" if other_base else "project03::AA00")},
        ], "connectionTemplates": [{"globalTemplateId": template,
            "candidatePortIdsA": ["source"], "candidatePortIdsB": ["base"]}]}
        return catalog, {**manifest, "scope": {
            "authorizedDrivingTemplateIds": [template] if authorized else []}}

    monkeypatch.setattr(planner, "load_relation_catalog_release", altered)
    result = planner.resolve_preferred_released_interface_authority(
        ROOT, _cad_id("project01::SS00"),
        selected_slot_definition_id=_cad_id("project03::AA00"),
    )
    assert result["ready"] is False
    assert result["status"] == "released_pair_driving_template_missing"


@pytest.mark.parametrize(
    "module,base",
    [("project03::AI00", "project01::JJ00"), ("project01::GN00", "project03::AA00")],
)
def test_context_does_not_silently_turn_native_incompatibility_into_datum(module, base):
    context = _context(base, module)
    direct = planner.assess_global_assembly_context_interfaces(ROOT, context)
    explicit = planner.assess_global_assembly_context_interfaces(
        ROOT, context, relation_execution_mode="datum_placement_demo"
    )
    assert direct["status"] == "blocked"
    assert direct["connections"][0]["status"] == "mechanically_incompatible"
    assert explicit["status"] == "ready"
    assert explicit["connections"][0]["status"] == "released_datum_placement_ready"
    assert explicit["cadStarted"] is False


def test_mixed_context_preserves_native_edges_and_both_types_of_datum_release():
    context = _context(
        "project03::AA00", "project03::AI00", "project01::GN00", "project05::P000"
    )
    result = planner.assess_global_assembly_context_interfaces(
        ROOT, context, relation_execution_mode="datum_placement_demo"
    )
    assert result["status"] == "ready"
    assert result["readyConnectionCount"] == 3
    assert [row["selectedMode"] for row in result["connections"]] == [
        "mechanical_interface", "parameterized_datum_placement", "parameterized_datum_placement"
    ]
    assert result["connections"][0]["catalogKey"] == "scanner"


def test_legacy_wastecup_support_recipe_requires_explicit_mode():
    context = _context("project03::AA00", "project05::P000")
    result = planner.assess_global_assembly_context_interfaces(ROOT, context)
    assert result["status"] == "blocked"
    assert result["connections"][0]["status"] == "explicit_datum_mode_required"
    disabled = planner.plan_preferred_interface_connection(
        ROOT, "project05::P000", selected_slot_definition_id="project03::AA00",
        allow_datum_fallback=False,
    )
    assert disabled["readyForReleasedCadExecution"] is False
    native = planner.plan_preferred_interface_connection(
        ROOT, "project05::P000", selected_slot_definition_id="project05::A000",
        allow_datum_fallback=True,
    )
    assert native["selectedMode"] == "mechanical_interface"


def test_newly_released_n000_jj00_pair_passes_explicit_datum_preflight():
    result = planner.assess_global_assembly_context_interfaces(
        ROOT, _context("project01::JJ00", "project05::N000"),
        relation_execution_mode="datum_placement_demo",
    )
    assert result["status"] == "ready"
    assert result["connections"][0]["status"] == "released_datum_placement_ready"
    assert result["connections"][0]["selectedMode"] == "parameterized_datum_placement"


def test_unknown_execution_mode_fails_closed():
    with pytest.raises(MechanicalInterfaceContractError, match="unsupported relation"):
        planner.assess_global_assembly_context_interfaces(
            ROOT, _context("project03::AA00", "project01::GN00"),
            relation_execution_mode="guess_datum",
        )


def test_ambiguous_cad_aliases_are_not_arbitrarily_selected(monkeypatch):
    monkeypatch.setattr(
        planner, "_definition_identity_maps",
        lambda _: ({}, {"cad/ambiguous": ["project03::AI00", "project01::SM00"]}),
    )
    result = planner._plan_datum_connection_with_identity(
        ROOT, "cad/ambiguous", selected_slot_definition_id="project01::JJ00"
    )
    assert result["status"] == "needs_interface_confirmation"
    assert result["readyForReleasedCadExecution"] is False


@pytest.mark.parametrize("mode", [None, "datum_placement_demo"])
def test_natural_language_compiler_forwards_explicit_mode_to_contract_gate(tmp_path, monkeypatch, mode):
    received = []
    monkeypatch.setattr(nl_manifest, "create_context", lambda *args: {})
    monkeypatch.setattr(nl_manifest, "apply_command_sequence", lambda *args: {"success": True})
    monkeypatch.setattr(nl_manifest, "load_context", lambda *args: {"contextId": "test"})
    monkeypatch.setattr(nl_manifest, "context_path", lambda *args: tmp_path / "test.json")

    def gate(workspace, context, *, relation_execution_mode=None):
        received.append(relation_execution_mode)
        return {"status": "blocked", "blockedConnectionCount": 1}

    monkeypatch.setattr(nl_manifest, "assess_global_assembly_context_interfaces", gate)
    result = nl_manifest.compile_natural_language_manifest_job(
        ROOT,
        {
            "contextId": "test", "requirements": ["建立箱体", "增加清洁模组"],
            "relationExecutionMode": mode, "enforceMechanicalInterfaceContracts": True,
        },
    )
    assert received == [mode]
    assert result["status"] == "blocked_by_mechanical_interface_contracts"
    assert result["cadStarted"] is False

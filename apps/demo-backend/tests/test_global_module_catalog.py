from pathlib import Path

from demo_backend.global_module_catalog import (
    build_global_module_catalog,
    infer_module_category,
    validate_global_module_catalog,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def test_build_real_global_catalog_is_deterministic_and_loads_identity_only_project06():
    first = build_global_module_catalog(WORKSPACE)
    second = build_global_module_catalog(WORKSPACE)

    assert first["catalogDigest"] == second["catalogDigest"]
    assert first["summary"]["loadedProjectCount"] == 5
    assert first["summary"]["missingProjectCount"] == 0
    assert first["summary"]["moduleDefinitionCount"] >= 39
    assert first["summary"]["semanticPortCount"] >= 30
    assert not any(item["code"] == "PROJECT_PROFILE_MISSING" for item in first["blockers"])
    project06 = next(item for item in first["projects"] if item["projectId"] == "project06")
    assert project06["status"] == "loaded"
    assert first["collisionPolicy"]["enabled"] is False
    assert validate_global_module_catalog(first)["success"] is True


def test_project_tokens_are_provenance_not_global_identity():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project01", "project02"))
    transport = [
        item for item in catalog["moduleDefinitions"] if item["category"] == "transport"
    ]

    assert len(transport) >= 2
    assert len({item["moduleDefinitionId"] for item in transport}) == len(transport)
    assert all(item["componentNames"] for item in transport)


def test_project03_prefixed_legacy_tokens_resolve_to_profile_modules():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project03",))
    unresolved = [
        item
        for item in catalog["blockers"]
        if item["code"] == "PORT_MODULE_NOT_IN_PROFILE"
    ]

    assert unresolved == []
    assert catalog["summary"]["semanticPortCount"] > 0


def test_category_inference_is_for_search_only():
    assert infer_module_category("产品定位CCD模组") == "ccd"
    assert infer_module_category("组合模块", ["条码扫描模组"]) == "scanner"
    assert infer_module_category("设备箱体与安装基座") == "frame"


def test_declared_shared_endpoint_catalog_makes_project02_spacing_ports_portable():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"] == "project02_planar_spacing_distance"
    )
    compatibility = [
        row
        for row in catalog["compatibility"]
        if row["globalTemplateId"] == template["globalTemplateId"]
    ]

    assert compatibility
    assert all(row["portableForTemplate"] is True for row in compatibility)
    assert template["provenance"]["endpointCatalogPath"].endswith(
        "project02_A500_A700_seed_plus_A720009_leaf_v1.json"
    )


def test_project01_primary_and_anti_rotation_are_a_first_class_template_combination():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project01",))

    assert catalog["summary"]["templateCombinationCount"] == 1
    combination = catalog["templateCombinations"][0]
    assert combination["legacyCombinationId"] == (
        "GN00_primary_plus_SS00_anti_rotation"
    )
    assert combination["memberLegacyTemplateIds"] == [
        "GN00_SS00_standalone_parallel",
        "GN00_to_JJ00_primary",
    ]
    assert combination["primaryLegacyTemplateId"] == "GN00_to_JJ00_primary"
    assert combination["exactMemberSetRequired"] is True
    assert combination["fullyLocatesAddedComponent"] is True
    assert combination["expectedResidualDof"] == 0


def test_cross_project_package_resolves_each_port_against_its_own_project_profile():
    catalog = build_global_module_catalog(
        WORKSPACE, project_ids=("project02", "project03")
    )
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"]
        == "AH00_to_A600_cross_project_three_datum_installation"
    )
    candidate_ids = {
        *template["candidatePortIdsA"],
        *template["candidatePortIdsB"],
    }
    ports = {
        row["globalPortId"]: row
        for row in catalog["semanticPorts"]
        if row["globalPortId"] in candidate_ids
    }
    module_ids = {row["moduleDefinitionId"] for row in ports.values()}
    aliases = {
        alias["projectId"]
        for module in catalog["moduleDefinitions"]
        if module["moduleDefinitionId"] in module_ids
        for alias in module.get("projectAliases") or []
    }

    assert aliases == {"project02", "project03"}
    assert all(row["portable"] is True for row in ports.values())
    assert not any(
        row["code"] in {"PORT_PROJECT_NOT_LOADED", "PORT_MODULE_NOT_IN_PROFILE"}
        and row.get("source", "").endswith(
            "project02_A600_project03_AH00_cross_project_slot_v1/"
            "semantic_port_catalog.json"
        )
        for row in catalog["blockers"]
    )

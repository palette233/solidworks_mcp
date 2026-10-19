from __future__ import annotations

from copy import deepcopy

import pytest

from demo_backend.project_assembly_profile import (
    PROFILE_SCHEMA,
    ProjectAssemblyProfileError,
    assembly_profile_digest,
    load_project_assembly_profile,
    module_alias_map,
    module_policy_map,
    validate_project_assembly_profile,
)


def test_project02_profile_is_complete_and_versioned() -> None:
    profile = load_project_assembly_profile("project02")
    assert profile["schemaVersion"] == PROFILE_SCHEMA
    assert profile["baseModule"] == "A600"
    assert profile["validatedSequence"] == [
        "A600", "A800", "A180", "A700", "A300", "A500", "A100", "A200", "T401"
    ]
    assert profile["modules"]["T401"]["instanceCount"] == 2
    assert len(profile["profileDigest"]) == 64


@pytest.mark.parametrize(
    ("project_id", "base", "sequence", "object_count"),
    [
        (
            "project01",
            "JJ00",
            ["JJ00", "SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00"],
            10,
        ),
        (
            "project03",
            "AA00",
            ["AA00", "AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"],
            10,
        ),
        (
            "project05",
            "A000",
            ["A000", "D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"],
            11,
        ),
        (
            "project06",
            "A000",
            ["A000", "D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"],
            13,
        ),
    ],
)
def test_cross_project_profiles_are_versioned_with_truthful_cad_readiness(
    project_id: str,
    base: str,
    sequence: list[str],
    object_count: int,
) -> None:
    profile = load_project_assembly_profile(project_id)
    assert profile["baseModule"] == base
    assert profile["validatedSequence"] == sequence
    assert sum(row.get("instanceCount", 1) for row in profile["modules"].values()) == object_count
    statuses = {
        token: row["assemblyPolicy"]["implementationStatus"]
        for token, row in profile["modules"].items()
        if token != base
    }
    if project_id == "project06":
        assert set(statuses.values()) == {"identity_only_cad_unvalidated"}
        assert profile["releaseBoundary"]["planPreviewMayPass"] is False
        assert profile["releaseBoundary"]["cadExecutionMayStart"] is False
    elif project_id == "project05":
        assert set(statuses.values()) == {"single_module_cad_validated"}
        assert profile["releaseBoundary"]["planPreviewMayPass"] is True
        assert profile["releaseBoundary"]["cadExecutionMayStart"] is True
        assert profile["releaseBoundary"]["staticDemoMayPass"] is True
    elif project_id == "project03":
        assert statuses["AE00"] == "single_module_cad_validated"
        assert statuses["AD00"] == "single_module_cad_validated"
        assert statuses["AI00"] == "single_module_cad_validated"
        assert statuses["AG00"] == "single_module_cad_validated"
        assert statuses["AH00"] == "single_module_cad_validated"
        assert statuses["AJ00"] == "single_module_cad_validated"
        assert statuses["AB00"] == "full_static_cad_validated_hybrid_snapshot"
    else:
        assert statuses["SS00"] == "single_module_cad_validated"
        assert statuses["FF00"] == "single_module_static_cad_validated_dynamic_missing"
        assert statuses["SM00"] == "single_module_cad_validated"
        assert statuses["GN00"] == "single_module_cad_validated"
        assert statuses["BD00"] == "single_module_cad_validated"
        assert statuses["GJ00"] == "single_module_cad_validated"
        assert statuses["LM00"] == "full_static_cad_validated_parent_context_snapshot"
        assert profile["releaseBoundary"]["staticDemoMayPass"] is True
        assert profile["releaseBoundary"]["productionDynamicRequires"]


def test_alias_and_policy_views_are_generated_from_profile() -> None:
    profile = load_project_assembly_profile("project02")
    aliases = module_alias_map(profile)
    policies = module_policy_map(profile)
    assert aliases["扫描模组"] == "A180"
    assert aliases["供胶系统"] == "T401"
    assert policies["A180"]["requires"] == ["A800"]
    assert policies["A100"]["requires"] == ["A800", "A180", "A700", "A300", "A500"]
    assert "A600" not in policies


def test_profile_digest_is_stable_for_equivalent_content() -> None:
    profile = load_project_assembly_profile("project02")
    payload = {key: value for key, value in profile.items() if key not in {"profilePath", "profileDigest"}}
    assert assembly_profile_digest(payload) == assembly_profile_digest(deepcopy(payload))


def test_profile_validation_rejects_alias_collision() -> None:
    profile = load_project_assembly_profile("project02")
    payload = {key: deepcopy(value) for key, value in profile.items() if key not in {"profilePath", "profileDigest"}}
    payload["modules"]["A180"]["aliases"].append("传输模组")
    with pytest.raises(ProjectAssemblyProfileError, match="同时指向"):
        validate_project_assembly_profile(payload)


def test_profile_validation_rejects_unknown_dependency() -> None:
    profile = load_project_assembly_profile("project02")
    payload = {key: deepcopy(value) for key, value in profile.items() if key not in {"profilePath", "profileDigest"}}
    payload["modules"]["A180"]["assemblyPolicy"]["requires"] = ["A999"]
    with pytest.raises(ProjectAssemblyProfileError, match="依赖未登记模组"):
        validate_project_assembly_profile(payload)

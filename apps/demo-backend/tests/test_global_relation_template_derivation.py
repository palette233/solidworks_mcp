import json
from pathlib import Path

from demo_backend.global_relation_semantics import normalize_template_relation_profile
from demo_backend.global_relation_template_derivation import (
    derive_standalone_validation_relation,
)


ROOT = Path(__file__).resolve().parents[3]
CATALOG = json.loads(
    (
        ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json"
    ).read_text(encoding="utf-8-sig")
)
SOURCE = "template/project03/ab00-to-aa00-partial-anchored-installation/05116b19ae"
PROJECT01_PARALLEL = "template/project01/gn00-ss00-standalone-parallel/5df3a32e59"
PROJECT01_COINCIDENT = "template/project01/gn00-jj00-standalone-coincident/e9a88b60ee"
PROJECT01_CONCENTRIC = "template/project01/gn00-jj00-standalone-concentric/95d38e785d"


def test_project03_distance5_can_be_derived_as_read_only_standalone_relation():
    candidate, evidence = derive_standalone_validation_relation(
        CATALOG,
        source_global_template_id=SOURCE,
        mate_name="距离5",
    )

    derived = next(
        row
        for row in candidate["connectionTemplates"]
        if row["globalTemplateId"] == evidence["derivedGlobalTemplateId"]
    )
    profile = normalize_template_relation_profile(derived)
    assert profile["supportsStandaloneRelation"] is True
    assert profile["drivesPlacement"] is False
    assert profile["relationKinds"] == ["distance"]
    assert profile["validationMateStepCount"] == 1
    assert derived["mateSteps"][0]["distanceMeters"] == 0.04
    assert evidence["sourceSemanticsChanged"] is False


def test_project01_existing_parallel_mate_can_be_derived_as_read_only_observation():
    candidate, evidence = derive_standalone_validation_relation(
        CATALOG,
        source_global_template_id=PROJECT01_PARALLEL,
        mate_name="平行1",
        observation_of_existing_mate=True,
    )

    derived = next(
        row
        for row in candidate["connectionTemplates"]
        if row["globalTemplateId"] == evidence["derivedGlobalTemplateId"]
    )
    profile = normalize_template_relation_profile(derived)
    assert profile["supportsStandaloneRelation"] is True
    assert profile["drivesPlacement"] is False
    assert profile["relationKinds"] == ["parallel"]
    assert derived["mateSteps"][0]["applicationMode"] == "validate_only"
    assert derived["provenance"]["sourceApplicationMode"] == "driving"
    assert evidence["derivationMode"] == "existing_mate_observation"
    assert evidence["sourceSemanticsChanged"] is False


def test_project01_existing_parallel_mate_requires_explicit_observation_mode():
    try:
        derive_standalone_validation_relation(
            CATALOG,
            source_global_template_id=PROJECT01_PARALLEL,
            mate_name="平行1",
        )
    except ValueError as error:
        assert "validate_only" in str(error)
    else:
        raise AssertionError("driving mate must not silently become a validation relation")


def test_project01_existing_coincident_mate_becomes_two_tolerance_observation():
    candidate, evidence = derive_standalone_validation_relation(
        CATALOG,
        source_global_template_id=PROJECT01_COINCIDENT,
        mate_name="重合6",
        observation_of_existing_mate=True,
    )

    derived = next(
        row
        for row in candidate["connectionTemplates"]
        if row["globalTemplateId"] == evidence["derivedGlobalTemplateId"]
    )
    profile = normalize_template_relation_profile(derived)
    assert profile["supportsStandaloneRelation"] is True
    assert profile["drivesPlacement"] is False
    assert profile["relationKinds"] == ["coincident"]
    assert derived["mateSteps"][0]["applicationMode"] == "validate_only"
    assert evidence["derivationMode"] == "existing_mate_observation"


def test_project01_existing_concentric_mate_becomes_read_only_axis_observation():
    candidate, evidence = derive_standalone_validation_relation(
        CATALOG,
        source_global_template_id=PROJECT01_CONCENTRIC,
        mate_name="同心11",
        observation_of_existing_mate=True,
    )

    derived = next(
        row
        for row in candidate["connectionTemplates"]
        if row["globalTemplateId"] == evidence["derivedGlobalTemplateId"]
    )
    profile = normalize_template_relation_profile(derived)
    assert profile["supportsStandaloneRelation"] is True
    assert profile["drivesPlacement"] is False
    assert profile["relationKinds"] == ["concentric"]
    assert derived["mateSteps"][0]["applicationMode"] == "validate_only"
    assert evidence["derivationMode"] == "existing_mate_observation"


from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from demo_backend.bounded_role_station import (
    build_bounded_role_station_candidate,
    validate_bounded_role_station_candidate,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError
from demo_backend.parameterized_datum_placement import (
    compile_parameterized_datum_validation_package,
)


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "data/assembly_stations/cleaning-n000-a600-bounded-role-station-v1.json"


def _candidate() -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    return build_bounded_role_station_candidate(ROOT, config)


def test_builds_new_n000_a600_role_station_candidate() -> None:
    candidate = _candidate()
    assert candidate["status"] == "ready_for_explicit_nonprototype_cad_validation"
    assert candidate["sourceModuleDefinitionId"] == "project05::N000"
    assert candidate["targetBaseDefinitionId"] == "project02::A600"
    assert candidate["nativeRoleStationContainment"]["passed"] is True
    assert candidate["finiteSupportGate"]["passed"] is True
    assert candidate["positionParametersMeters"] != {
        "longitudinal": 0.465,
        "lateral": 0.7125,
        "supportGap": 0.0,
    }
    assert candidate["endpointReuse"]["scope"] == (
        "endpoint_bundle_only_not_position_or_execution_authority"
    )


def test_candidate_allows_only_exact_new_validation_package() -> None:
    candidate = _candidate()
    package = compile_parameterized_datum_validation_package(
        ROOT,
        "project05::N000",
        "project02::A600",
        position_parameters=candidate["positionParametersMeters"],
        distance_flip_dimensions=candidate["distanceFlipDimensions"],
        bounded_role_station_candidate=candidate,
    )
    assert package["status"] == "ready_for_explicit_nonprototype_cad_validation"
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["caseAnchorUsed"] is False
    assert package["targetLeafPoseAnchorsUsed"] is False
    assert package["boundedRoleStationCandidate"]["candidateDigest"] == candidate[
        "candidateDigest"
    ]


def test_candidate_rejects_parameter_or_digest_changes() -> None:
    candidate = _candidate()
    changed = copy.deepcopy(candidate)
    changed["positionParametersMeters"]["lateral"] += 0.001
    with pytest.raises(
        MechanicalInterfaceContractError, match="candidate digest mismatch"
    ):
        validate_bounded_role_station_candidate(
            changed,
            module_definition_id="project05::N000",
            slot_definition_id="project02::A600",
            position_parameters=changed["positionParametersMeters"],
            distance_flip_dimensions=changed["distanceFlipDimensions"],
            safety_block={"reasonCode": "TRANSPORT_OCCUPANCY_REGION_OVERLAP"},
        )


def test_revoked_pair_still_blocks_without_new_station_evidence() -> None:
    with pytest.raises(
        MechanicalInterfaceContractError,
        match="TRANSPORT_OCCUPANCY_REGION_OVERLAP",
    ):
        compile_parameterized_datum_validation_package(
            ROOT,
            "project05::N000",
            "project02::A600",
            position_parameters={
                "longitudinal": 0.465,
                "lateral": 0.7125,
                "supportGap": 0.0,
            },
        )

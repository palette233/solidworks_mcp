from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_project05_d000_scoped_driving_candidate import (  # noqa: E402
    SOURCE_AUDIT,
    SOURCE_ENDPOINTS,
    SOURCE_GRAPH,
    SOURCE_SEMANTIC,
    _read,
    build_candidate_package,
)


def test_scoped_candidate_upgrades_width_without_reguessing_faces():
    source_endpoints = _read(SOURCE_ENDPOINTS)
    candidate, derived_endpoints = build_candidate_package(
        _read(SOURCE_SEMANTIC),
        source_endpoints,
        _read(SOURCE_GRAPH),
        _read(SOURCE_AUDIT),
    )

    template = candidate["connectionTemplates"][0]
    assert template["templateId"] == "D000_to_A000_scoped_driving_v2"
    assert [row["mateName"] for row in template["mateSteps"]] == [
        "重合3",
        "距离1",
        "宽度17",
    ]
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert template["constraintEffect"]["exactMateBundleRequired"] is True
    assert template["mateSteps"][-1]["advancedOptions"]["WidthEndpointIndices"] == [0, 1]
    assert template["mateSteps"][-1]["advancedOptions"]["TabEndpointIndices"] == [2, 3]
    assert candidate["readOnlySourceRelations"] == []
    assert candidate["drivingScope"]["status"] == "candidate_only_not_released"

    source_ids = [row["EndpointId"] for row in source_endpoints["Endpoints"]]
    derived_ids = [row["EndpointId"] for row in derived_endpoints["Endpoints"]]
    assert derived_ids == source_ids
    assert derived_endpoints["DerivedPackage"]["geometryChanged"] is False


def test_scoped_candidate_registers_all_four_width_roles():
    candidate, _ = build_candidate_package(
        _read(SOURCE_SEMANTIC),
        _read(SOURCE_ENDPOINTS),
        _read(SOURCE_GRAPH),
        _read(SOURCE_AUDIT),
    )
    roles = {
        binding["role"]
        for port in candidate["ports"]
        for binding in port["endpointBindings"]
    }
    assert {
        "宽度17_context_1",
        "宽度17_context_2",
        "宽度17_target_1",
        "宽度17_target_2",
    }.issubset(roles)

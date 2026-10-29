import copy
import json
import importlib.util
import sys
from pathlib import Path

import pytest

from demo_backend.direct_interface_validation import (
    DirectInterfaceValidationError,
    compile_direct_interface_validation_package,
)
from demo_backend.mechanical_interface_contracts import (
    _digest,
    load_calibration_contract_catalog,
)
from demo_backend.global_interface_contract_planner import (
    plan_global_interface_connection,
)


ROOT = Path(__file__).resolve().parents[3]
BD00_ROOT = ROOT / "demo/semantic_ports/project01_BD00_fifth_increment_v1"
A600_ROOT = ROOT / "demo/semantic_ports/project02_A600_project03_AH00_cross_project_slot_v1"
ACQUISITION_ROOT = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)
WRAPPER = (
    ROOT
    / "demo/global_assembly_contexts/manifest_jobs/"
    "project02-job-6e3c1b72de5d/packet-runs/packet-001-attempt-01/"
    "base-context-wrapper.SLDASM"
)
BD00_SOURCE = (
    ROOT.parents[1]
    / "cad_data/001-给港中文AI训练用资料_20260624/项目01/01-项目3D图纸/"
    "CITLB24N074&CITLB24N075/8.FL9C24N074BD00.001_标定模组/"
    "FL9C24N074BD00.001.SLDASM"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _compile(**overrides) -> dict:
    request = _read(ACQUISITION_ROOT / "slot_acquisition_request.json")
    catalog = copy.deepcopy(load_calibration_contract_catalog(ROOT))
    # Keep compiler unit tests independent from the mutable live release set.
    # The production catalog may already contain the exact BD00/A600 release.
    exact = next(
        row
        for row in catalog["compatibilityMatrix"]
        if row["moduleDefinitionId"] == "project01::BD00"
        and row["slotDefinitionId"] == "project02::A600"
        and row["compatible"] is True
    )
    exact["requiresNewPairCadValidation"] = True
    exact["existingPairReleaseReusable"] = False
    exact["pairReleaseEvidence"] = None
    exact["status"] = "compatible_contract_pending_pair_cad"
    catalog["catalogDigest"] = _digest(
        {key: value for key, value in catalog.items() if key != "catalogDigest"}
    )
    kwargs = {
        "contract_catalog": catalog,
        "module_definition_id": "project01::BD00",
        "slot_definition_id": "project02::A600",
        "module_face_catalog": _read(BD00_ROOT / "face_endpoint_catalog.json"),
        "slot_face_catalog": _read(A600_ROOT / "face_endpoint_catalog.json"),
        "module_source_path": BD00_SOURCE,
        "slot_source_path": Path(request["targetBase"]["cadPath"]),
        "base_wrapper_path": WRAPPER,
        "module_hierarchy_path": "FL9C24N074BD00.001-1",
        "slot_hierarchy_path": "FL9A24D062A600.001-1",
    }
    kwargs.update(overrides)
    return compile_direct_interface_validation_package(**kwargs)


def test_bd00_a600_package_uses_real_endpoints_without_pose_anchor():
    package = _compile()
    graph = package["effectiveMateGraph"]
    assert package["status"] == "ready_for_nonprototype_cad_validation"
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["caseAnchorUsed"] is False
    assert package["normalExecutionAuthorized"] is False
    assert [row["MateTypeName"] for row in graph["Mates"]] == [
        "swMateCOINCIDENT",
        "swMateCONCENTRIC",
        "swMateCONCENTRIC",
    ]
    assert [row["AlignmentName"] for row in graph["Mates"]] == [
        "swMateAlignANTI_ALIGNED",
        "swMateAlignALIGNED",
        "swMateAlignALIGNED",
    ]
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["A600"]
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert package["instantiatedTemplate"]["templateId"] == package["templateId"]
    assert package["selectedEndpointCatalog"]["EndpointCount"] == 6
    assert {
        row["EndpointId"]
        for row in package["selectedEndpointCatalog"]["Endpoints"]
    } == set(package["selectedEndpointIds"])
    assert all(
        endpoint.get("SourceAssemblyPersistentReferenceBase64")
        for mate in graph["Mates"]
        for endpoint in mate["Endpoints"]
    )


def test_released_pair_is_rejected_instead_of_being_revalidated():
    with pytest.raises(
        DirectInterfaceValidationError,
        match="not an unpublished CAD-validation candidate",
    ):
        _compile(
            module_definition_id="project03::AH00",
            module_hierarchy_path="FL9A24D063AH00.001-1",
        )


def test_json_entry_materializes_digest_valid_package_and_refuses_overwrite(tmp_path, monkeypatch):
    from demo_backend.direct_interface_relation_release import load_materialized_direct_interface_package
    spec = importlib.util.spec_from_file_location("direct_candidate_cli", ROOT / "scripts/compile_direct_interface_candidate.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    compiled = _compile()
    monkeypatch.setattr(cli, "compile_direct_interface_validation_package", lambda **kwargs: copy.deepcopy(compiled))
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"schemaVersion": "direct-interface-candidate-request/v1", "compilerInputs": {
        key: str(empty) for key in ("contract_catalog", "module_face_catalog", "slot_face_catalog")
    }}), encoding="utf-8")
    output = tmp_path / "candidate"
    monkeypatch.setattr(sys, "argv", ["compile", str(request), "--output-dir", str(output)])
    assert cli.main() == 0
    package, graph, _ = load_materialized_direct_interface_package(output)
    assert package["packageDigest"] == compiled["packageDigest"]
    assert graph == compiled["effectiveMateGraph"]
    assert "compilationTiming" not in package
    assert _read(output / "compilation-report.json")["cadExecuted"] is False
    with pytest.raises(FileExistsError):
        cli.main()


def test_missing_endpoint_fails_before_cad():
    catalog = _read(BD00_ROOT / "face_endpoint_catalog.json")
    broken = copy.deepcopy(catalog)
    contract = next(
        row
        for row in load_calibration_contract_catalog(ROOT)["contracts"]
        if row["moduleDefinitionId"] == "project01::BD00"
    )
    missing_id = contract["endpointBindings"][0]["endpointId"]
    broken["Endpoints"] = [
        row for row in broken["Endpoints"] if row["EndpointId"] != missing_id
    ]
    with pytest.raises(DirectInterfaceValidationError, match="cannot be recovered"):
        _compile(module_face_catalog=broken)


def test_confirmed_base_definition_selects_the_only_released_compatible_slot():
    plan = plan_global_interface_connection(
        ROOT,
        "project01::BD00",
        selected_slot_definition_id="project02::A600",
    )
    assert plan["status"] == "selected_explicit_compatible_slot"
    assert plan["readyForTemplateCompilation"] is True
    assert plan["selectedMatch"]["compatible"] is True
    assert plan["selectedMatch"]["existingPairReleaseReusable"] is True
    assert plan["selectedMatch"]["slotDefinitionId"] == "project02::A600"
    assert plan["selectedMatch"]["interfaceFamily"] == (
        "calibration_plane_two_hole_mount/v1"
    )

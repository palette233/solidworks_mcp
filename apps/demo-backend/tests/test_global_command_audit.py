import json
from pathlib import Path

from demo_backend.global_command_audit import build_global_command_audit


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "demo/global_assembly_contexts/project01-jj00-ss00-gn00-v10-combination-v1"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_project01_v10_command_audit_maps_language_to_ports_combination_and_packets():
    catalog = _read(
        ROOT
        / "demo/global_assembly_catalog/releases/"
        "relation-v10-project01-combination-driving-20261011/"
        "global_module_catalog.json"
    )
    context = _read(
        ROOT
        / "demo/global_assembly_contexts/"
        "project01-jj00-ss00-gn00-v10-combination-v1.json"
    )
    report = build_global_command_audit(
        catalog,
        context,
        _read(BASE / "transaction-dag.json"),
        _read(BASE / "cad-transaction-manifest.json"),
    )

    assert report["commandCount"] == 4
    assert report["mappedCommandCount"] == 4
    assert report["commands"][0]["status"] == "base_context_declared"
    ss00 = report["commands"][1]
    primary = report["commands"][2]
    anti_rotation = report["commands"][3]
    assert ss00["cadPacketIds"] == ["packet-001"]
    assert primary["cadPacketIds"] == ["packet-002"]
    assert anti_rotation["cadPacketIds"] == ["packet-002"]
    assert primary["connections"][0]["singleTemplateExpectedResidualDof"] == 1
    assert anti_rotation["connections"][0]["singleTemplateExpectedResidualDof"] == 4
    assert primary["combinedExpectedResidualDof"] == 0
    assert anti_rotation["combinedExpectedResidualDof"] == 0
    assert primary["selectedTemplateCombinationIds"] == anti_rotation[
        "selectedTemplateCombinationIds"
    ]
    assert primary["selectedTemplateCombinationIds"] == [
        "combination/project01/gn00-primary-plus-ss00-anti-rotation/18004cfdec"
    ]
    assert primary["connections"][0]["portA"]["endpointRoles"]

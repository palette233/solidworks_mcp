"""Pure tests: no SolidWorks process is started by this module."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gn00_parameter_script", ROOT / "scripts/run_gn00_chain_parameter_comparison.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_resolve_stage_binds_cad_envelope_and_file(tmp_path):
    output, cad_path = tmp_path / "four.SLDASM", tmp_path / "cad-result.json"
    output.write_bytes(b"closed assembly fixture")
    write(cad_path, {"success": True, "outputAssemblyPath": str(output), "outputAssemblySha256": runner.sha(output)})
    envelope_path = tmp_path / "execution-envelope.json"
    write(envelope_path, {"success": True, "cadResultPath": str(cad_path)})
    closure = {"status": "passed", "checks": {"ok": True}, "finalAssemblyPath": str(output),
               "finalAssemblySha256": runner.sha(output), "executionEnvelopePath": str(envelope_path),
               "executionEnvelopeSha256": runner.sha(envelope_path)}
    closure["closureDigest"] = runner.digest(closure)
    path = tmp_path / "stage-closure.json"
    write(path, closure)
    assert runner.resolve_stage(path)[:2] == (output, cad_path)
    output.write_bytes(b"changed")
    with pytest.raises(ValueError, match="output or execution envelope changed"):
        runner.resolve_stage(path)


def test_resolve_stage_rejects_changed_closure(tmp_path):
    path = tmp_path / "stage-closure.json"
    write(path, {"status": "passed", "checks": {"ok": True}, "closureDigest": "stale"})
    with pytest.raises(ValueError, match="digest changed"):
        runner.resolve_stage(path)


def states(tmp_path):
    transform = [1., 0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0.]
    components = [{"sourcePath": f"D:/cad/{token}.001.SLDASM", "name": f"{token}.001-1",
                   "transform": transform[:], "configuration": "Default", "solvingState": 0,
                   "constrainedStatus": 3, "isFixed": token == "AA00"}
                  for token in ("AA00", "SS00", "AI00", "BD00", "GN00")]
    mates = [{"name": f"old-{i}", "mateType": 5, "alignment": 0,
              "dimensionSystemValue": .1, "isSuppressed": False, "errorCode": 0} for i in range(9)]
    source, output = tmp_path / "source.SLDASM", tmp_path / "output.SLDASM"
    source.write_bytes(b"four")
    output.write_bytes(b"five")
    state = {"success": True, "assemblyPath": str(output), "assemblySha256": runner.sha(output),
             "sourceCheckpointSha256Before": runner.sha(source), "sourceCheckpointSha256After": runner.sha(source),
             "sourceObserved": {"readOnly": True, "components": copy.deepcopy(components[:4]), "allTopLevelMates": copy.deepcopy(mates)},
             "observed": {"readOnly": True, "components": components,
                          "allTopLevelMates": mates + [{**mates[0], "name": f"new-{i}"} for i in range(3)]}}
    return state, source, output


def test_readonly_requires_preserved_four_components_and_nine_mates(tmp_path):
    state, source, output = states(tmp_path)
    path = tmp_path / "readonly.json"
    write(path, state)
    assert runner.verify_readonly_report(path, output, source)[1]["success"]
    state["observed"]["components"][1]["transform"][10] = .002
    write(path, state)
    with pytest.raises(ValueError, match="four components or nine mates"):
        runner.verify_readonly_report(path, output, source)


def test_readonly_rejects_suppressed_original_mate(tmp_path):
    state, source, output = states(tmp_path)
    state["observed"]["allTopLevelMates"][1]["isSuppressed"] = True
    path = tmp_path / "readonly.json"
    write(path, state)
    with pytest.raises(ValueError, match="four components or nine mates"):
        runner.verify_readonly_report(path, output, source)


def test_readonly_rejects_file_changed_after_observation(tmp_path):
    state, source, output = states(tmp_path)
    path = tmp_path / "readonly.json"
    write(path, state)
    output.write_bytes(b"different")
    with pytest.raises(ValueError, match="stale"):
        runner.verify_readonly_report(path, output, source)


def test_run_phase_refuses_to_overwrite_existing_diagnostics(tmp_path):
    write(tmp_path / "cad-insert.execution.json", {"returnCode": 2})
    with pytest.raises(FileExistsError, match="Preserving"):
        runner.run_phase("cad-insert", ["must-not-run"], tmp_path, [], 1)

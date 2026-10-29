"""Offline guard/timeout tests only; they do not prove a live CAD result."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("station_append", ROOT/"scripts/run_station_candidate_append.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def graph():
    return runner.read(ROOT/"demo/role_station_strengthening_20261028/functional-chain-v1/gn00-service-candidate-v1/effective-mate-graph.json")


def test_accepts_unanchored_rigid_pair_without_mutation():
    value = graph()
    before = copy.deepcopy(value)
    runner.validate_graph(value, "AA00", "GN00")
    assert before == value


@pytest.mark.parametrize("change", [
    lambda g: g.update(CaseAnchor={"module": "GN00"}),
    lambda g: g.update(TargetLeafPoseAnchors=[{}]),
    lambda g: g["EditPolicy"].update(fixedModuleTokens=["AA00", "GN00"]),
    lambda g: g["EditPolicy"].update(initialPlacementMode="source"),
    lambda g: g["Modules"][1].update(SolvingState=1),
    lambda g: g["Modules"].append({"ModuleToken": "A700"}),
    lambda g: g["Mates"][0].update(IsSuppressed=True),
    lambda g: g["Mates"][0].update(ModuleTokens=["AA00", "A700"]),
    lambda g: g["Mates"][0].update(Endpoints=[]),
    lambda g: g["Mates"][0].update(MateType=2, MateTypeName="swMatePARALLEL"),
    lambda g: g["Mates"][0].update(Distance=float("nan")),
    lambda g: g["Mates"][0].update(AdvancedOptions={"DistanceFlipDimension": "false"}),
    lambda g: g["Mates"][0]["Endpoints"][0].update(ModuleToken="A700"),
    lambda g: g["Mates"][0]["Endpoints"][0].update(SurfaceType="Cylinder"),
    lambda g: g["Mates"][0]["Endpoints"][0].update(FaceNormalWorld=g["Mates"][1]["Endpoints"][0]["FaceNormalWorld"]),
    lambda g: g["Modules"][1]["SourceTransform"].__setitem__(9, 1),
    lambda g: g["EditPolicy"].update(fixCaseAnchorBeforeMates=True),
    lambda g: g["BaseGraphPolicy"].update(prototypeTopLevelTargetPoseAllowed=True),
])
def test_rejects_inappropriate_experiment(change):
    value = graph()
    change(value)
    with pytest.raises(ValueError):
        runner.validate_graph(value, "AA00", "GN00")


def test_timeout_is_recorded_not_success(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1, output=b"partial CAD progress", stderr=b"partial warning")
    monkeypatch.setattr(runner.subprocess, "run", timeout)
    report = {"phases": []}
    with pytest.raises(RuntimeError):
        runner.run_phase("cad", ["fake"], tmp_path, report, 1)
    record = runner.read(tmp_path/"cad.execution.json")
    assert record["timeout"] and record["returnCode"] is None
    assert record["durationSeconds"] >= 0
    assert record["stdout"] == "partial CAD progress"
    assert record["stderr"] == "partial warning"
    assert report["phases"][0]["name"] == "cad"


def test_failed_child_is_retained(monkeypatch, tmp_path):
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 2, b"", b"bad mate"))
    with pytest.raises(RuntimeError):
        runner.run_phase("cad", ["fake"], tmp_path, {"phases": []}, 1)
    assert runner.read(tmp_path/"cad.execution.json")["stderr"] == "bad mate"


def test_real_p000_three_datum_graph_allows_base_baseline_transform():
    value = runner.read(ROOT/"demo/role_station_strengthening_20261028/functional-chain-v1/p000-native-cup-projection-candidate-v1/candidate_effective_mate_graph.json")
    assert value["Modules"][0]["SourceTransform"] != runner.IDENTITY
    runner.validate_graph(value, "AA00", "P000")


def test_launch_failure_is_retained(monkeypatch, tmp_path):
    def failed(*args, **kwargs):
        raise OSError("could not launch child")
    monkeypatch.setattr(runner.subprocess, "run", failed)
    with pytest.raises(RuntimeError):
        runner.run_phase("cad", ["fake"], tmp_path, {"phases": []}, 1)
    assert runner.read(tmp_path/"cad.execution.json")["launchFailed"] is True


def _arguments(source, graph_file, output):
    return ["runner", "--source", str(source), "--graph", str(graph_file), "--output-dir", str(output),
            "--expected-source-sha256", runner.sha(source), "--expected-graph-sha256", runner.sha(graph_file),
            "--target", "GN00", "--source-count", "4"]


def test_explicit_demo_authorization_is_required_before_launch(monkeypatch, tmp_path):
    source, graph_file = tmp_path/"source.SLDASM", tmp_path/"graph.json"
    source.write_bytes(b"synthetic fixture only")
    graph_file.write_text(json.dumps(graph()), encoding="utf-8")
    monkeypatch.setattr(runner.sys, "argv", _arguments(source, graph_file, tmp_path/"out"))
    monkeypatch.setattr(runner, "run_phase", lambda *a, **k: pytest.fail("CAD must not run"))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert not (tmp_path/"out").exists()


def test_input_change_between_confirmation_and_launch_does_not_reauthorize_new_hash(monkeypatch, tmp_path):
    source, graph_file = tmp_path/"source.SLDASM", tmp_path/"graph.json"
    source.write_bytes(b"synthetic fixture only")
    graph_file.write_text(json.dumps(graph()), encoding="utf-8")
    output = tmp_path/"out"
    argv = _arguments(source, graph_file, output) + ["--allow-demo-estimate"]
    original, count = runner.sha, 0
    def changed(path):
        nonlocal count
        if Path(path) == source:
            count += 1
            if count >= 2:
                return "0" * 64
        return original(path)
    monkeypatch.setattr(runner, "sha", changed)
    monkeypatch.setattr(runner.sys, "argv", argv)
    monkeypatch.setattr(runner, "run_phase", lambda *a, **k: pytest.fail("CAD must not run"))
    assert runner.main() == 2
    summary = runner.read(output/"append-summary.json")
    assert summary["success"] is False
    assert summary["sourceAssemblySha256"] == argv[argv.index("--expected-source-sha256") + 1]
    assert "changed before CAD launch" in summary["error"]


def test_missing_source_after_child_failure_still_retains_summary(monkeypatch, tmp_path):
    source, graph_file = tmp_path/"source.SLDASM", tmp_path/"graph.json"
    source.write_bytes(b"synthetic fixture only")
    graph_file.write_text(json.dumps(graph()), encoding="utf-8")
    output = tmp_path/"out"
    argv = _arguments(source, graph_file, output) + ["--allow-demo-estimate"]
    def failed(name, command, *args, **kwargs):
        assert command[command.index("--expected-source-sha256") + 1] == argv[argv.index("--expected-source-sha256") + 1]
        source.unlink()
        raise RuntimeError("synthetic child failure")
    monkeypatch.setattr(runner.sys, "argv", argv)
    monkeypatch.setattr(runner, "run_phase", failed)
    assert runner.main() == 2
    summary = runner.read(output/"append-summary.json")
    assert summary["success"] is False and summary["sourceUnchanged"] is False
    assert summary["finalEvidenceErrors"]


def test_actual_gn00_saved_result_and_state_satisfy_explicit_postchecks():
    directory = ROOT/"demo/role_station_strengthening_20261028/functional-chain-v1/s05-gn00"
    cad = runner.read(directory/"cad-result.json")
    source, graph_file, output = Path(cad["sourceAssemblyPath"]), Path(cad["executionEffectiveGraphPath"]), directory/"assembly.SLDASM"
    runner.validate_cad_result(cad, source=source, graph=graph_file, output=output,
        source_sha=cad["sourceAssemblySha256Before"], graph_sha=cad["executionEffectiveGraphSha256"], target="GN00", variant=3)
    runner.validate_state(runner.read(directory/"reopened-state.json"), source=source, output=output,
        source_sha=cad["sourceAssemblySha256Before"], source_count=4, base="AA00", target="GN00", graph=graph())
    cad["toolResult"]["Diagnostics"] = []
    with pytest.raises(ValueError, match="nonprototype"):
        runner.validate_cad_result(cad, source=source, graph=graph_file, output=output,
            source_sha=cad["sourceAssemblySha256Before"], graph_sha=cad["executionEffectiveGraphSha256"], target="GN00", variant=3)

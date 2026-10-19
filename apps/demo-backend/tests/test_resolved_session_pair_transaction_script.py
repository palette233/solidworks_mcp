from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_PATH = WORKSPACE / "scripts/run_resolved_session_pair_transaction.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_resolved_session_pair_transaction", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(tmp_path: Path, monkeypatch, *, fail_cad: bool):
    module = _load_script()
    source = tmp_path / "source.SLDASM"
    output = tmp_path / "output.SLDASM"
    result = tmp_path / "result.json"
    work_dir = tmp_path / "transaction"
    executable = tmp_path / "mcp.exe"
    source.write_bytes(b"immutable-source")
    executable.write_bytes(b"exe")
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def call_tool(self, name, payload):
            calls.append((name, payload))
            if name == "ExportModuleMateGraph":
                graph = {"SchemaVersion": "solidworks-module-mate-graph/v1.4"}
                Path(payload["outputPath"]).write_text(json.dumps(graph), encoding="utf-8")
                return graph
            assert name == "RemateComponentInAssemblyContextFromMateGraph"
            Path(payload["outputAssemblyPath"]).write_bytes(b"staging-assembly")
            if fail_cad:
                raise RuntimeError("simulated CAD failure")
            return {
                "Success": True,
                "ExecutionMode": "direct_existing_component_mate_edit",
                "TargetComponentReinserted": False,
                "TargetComponentExplicitlyDisplaced": False,
            }

        def call_tool_text(self, name, payload):
            calls.append((name, payload))
            return "closed"

    monkeypatch.setattr(
        module,
        "build_pair_transaction",
        lambda *args, **kwargs: (
            {"Modules": [], "Mates": []},
            {"operations": [{"operation": "updateMate"}, {"operation": "updateMate"}]},
            {"Mates": [{"MateName": "M1"}, {"MateName": "M2"}]},
            {"publishAllowed": True, "constraintRank": 6, "residualDof": 0},
        ),
    )
    args = argparse.Namespace(
        source=source,
        target="D000",
        context="A000",
        output=output,
        work_dir=work_dir,
        result=result,
        exe=executable,
        timeout=10.0,
        direct_stdio=True,
    )
    payload = module.run_pipeline(args, client_factory=FakeClient)
    return payload, output, result, calls


def test_single_command_resolved_session_pipeline_publishes_atomically(tmp_path, monkeypatch):
    payload, output, result, calls = _run(tmp_path, monkeypatch, fail_cad=False)
    assert payload["success"] is True
    assert payload["published"] is True
    assert payload["sourceAssemblyUnchanged"] is True
    assert output.read_bytes() == b"staging-assembly"
    assert json.loads(result.read_text(encoding="utf-8"))["outputAssemblySha256"]
    remate = next(item for item in calls if item[0] == "RemateComponentInAssemblyContextFromMateGraph")
    assert remate[1]["preserveResolvedSourceSession"] is True
    assert (tmp_path / "transaction/manifest.json").is_file()


def test_single_command_resolved_session_pipeline_archives_cad_failure(tmp_path, monkeypatch):
    payload, output, result, calls = _run(tmp_path, monkeypatch, fail_cad=True)
    assert payload["success"] is False
    assert payload["published"] is False
    assert not output.exists()
    assert Path(payload["failedArtifactPath"]).read_bytes() == b"staging-assembly"
    assert "cad_execution: simulated CAD failure" == payload["executionError"]
    assert json.loads(result.read_text(encoding="utf-8"))["sourceAssemblyUnchanged"] is True

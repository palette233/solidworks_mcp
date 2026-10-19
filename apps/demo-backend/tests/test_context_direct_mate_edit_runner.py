from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_PATH = WORKSPACE / "scripts/run_context_direct_mate_edit.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_context_direct_mate_edit", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    tmp_path: Path,
    monkeypatch,
    *,
    fail: bool,
    prepare: bool = False,
    displace: bool = False,
):
    module = _load_script()
    source = tmp_path / "source.SLDASM"
    effective = tmp_path / "effective.json"
    executable = tmp_path / "mcp.exe"
    output = tmp_path / "output.SLDASM"
    result = tmp_path / "result.json"
    source.write_bytes(b"immutable-source")
    effective.write_text("{}", encoding="utf-8")
    executable.write_bytes(b"exe")
    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def call_tool(self, name, payload):
            if name == "open_document":
                return {"Document": {"Path": payload["path"]}}
            if name == "resolve_all_lightweight_components":
                return {"Success": True, "RawResolveCode": 0}
            captured.update(payload)
            staging = Path(payload["outputAssemblyPath"])
            staging.write_bytes(b"staging-assembly")
            if fail:
                raise RuntimeError("simulated CAD endpoint failure")
            return {
                "Success": True,
                "ExecutionMode": "direct_existing_component_mate_edit",
                "TargetComponentReinserted": False,
                "TargetComponentExplicitlyDisplaced": bool(
                    payload.get("forceInitialDisplacement")
                ),
            }

        def call_tool_text(self, name, payload):
            return "closed"

    monkeypatch.setattr(module, "McpClient", FakeClient)
    monkeypatch.setattr(
        module,
        "preflight_direct_mate_transaction",
        lambda *args, **kwargs: {"publishAllowed": True, "status": "ready_for_cad_execution"},
    )
    argv = [
            str(SCRIPT_PATH),
            "--source",
            str(source),
            "--effective",
            str(effective),
            "--output",
            str(output),
            "--result",
            str(result),
            "--target",
            "D000",
            "--expected-source-sha256",
            _sha(source),
            "--expected-effective-sha256",
            _sha(effective),
            "--exe",
            str(executable),
            "--preserve-resolved-source-session",
        ]
    if prepare:
        argv.append("--prepare-resolved-source-session")
    if displace:
        argv.append("--displace-target-before-remate")
    monkeypatch.setattr(sys, "argv", argv)
    exit_code = module.main()
    return exit_code, output, result, captured


def test_resolved_session_runner_publishes_only_verified_success(tmp_path, monkeypatch):
    exit_code, output, result, captured = _run(tmp_path, monkeypatch, fail=False)
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert output.read_bytes() == b"staging-assembly"
    assert captured["preserveResolvedSourceSession"] is True
    assert payload["success"] is True
    assert payload["published"] is True
    assert payload["sourceAssemblyUnchanged"] is True
    assert payload["preserveResolvedSourceSession"] is True


def test_resolved_session_runner_archives_failed_staging_copy(tmp_path, monkeypatch):
    exit_code, output, result, captured = _run(tmp_path, monkeypatch, fail=True)
    payload = json.loads(result.read_text(encoding="utf-8"))
    failed = Path(payload["failedArtifactPath"])
    assert exit_code == 2
    assert not output.exists()
    assert failed.read_bytes() == b"staging-assembly"
    assert captured["preserveResolvedSourceSession"] is True
    assert payload["success"] is False
    assert payload["published"] is False
    assert "simulated CAD endpoint failure" in payload["executionError"]


def test_runner_can_prepare_resolved_source_in_same_session(tmp_path, monkeypatch):
    exit_code, _, result, captured = _run(
        tmp_path, monkeypatch, fail=False, prepare=True
    )
    payload = json.loads(result.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured["preserveResolvedSourceSession"] is True
    assert payload["sessionPreparation"]["requested"] is True
    assert payload["sessionPreparation"]["resolved"]["Success"] is True


def test_runner_can_require_non_source_initial_pose(tmp_path, monkeypatch):
    exit_code, _, result, captured = _run(
        tmp_path, monkeypatch, fail=False, prepare=True, displace=True
    )
    payload = json.loads(result.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured["forceInitialDisplacement"] is True
    assert payload["displaceTargetBeforeRemate"] is True
    assert payload["toolResult"]["TargetComponentExplicitlyDisplaced"] is True

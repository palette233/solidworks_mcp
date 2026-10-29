"""Mock MCP timing/error tests. No test launches SolidWorks or real CAD."""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def scan(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("leaf_face_timing_test_script", ROOT / "scripts/build_leaf_face_endpoint_catalog.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    source = tmp_path / "source.SLDASM"
    source.write_bytes(b"unchanged-source-fixture")
    args = argparse.Namespace(
        exe=tmp_path / "mcp.exe", source=source, module="AA00", leaf="base-plate-1",
        output=tmp_path / "leaf.json", base_catalog=None, merged_output=None,
        minimum_face_area=1e-8, maximum_face_count=300,
        include_nonplanar=True, timeout=10.0,
    )
    behavior = {"scan_error": None, "connect_error": None, "cleanup_error": None,
                "close_error": None, "session_restored": True, "missing_tool": False,
                "return_failure": False, "write_output": True}
    calls = []

    class Client:
        def __init__(self, *a, **kw):
            calls.append(("construct", kw))

        def __enter__(self):
            calls.append(("enter", None))
            return self

        def __exit__(self, *a):
            calls.append(("close", None))
            if behavior["close_error"]:
                raise behavior["close_error"]
            return False

        def list_tools(self):
            return [] if behavior["missing_tool"] else [{"name": "build_leaf_face_endpoint_catalog"}]

        def call_tool(self, name, payload):
            calls.append((name, payload))
            if name == "solid_works_connect":
                if behavior["connect_error"]:
                    raise behavior["connect_error"]
                return {}
            if name == "ListDocuments":
                return [{"Path": str(source)}]
            assert name == "BuildLeafFaceEndpointCatalog", "No save/mutation tool is allowed"
            if behavior["scan_error"]:
                raise behavior["scan_error"]
            result = {"EndpointCount": 2}
            if behavior["write_output"]:
                Path(payload["outputPath"]).write_text(json.dumps(result), encoding="utf-8")
            return {"Success": False} if behavior["return_failure"] else result

    def cleanup(client, baseline):
        calls.append(("cleanup", baseline))
        if behavior["cleanup_error"]:
            raise behavior["cleanup_error"]
        return {"sessionRestored": behavior["session_restored"]}

    monkeypatch.setattr(script, "McpClient", Client)
    monkeypatch.setattr(script, "restore_open_document_baseline", cleanup)
    return script, args, behavior, calls


def _timing(args):
    return json.loads(args.output.with_suffix(".timing.json").read_text(encoding="utf-8"))


def test_success_records_separate_phase_timings_without_source_save(scan):
    script, args, _, calls = scan
    assert script.run(args) == 0
    timing = _timing(args)
    assert timing["success"] is True
    assert timing["status"] == "succeeded"
    assert datetime.fromisoformat(timing["startedAtUtc"]).utcoffset().total_seconds() == 0
    assert datetime.fromisoformat(timing["finishedAtUtc"]) >= datetime.fromisoformat(timing["startedAtUtc"])
    for name in ("connect", "scan", "cleanup", "clientClose"):
        assert timing["phaseDurationsSeconds"][name] >= 0
        assert timing["phases"][name]["status"] == "succeeded"
    assert timing["durationSeconds"] >= sum(value or 0 for value in timing["phaseDurationsSeconds"].values())
    assert timing["sourceSaveRequested"] is False
    assert args.source.read_bytes() == b"unchanged-source-fixture"
    payload = next(payload for name, payload in calls if name == "BuildLeafFaceEndpointCatalog")
    assert payload == {"sourceAssemblyPath": str(args.source.resolve()), "moduleToken": "AA00",
                       "leafSelector": "base-plate-1", "outputPath": str(args.output.resolve()),
                       "planarOnly": False, "minimumFaceArea": 1e-8, "maximumFaceCount": 300, "saveJson": True}


def test_connect_failure_is_recorded_and_no_scan_or_cleanup_runs(scan):
    script, args, behavior, calls = scan
    error = RuntimeError("COM attach failed")
    behavior["connect_error"] = error
    with pytest.raises(RuntimeError) as captured:
        script.run(args)
    assert captured.value is error
    timing = _timing(args)
    assert timing["status"] == "failed"
    assert timing["phases"]["connect"]["status"] == "failed"
    assert timing["phaseDurationsSeconds"]["scan"] is None
    assert timing["phaseDurationsSeconds"]["cleanup"] is None
    assert not any(name in {"BuildLeafFaceEndpointCatalog", "cleanup"} for name, _ in calls)


@pytest.mark.parametrize("secondary_error", [None, "cleanup", "close", "both"])
def test_scan_exception_is_not_masked_by_cleanup_or_close(scan, secondary_error):
    script, args, behavior, calls = scan
    original = TimeoutError("bounded scan timed out")
    behavior["scan_error"] = original
    if secondary_error in {"cleanup", "both"}:
        behavior["cleanup_error"] = RuntimeError("cleanup failed too")
    if secondary_error in {"close", "both"}:
        behavior["close_error"] = RuntimeError("client close failed too")
    with pytest.raises(TimeoutError) as captured:
        script.run(args)
    assert captured.value is original
    timing = _timing(args)
    assert timing["success"] is False
    assert timing["errorType"] == "TimeoutError"
    assert timing["error"] == "bounded scan timed out"
    assert timing["phases"]["scan"]["status"] == "failed"
    assert timing["phaseDurationsSeconds"]["cleanup"] >= 0
    assert any(name == "close" for name, _ in calls)


@pytest.mark.parametrize("failure", ["restore_false", "cleanup_exception", "close_exception"])
def test_cleanup_failure_after_successful_scan_cannot_claim_success(scan, failure):
    script, args, behavior, _ = scan
    if failure == "restore_false":
        behavior["session_restored"] = False
    elif failure == "cleanup_exception":
        behavior["cleanup_error"] = RuntimeError("cleanup exception")
    else:
        behavior["close_error"] = RuntimeError("close exception")
    with pytest.raises(RuntimeError):
        script.run(args)
    timing = _timing(args)
    assert timing["status"] == "failed"
    assert timing["success"] is False
    assert timing["phases"]["scan"]["status"] == "succeeded"
    assert args.output.is_file()


@pytest.mark.parametrize("failure", ["missing_tool", "return_failure", "write_output"])
def test_invalid_scan_result_leaves_failed_timing(scan, failure):
    script, args, behavior, _ = scan
    behavior[failure] = False if failure == "write_output" else True
    with pytest.raises(RuntimeError):
        script.run(args)
    timing = _timing(args)
    assert timing["status"] == "failed"
    assert timing["finishedAtUtc"]


@pytest.mark.parametrize("existing", ["catalog", "timing", "merged"])
def test_existing_artifacts_are_never_overwritten_or_start_mcp(scan, existing):
    script, args, _, calls = scan
    if existing == "catalog":
        path = args.output
    elif existing == "timing":
        path = args.output.with_suffix(".timing.json")
    else:
        args.base_catalog = args.source.parent / "base.json"
        args.merged_output = args.source.parent / "merged.json"
        path = args.merged_output
    path.write_bytes(b"existing-do-not-change")
    with pytest.raises(FileExistsError):
        script.run(args)
    assert path.read_bytes() == b"existing-do-not-change"
    assert calls == []


def test_invalid_merge_arguments_get_failure_timing_without_starting_mcp(scan):
    script, args, _, calls = scan
    args.base_catalog = args.source.parent / "base.json"
    with pytest.raises(ValueError):
        script.run(args)
    assert _timing(args)["status"] == "failed"
    assert calls == []


def test_optional_merge_keeps_existing_behavior_and_records_duration(scan, monkeypatch):
    script, args, _, _ = scan
    args.base_catalog = args.source.parent / "base.json"
    args.base_catalog.write_text('{"EndpointCount": 3}', encoding="utf-8")
    args.merged_output = args.source.parent / "merged.json"
    monkeypatch.setattr(script, "merge_face_endpoint_catalogs", lambda base, leaf: {"EndpointCount": base["EndpointCount"] + leaf["EndpointCount"]})
    assert script.run(args) == 0
    assert json.loads(args.merged_output.read_text())["EndpointCount"] == 5
    assert _timing(args)["phaseDurationsSeconds"]["merge"] >= 0


def test_merge_failure_is_recorded_after_scan_and_cleanup(scan, monkeypatch):
    script, args, _, _ = scan
    args.base_catalog = args.source.parent / "base.json"
    args.base_catalog.write_text('{}', encoding="utf-8")
    args.merged_output = args.source.parent / "merged.json"
    error = ValueError("bad merged catalog")
    def fail(*_):
        raise error
    monkeypatch.setattr(script, "merge_face_endpoint_catalogs", fail)
    with pytest.raises(ValueError) as captured:
        script.run(args)
    assert captured.value is error
    timing = _timing(args)
    assert timing["status"] == "failed"
    assert timing["phases"]["merge"]["status"] == "failed"
    assert timing["phases"]["cleanup"]["status"] == "succeeded"

from __future__ import annotations

import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_PATH = WORKSPACE / "scripts/run_global_cad_transaction_packet.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_global_cad_transaction_packet", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _command(strategy: str):
    module = _load_script()
    return module.build_adapter_command(
        {
            "executionStrategy": strategy,
            "outputAssemblyPath": "output.SLDASM",
            "targetModuleToken": "A500",
        },
        execution_source=Path("source.SLDASM"),
        execution_source_sha256="source-sha",
        execution_graph=Path("graph.json"),
        execution_graph_sha256="graph-sha",
        result_path=Path("result.json"),
    )


def test_add_relation_dispatches_direct_edit_adapter():
    command = _command("direct_existing_component_mate_edit")
    assert command[1].endswith("run_context_direct_mate_edit.py")
    assert command[-2:] == ["--target", "A500"]


def test_verify_relation_dispatches_read_only_adapter_with_measurement_target():
    command = _command("read_only_existing_relation_verification")
    assert command[1].endswith("run_context_relation_verify.py")
    assert command[-2:] == ["--target", "A500"]


def test_capture_open_document_baseline_normalizes_paths(monkeypatch):
    module = _load_script()

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def call_tool(self, name, _arguments):
            if name == "solid_works_connect":
                return {"connected": True}
            assert name == "ListDocuments"
            return [
                {"Path": str(WORKSPACE / "demo" / "A.SLDASM")},
                {"path": str(WORKSPACE / "demo" / "A.SLDASM")},
            ]

    monkeypatch.setattr(module, "McpClient", FakeClient)
    baseline = module.capture_open_document_baseline()

    assert baseline["openDocumentCount"] == 1
    assert len(baseline["paths"]) == 1
    assert baseline["paths"][0].endswith("a.sldasm")


def test_restore_packet_document_baseline_reports_packet_cleanup(monkeypatch):
    module = _load_script()
    received = {}

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def call_tool(self, name, _arguments):
            assert name == "solid_works_connect"
            return {"connected": True}

    def fake_restore(_client, baseline_paths):
        received["paths"] = baseline_paths
        return {
            "closedPaths": ["generated.SLDPRT"],
            "errors": [],
            "sessionRestored": True,
        }

    monkeypatch.setattr(module, "McpClient", FakeClient)
    monkeypatch.setattr(module, "restore_open_document_baseline", fake_restore)
    result = module.restore_packet_document_baseline(
        {"paths": ["original.sldasm"], "openDocumentCount": 1}
    )

    assert received["paths"] == {"original.sldasm"}
    assert result == {
        "baselineOpenDocumentCount": 1,
        "closedDocumentPaths": ["generated.SLDPRT"],
        "errors": [],
        "sessionRestoredToBaseline": True,
    }


def test_adapter_self_cleanup_evidence_avoids_redundant_mcp_cleanup():
    module = _load_script()
    result = module.adapter_self_cleanup_result(
        {
            "success": True,
            "outputClosedAfterVerification": True,
            "targetSourceSessionClean": True,
            "toolResult": {
                "Reopened": True,
                "ReopenedMateParametersMatch": True,
            },
        },
        {"paths": ["original.sldasm"], "openDocumentCount": 1},
    )

    assert result["sessionRestoredToBaseline"] is True
    assert result["cleanupMode"] == "adapter_self_cleanup_evidence"
    assert result["errors"] == []


def test_adapter_self_cleanup_requires_all_explicit_invariants():
    module = _load_script()
    assert module.adapter_self_cleanup_result(
        {
            "success": True,
            "outputClosedAfterVerification": False,
            "targetSourceSessionClean": True,
            "toolResult": {
                "Reopened": True,
                "ReopenedMateParametersMatch": True,
            },
        },
        {"paths": [], "openDocumentCount": 0},
    ) is None

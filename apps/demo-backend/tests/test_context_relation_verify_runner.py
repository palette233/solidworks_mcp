from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_PATH = WORKSPACE / "scripts/run_context_relation_verify.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_context_relation_verify", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_read_only_relation_verifier_measures_without_mate_mutation(tmp_path, monkeypatch):
    module = _load_script()
    source = tmp_path / "source.SLDASM"
    graph = tmp_path / "relation.json"
    executable = tmp_path / "mcp.exe"
    output = tmp_path / "output.SLDASM"
    result = tmp_path / "result.json"
    source.write_bytes(b"immutable-checkpoint")
    executable.write_bytes(b"exe")
    graph.write_text(
        json.dumps(
            {
                "Mates": [],
                "PatchAudit": {"operations": []},
                "SemanticAssemblyPlanAudit": {
                    "ValidationRelations": [
                        {
                            "relationName": "距离8",
                            "relationType": 5,
                            "expectedDistanceMeters": 0.05,
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def call_tool(self, name, payload):
            assert name == "VerifyRelationsInAssemblyContextFromMateGraph"
            assert "outputAssemblyPath" not in payload
            return {
                "Success": True,
                "ExecutionMode": "read_only_existing_relation_verification",
                "ValidationResults": [
                    {
                        "RelationName": "距离8",
                        "Passed": True,
                        "MeasuredDistanceMeters": 0.05,
                    }
                ],
            }

    monkeypatch.setattr(module, "McpClient", FakeClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--source",
            str(source),
            "--effective",
            str(graph),
            "--output",
            str(output),
            "--target",
            "A500",
            "--result",
            str(result),
            "--expected-source-sha256",
            _sha(source),
            "--expected-effective-sha256",
            _sha(graph),
            "--exe",
            str(executable),
        ],
    )

    assert module.main() == 0
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert output.read_bytes() == b"immutable-checkpoint"
    assert payload["success"] is True
    assert payload["sourceAssemblyUnchanged"] is True
    assert payload["noMateMutation"] is True
    assert payload["checkpointPublicationMode"] == (
        "filesystem_copy_of_verified_source"
    )
    assert payload["validationResults"][0]["Passed"] is True

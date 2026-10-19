from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project03_ac00_flat_snapshot_increment_graph.py"
SPEC = importlib.util.spec_from_file_location("flat_snapshot_increment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_replaces_ac00_with_fixed_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.SLDASM"
    snapshot.write_bytes(b"assembly")
    source = {
        "Modules": [
            {"ModuleToken": "CTX", "Path": "ctx.SLDASM"},
            {"ModuleToken": "FL9A24D063AC00", "Path": "old.SLDASM"},
        ],
        "Mates": [{"MateName": "old"}],
        "EditPolicy": {"fixedModuleTokens": ["CTX"]},
    }
    result = MODULE.build(source, snapshot, {"success": True, "status": "PASSED"})
    assert result["ModuleCount"] == 2
    assert result["InterModuleMateCount"] == 0
    assert result["Mates"] == []
    target = next(item for item in result["Modules"] if item["ModuleToken"] == MODULE.TARGET_TOKEN)
    assert target["SourceTransform"] == MODULE.IDENTITY
    assert result["EditPolicy"]["caseAnchoredModuleTokens"] == [MODULE.TARGET_TOKEN]
    assert result["SemanticAssemblyPlanAudit"]["flatStaticSnapshot"]["productionReady"] is False


def test_cli_output_parent_can_be_created(tmp_path: Path, monkeypatch) -> None:
    snapshot = tmp_path / "snapshot.SLDASM"
    closure = tmp_path / "closure.json"
    source = tmp_path / "source.json"
    output = tmp_path / "nested" / "effective.json"
    snapshot.write_bytes(b"assembly")
    closure.write_text('{"success": true, "status": "PASSED"}', encoding="utf-8")
    source.write_text(
        '{"Modules":[{"ModuleToken":"FL9A24D063AC00"}],"EditPolicy":{}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--source-effective",
            str(source),
            "--snapshot",
            str(snapshot),
            "--snapshot-closure",
            str(closure),
            "--output",
            str(output),
        ],
    )
    assert MODULE.main() == 0
    assert output.is_file()

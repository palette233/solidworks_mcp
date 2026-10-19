from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/finalize_project03_ac00_hybrid_static_snapshot.py"
SPEC = importlib.util.spec_from_file_location("hybrid_snapshot_finalize", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_hybrid_closure_keeps_static_claim_boundary() -> None:
    graph = {
        "ModuleCount": 34,
        "StaticSnapshotAudit": {
            "sourceLeafInstanceCount": 118,
            "coveredSourceLeafInstanceCount": 118,
        },
    }
    manifest = {"batchCount": 2}
    batches = [{"success": True}, {"success": True}]
    root = {
        "success": True,
        "durationSeconds": 5,
        "toolResult": {
            "Success": True,
            "ComponentStatuses": [
                {"SolvingStateMatches": True},
                {"SolvingStateMatches": True},
            ],
        },
    }
    comparisons = {
        "AC20": {"stable": True, "unstableCount": 0},
        "AC30": {"stable": True, "unstableCount": 0},
        "AC40": {"stable": True, "unstableCount": 0},
    }
    result = MODULE.build(graph, manifest, batches, root, comparisons)
    assert result["success"] is True
    assert result["claims"]["sourceLeafGeometryCoverageComplete"] is True
    assert result["claims"]["motionSemanticsReconstructed"] is False
    assert result["claims"]["productionDynamicClosure"] is False

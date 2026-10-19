from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/finalize_project03_ac00_flat_static_snapshot.py"
SPEC = importlib.util.spec_from_file_location("flat_snapshot_finalize", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_closure_requires_exact_reopened_leaf_pose() -> None:
    transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 2, 3, 1, 0, 0, 0]
    graph = {
        "StaticSnapshotAudit": {
            "leafManifest": [
                {
                    "moduleToken": "L1",
                    "sourceRelativeHierarchyPath": "A/L1",
                    "expectedWorldTransform": transform,
                }
            ]
        }
    }
    run = {
        "success": True,
        "durationSeconds": 1.5,
        "toolResult": {
            "Success": True,
            "ComponentStatuses": [
                {
                    "ModuleToken": "L1",
                    "WorldTransform": transform,
                    "SolvingStateMatches": True,
                    "ConstrainedStatus": 3,
                }
            ],
        },
    }
    result = MODULE.build_closure(graph, run, Path("g.json"), Path("r.json"))
    assert result["success"] is True
    assert result["metrics"]["expectedLeafCount"] == 1
    assert result["claims"]["motionSemanticsReconstructed"] is False


def test_closure_rejects_pose_drift() -> None:
    graph = {
        "StaticSnapshotAudit": {
            "leafManifest": [
                {
                    "moduleToken": "L1",
                    "sourceRelativeHierarchyPath": "L1",
                    "expectedWorldTransform": [0] * 16,
                }
            ]
        }
    }
    run = {
        "success": True,
        "toolResult": {
            "Success": True,
            "ComponentStatuses": [
                {
                    "ModuleToken": "L1",
                    "WorldTransform": [1] + [0] * 15,
                    "SolvingStateMatches": True,
                    "ConstrainedStatus": 3,
                }
            ],
        },
    }
    result = MODULE.build_closure(graph, run, Path("g.json"), Path("r.json"))
    assert result["success"] is False
    assert "one or more leaf poses drifted" in result["blockers"]

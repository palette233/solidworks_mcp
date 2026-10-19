import importlib.util
import argparse
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/run_project02_current_collision_feedback.py"
SPEC = importlib.util.spec_from_file_location("current_collision_feedback", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_focused_collision_batch_keeps_only_complete_collisions():
    result = MODULE.focused_collision_batch(
        {
            "assemblyPath": "x",
            "pairs": [
                {
                    "pair": ["A", "B"],
                    "exactCheckComplete": True,
                    "failedBodyPairCount": 0,
                    "hasInterference": False,
                    "interferingBodyPairCount": 0,
                },
                {
                    "pair": ["C", "D"],
                    "exactCheckComplete": True,
                    "failedBodyPairCount": 0,
                    "hasInterference": True,
                    "interferingBodyPairCount": 1,
                },
            ],
        }
    )
    assert result["requestedPairCount"] == 1
    assert result["completedPairCount"] == 1
    assert result["pairs"][0]["pair"] == ["C", "D"]


def test_durable_replay_layout_detection_rejects_selection_status_stub():
    assert not MODULE.has_durable_replay_layout(
        {"caseId": "project02", "status": "preview_ready"}
    )
    assert MODULE.has_durable_replay_layout(
        {"components": [{"componentName": "A500", "layout2d": {"x": 0, "y": 0}}]}
    )
    assert MODULE.has_durable_replay_layout(
        {
            "steps": [
                {
                    "tool": "apply_captured_common_base_layout",
                    "payload": {"components": [{"componentName": "A500"}]},
                }
            ]
        }
    )


def test_write_failure_report_persists_blocker(tmp_path):
    args = argparse.Namespace(batch=tmp_path / "batch.json")
    args.batch.write_text("{}", encoding="utf-8")
    try:
        raise RuntimeError("no feasible layout")
    except RuntimeError as exc:
        path = MODULE.write_failure_report(
            tmp_path,
            args=args,
            feedback={"confirmedCollisionPairs": [{"pair": ["A300", "A700"]}]},
            metadata={"applied": True},
            artifacts={"request": "request.json"},
            error=exc,
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["status"] == "FEEDBACK_SOLVE_NO_FEASIBLE_LAYOUT"
    assert document["errorType"] == "RuntimeError"
    assert document["confirmedCollisionPairCount"] == 1
    assert "do not Replay" in document["nextGate"]

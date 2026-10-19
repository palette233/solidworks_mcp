from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from project_saved_replay_poses import (
    _target_normal_delta,
    load_layouts_from_replay_artifact,
)


class ProjectSavedReplayPoseTests(unittest.TestCase):
    def test_projection_report_can_be_used_as_next_iteration_baseline(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            replay = directory / "replay.json"
            replay.write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "componentName": "A300",
                                "layout2d": {
                                    "x": -0.45,
                                    "y": 0.07,
                                    "thetaDegrees": 180.0,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            projection = directory / "projection.json"
            projection.write_text(
                json.dumps(
                    {
                        "baselineReplay": str(replay),
                        "diagnostics": [
                            {
                                "componentName": "A300",
                                "deltaLayoutMeters": [0.05, -0.01],
                                "thetaDeltaDegrees": 0.0,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            recovered = load_layouts_from_replay_artifact(projection)

        self.assertAlmostEqual(recovered["A300"]["x"], -0.40)
        self.assertAlmostEqual(recovered["A300"]["y"], 0.06)
        self.assertAlmostEqual(recovered["A300"]["thetaDegrees"], 180.0)

    def test_changed_normal_offset_is_reconstructed_from_source_pose(self):
        component = {
            "sourceTransform": [
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.153,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
            ],
            "bottomCenterWorld": [0.0, 0.018, 0.0],
        }

        delta, inferred = _target_normal_delta(
            [0.0, 0.135, 0.0],
            component,
            {"normalOffsetMeters": 0.0},
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        )

        self.assertAlmostEqual(inferred, 0.018)
        self.assertAlmostEqual(delta, 0.0)

    def test_unchanged_normal_offset_does_not_move_saved_pose(self):
        component = {
            "sourceTransform": [
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.153,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
            ],
            "bottomCenterWorld": [0.0, 0.018, 0.0],
        }

        delta, inferred = _target_normal_delta(
            [0.0, 0.135, 0.0],
            component,
            {"normalOffsetMeters": 0.018},
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        )

        self.assertAlmostEqual(inferred, 0.018)
        self.assertAlmostEqual(delta, 0.018)

    def test_source_pose_is_preserved_when_target_matches_captured_bottom_height(self):
        component = {
            "sourceTransform": [
                1.0, 0.0, 0.0,
                0.0, 1.0, 0.0,
                0.0, 0.0, 1.0,
                0.0, 0.153, 0.0,
                1.0, 0.0, 0.0, 0.0,
            ],
            "bottomCenterWorld": [0.0, 0.018, 0.0],
        }

        delta, inferred = _target_normal_delta(
            [0.0, 0.153, 0.0],
            component,
            {"normalOffsetMeters": 0.018},
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        )

        self.assertAlmostEqual(inferred, 0.018)
        self.assertAlmostEqual(delta, 0.0)


if __name__ == "__main__":
    unittest.main()

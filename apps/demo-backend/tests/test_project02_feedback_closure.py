from __future__ import annotations

from scripts.summarize_project02_feedback_closure import (
    module_token,
    pose_map,
    unchanged_tokens,
)


def _pose(name: str, translation: float = 0.0) -> dict:
    return {
        "Name": name,
        "Transform": [1, 0, 0, 0, 1, 0, 0, 0, 1, translation, 0, 0, 1, 0, 0, 0],
    }


def test_static_a100_replacement_uses_a100_module_identity():
    assert module_token("A100_WITH_A150_SLOT0_RIGID_V3-1") == "A100"
    assert module_token("FL9A24D062A600.001-1") == "A600"


def test_unchanged_tokens_requires_same_transform():
    reference = [_pose("FL9A24D062A600.001-1"), _pose("FL9A24D062A800.001-1")]
    current = {
        "components": [
            _pose("FL9A24D062A600.001-1"),
            _pose("FL9A24D062A800.001-1", 0.01),
        ]
    }

    assert unchanged_tokens(current, reference) == {"A600"}
    assert set(pose_map(current)) == {"A600", "A800"}

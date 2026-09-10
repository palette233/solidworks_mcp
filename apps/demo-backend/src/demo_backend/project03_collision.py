"""Saved-Replay broad-phase and strict-pair audit for Project03."""

from __future__ import annotations

from typing import Any

from .project01_collision import build_project01_replay_screening


def build_project03_replay_screening(
    occupancy: dict[str, Any],
    replay_layout: dict[str, Any],
    replay_result: dict[str, Any],
    source_poses: dict[str, Any],
) -> dict[str, Any]:
    return build_project01_replay_screening(
        occupancy,
        replay_layout,
        replay_result,
        source_poses,
        project_id="project03",
        code_marker="D063",
    )

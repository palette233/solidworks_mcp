"""Materialize an approved Project03 layout as a ten-module Replay document."""

from __future__ import annotations

from typing import Any

from .project01_replay import build_project01_replay_layout


def build_project03_replay_layout(
    selected: dict[str, Any],
    occupancy: dict[str, Any],
    top_level_poses: dict[str, Any],
) -> dict[str, Any]:
    return build_project01_replay_layout(
        selected,
        occupancy,
        top_level_poses,
        project_id="project03",
        code_marker="D063",
        expected_component_count=10,
        base_component_name="FL9A24D063AE00.001-1",
    )

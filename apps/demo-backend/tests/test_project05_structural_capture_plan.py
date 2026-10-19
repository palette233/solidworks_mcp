from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project05_structural_capture_plan import build_project05_structural_capture_plan


def test_capture_plan_is_resumable_and_blocks_on_missing_structural_modules(tmp_path: Path) -> None:
    capture_dir = tmp_path / "demo/layout_previews"
    capture_dir.mkdir(parents=True)
    for code in ("K000", "F000"):
        (capture_dir / f"project05_{code.lower()}_world_leaf_envelopes.json").write_text(
            json.dumps({"coverageComplete": True, "bodyCount": 3, "bodies": []}), encoding="utf-8"
        )
    readiness = {"modules": [
        {"cadId": f"FL9C254098{code}.001", "expectedFileName": f"{code}.SLDASM", "resolvedCadPath": f"C:/{code}.SLDASM"}
        for code in ("A000", "E000", "D000", "K000", "B000", "Z000", "F000", "G000", "M000", "P000")
    ] + [{"cadId": "FL9C251093N000.001", "expectedFileName": "N000.SLDASM", "resolvedCadPath": "C:/N000.SLDASM"}]}
    result = build_project05_structural_capture_plan(tmp_path, readiness)
    assert result["completeCaptureCount"] == 2
    assert "A000" in result["pendingCaptureCodes"]
    assert "Z000" in result["pendingCaptureCodes"]
    assert result["releaseGate"]["coarseTop3SolveAllowed"] is False

import json
from pathlib import Path

from demo_backend.dynamic_engineering_acquisition import (
    audit_a100_limit_source,
    audit_a700_state_sources,
)


def snapshot(path: Path, *, a730_x: float) -> None:
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]

    def row(name, translation):
        return {
            "relativeHierarchyPath": name,
            "depthFromModuleRoot": 0 if name == "@root" else 1,
            "Transform": identity + translation + [1, 0, 0, 0],
            "ReferencedConfiguration": "Default",
            "SolvingStateName": "rigid",
        }

    path.write_text(
        json.dumps(
            {
                "components": [
                    row("@root", [10, 20, 30]),
                    row("A710", [10.1, 20, 30]),
                    row("A720", [10.2, 20, 30]),
                    row("A730", [10 + a730_x, 20, 30]),
                ]
            }
        ),
        encoding="utf-8",
    )


def test_a700_rejects_three_labels_when_geometry_is_duplicated(tmp_path: Path):
    pose = tmp_path / "same.json"
    assembly = tmp_path / "state.SLDASM"
    assembly.write_bytes(b"cad")
    snapshot(pose, a730_x=0.3)
    result = audit_a700_state_sources(
        [
            {"stateId": state, "snapshotPath": pose, "assemblyPath": assembly, "sourceAuditAccepted": True}
            for state in ("cleaning", "weighing", "maintenance")
        ]
    )
    assert result["complete"] is False
    assert result["acceptedDistinctStateCount"] == 1


def test_a700_accepts_three_distinct_module_local_states(tmp_path: Path):
    assembly = tmp_path / "state.SLDASM"
    assembly.write_bytes(b"cad")
    candidates = []
    for state, position in zip(("cleaning", "weighing", "maintenance"), (0.3, 0.4, 0.5)):
        pose = tmp_path / f"{state}.json"
        snapshot(pose, a730_x=position)
        candidates.append({"stateId": state, "snapshotPath": pose, "assemblyPath": assembly, "sourceAuditAccepted": True})
    result = audit_a700_state_sources(candidates)
    assert result["complete"] is True
    assert result["acceptedDistinctStateCount"] == 3


def test_a100_rejects_ordinary_distance_mate_as_limit():
    result = audit_a100_limit_source(
        {
            "mateType": "swMateDISTANCE",
            "limitKind": "limit-mate",
            "minimumMeters": 0.0,
            "maximumMeters": 0.5,
            "authority": "measured-limits",
            "sourceReference": "measurement-001",
        }
    )
    assert result["accepted"] is False
    assert "普通距离配合不能作为限位配合" in result["reasons"]


def test_a100_accepts_traceable_mechanical_range():
    result = audit_a100_limit_source(
        {
            "mateType": "",
            "limitKind": "mechanical-stop",
            "minimumMeters": 0.0,
            "maximumMeters": 0.5,
            "authority": "measured-limits",
            "sourceReference": "measurement-001",
        }
    )
    assert result["accepted"] is True

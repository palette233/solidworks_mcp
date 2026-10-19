from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_backend.brep_evidence_cache import (
    build_cache_entry,
    build_pair_fingerprint,
    validate_cache_entry,
)


def pose(name: str, path: Path, x: float, configuration: str = "Default"):
    return {
        "name": name,
        "path": str(path),
        "translation": [x, 0.0, 0.0],
        "xAxis": [1.0, 0.0, 0.0],
        "yAxis": [0.0, 1.0, 0.0],
        "zAxis": [0.0, 0.0, 1.0],
        "referencedConfiguration": configuration,
    }


def accepted_evidence():
    return {
        "ExactCheckComplete": True,
        "FailedBodyPairCount": 0,
        "HasInterference": False,
    }


def cache(tmp_path: Path):
    first_file = tmp_path / "first.SLDASM"
    second_file = tmp_path / "second.SLDASM"
    evidence_path = tmp_path / "evidence.json"
    first_file.write_bytes(b"first")
    second_file.write_bytes(b"second")
    evidence = accepted_evidence()
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    fingerprint = build_pair_fingerprint(
        pose("A-1", first_file, 0.0),
        pose("B-1", second_file, 1.0),
        policy="zeroInterference",
    )
    return first_file, second_file, evidence_path, evidence, fingerprint, build_cache_entry(
        fingerprint, evidence_path, evidence
    )


def test_cache_reuses_after_common_global_translation(tmp_path: Path):
    first_file, second_file, _, evidence, fingerprint, entry = cache(tmp_path)
    shifted = build_pair_fingerprint(
        pose("A-1", first_file, 5.0),
        pose("B-1", second_file, 6.0),
        policy="zeroInterference",
    )
    assert shifted["cacheKey"] == fingerprint["cacheKey"]
    assert validate_cache_entry(entry, shifted, evidence)["cacheReusable"] is True


def test_runtime_instance_suffix_change_does_not_invalidate_geometry_cache(
    tmp_path: Path,
):
    first_file, second_file, _, evidence, fingerprint, entry = cache(tmp_path)
    renamed = build_pair_fingerprint(
        pose("A-17", first_file, 0.0),
        pose("B-3", second_file, 1.0),
        policy="zeroInterference",
    )
    assert renamed["sources"][0]["componentName"] != fingerprint["sources"][0]["componentName"]
    assert renamed["cacheKey"] == fingerprint["cacheKey"]
    assert validate_cache_entry(entry, renamed, evidence)["cacheReusable"] is True


def test_identical_source_pair_is_stable_when_instance_names_swap(tmp_path: Path):
    shared = tmp_path / "shared.SLDASM"
    shared.write_bytes(b"shared")
    first = build_pair_fingerprint(
        pose("shared-1", shared, 0.0),
        pose("shared-2", shared, 2.0),
        policy="zeroInterference",
    )
    swapped = build_pair_fingerprint(
        pose("shared-2", shared, 2.0),
        pose("shared-1", shared, 0.0),
        policy="zeroInterference",
    )
    assert swapped["cacheKey"] == first["cacheKey"]


def test_relative_motion_invalidates_cache(tmp_path: Path):
    first_file, second_file, _, evidence, _, entry = cache(tmp_path)
    moved = build_pair_fingerprint(
        pose("A-1", first_file, 0.0),
        pose("B-1", second_file, 1.001),
        policy="zeroInterference",
    )
    result = validate_cache_entry(entry, moved, evidence)
    assert result["cacheReusable"] is False
    assert "fingerprint changed" in result["reasons"][0]


@pytest.mark.parametrize("change", ["source", "configuration", "policy"])
def test_geometry_configuration_or_policy_change_invalidates(tmp_path: Path, change: str):
    first_file, second_file, _, evidence, _, entry = cache(tmp_path)
    configuration = "Default"
    policy = "zeroInterference"
    if change == "source":
        first_file.write_bytes(b"changed")
    elif change == "configuration":
        configuration = "Alt"
    else:
        policy = "noNewInterferenceOverAcceptedBaseline"
    current = build_pair_fingerprint(
        pose("A-1", first_file, 0.0, configuration),
        pose("B-1", second_file, 1.0),
        policy=policy,
    )
    assert validate_cache_entry(entry, current, evidence)["cacheReusable"] is False


def test_rejects_incomplete_or_tampered_evidence(tmp_path: Path):
    _, _, evidence_path, evidence, fingerprint, entry = cache(tmp_path)
    incomplete = {"ExactCheckComplete": False, "HasInterference": False}
    assert validate_cache_entry(entry, fingerprint, incomplete)["cacheReusable"] is False
    evidence_path.write_text("{}", encoding="utf-8")
    assert validate_cache_entry(entry, fingerprint, evidence)["cacheReusable"] is False


def test_only_accepted_evidence_can_enter_cache(tmp_path: Path):
    first_file = tmp_path / "a.SLDASM"
    second_file = tmp_path / "b.SLDASM"
    evidence_path = tmp_path / "evidence.json"
    first_file.write_bytes(b"a")
    second_file.write_bytes(b"b")
    evidence_path.write_text("{}", encoding="utf-8")
    fingerprint = build_pair_fingerprint(
        pose("A", first_file, 0.0), pose("B", second_file, 1.0), policy="zeroInterference"
    )
    with pytest.raises(ValueError):
        build_cache_entry(fingerprint, evidence_path, {"ExactCheckComplete": False})


def test_effective_exact_evidence_with_resolved_official_fallback_is_cacheable(
    tmp_path: Path,
):
    first_file = tmp_path / "a.SLDASM"
    second_file = tmp_path / "b.SLDASM"
    evidence_path = tmp_path / "effective.json"
    first_file.write_bytes(b"a")
    second_file.write_bytes(b"b")
    evidence = {
        "ExactCheckComplete": False,
        "EffectiveExactCheckComplete": True,
        "FailedBodyPairCount": 1,
        "HasInterference": True,
        "Acceptance": {
            "Accepted": True,
            "CandidateFailureFallback": {"Resolved": True},
        },
    }
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    fingerprint = build_pair_fingerprint(
        pose("A", first_file, 0.0),
        pose("B", second_file, 1.0),
        policy="noNewInterferenceOverAcceptedBaseline",
    )
    entry = build_cache_entry(fingerprint, evidence_path, evidence)
    assert validate_cache_entry(entry, fingerprint, evidence)["cacheReusable"] is True

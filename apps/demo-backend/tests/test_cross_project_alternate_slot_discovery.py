import json
import re
from pathlib import Path

from demo_backend.cross_project_alternate_slot_discovery import (
    build_alternate_slot_discovery,
)


ROOT = Path(__file__).resolve().parents[3]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _evidence_catalogs():
    release_root = ROOT / "demo/global_assembly_catalog/releases"
    pattern = re.compile(r"^relation-v\d+-project\d+-")
    paths = []
    for directory in release_root.iterdir():
        path = directory / "global_module_catalog.json"
        if not pattern.match(directory.name) or not path.is_file():
            continue
        paths.append(path)
    catalogs = [
        _read(ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json")
    ]
    seen = {catalogs[0]["catalogDigest"]}
    for path in sorted(paths):
        catalog = _read(path)
        digest = catalog["catalogDigest"]
        if digest in seen:
            continue
        seen.add(digest)
        catalogs.append(catalog)
    return catalogs


def test_real_catalog_discovers_the_new_a600_slot_without_guessing_unregistered_geometry():
    matrix = _read(
        ROOT
        / "demo/cross_project_substitution/coverage-v1/"
        "cross_project_candidate_matrix.json"
    )
    report = build_alternate_slot_discovery(
        matrix, evidence_catalogs=_evidence_catalogs()
    )

    assert report["scannedDirectionalPairCount"] == 56
    counts = report["statusCounts"]
    assert sum(counts.values()) == report["scannedDirectionalPairCount"]
    assert counts["registered_alternate_slot_ready"] == 2
    assert counts["registered_alternate_slot_needs_geometry_review"] == 0
    # New immutable relation releases may legitimately expose additional
    # registered slots.  They must remain explicit incompatible results rather
    # than being hidden as "no slot" or guessed into a ready relation.
    assert counts["registered_alternate_slots_incompatible"] >= 1
    assert report["policy"]["unregisteredGeometryInferred"] is False


def test_project03_ah00_can_use_the_registered_a600_operation_side_slot():
    matrix = _read(
        ROOT
        / "demo/cross_project_substitution/coverage-v1/"
        "cross_project_candidate_matrix.json"
    )
    report = build_alternate_slot_discovery(
        matrix, evidence_catalogs=_evidence_catalogs()
    )
    row = next(
        item
        for item in report["rows"]
        if item["sourceProjectIds"] == ["project03"]
        and item["sourceModuleTokens"] == ["AH00"]
        and item["targetProjectIds"] == ["project02"]
        and item["targetModuleTokens"] == ["A500"]
    )

    assert row["status"] == "registered_alternate_slot_ready"
    assert row["targetBaseAliases"][0]["moduleToken"] == "A600"
    assert row["readyAlternateSlotCount"] == 1
    assert row["alternateSlotAssessments"][0]["blockers"] == []

#!/usr/bin/env python3
"""Import the verified AA00/AF00 fixed-base exact result into the live cache."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.brep_evidence_cache import (  # noqa: E402
    build_cache_entry,
    build_pair_fingerprint,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _component(payload: dict, token: str) -> dict:
    return next(
        row
        for row in payload.get("components") or []
        if token in str(row.get("Name") or row.get("name") or "")
    )


def main() -> int:
    root = WORKSPACE / "demo/semantic_ports"
    job_root = root / "project03_live_adapter_full_jobs/project03-job-acc1cd320f35"
    current_poses_path = (
        job_root / "collision-gates/step-07-ab00/attempt2-poses.json"
    )
    reference_poses_path = (
        root / "project03_full_hybrid_static_v1/context_before_top_level_poses.json"
    )
    exact_path = root / "project03_full_hybrid_static_v1/interference_exact.json"
    cache_path = (
        root
        / "project03_live_adapter_four_step_jobs/pair_brep_cache_manifest_v3.json"
    )
    output_dir = root / "project03_live_adapter_full_jobs/independent_collision_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_evidence_path = output_dir / "AA00__AF00_exact_reused.json"
    audit_path = output_dir / "AA00__AF00_cache_import.json"

    current = _load(current_poses_path)
    reference = _load(reference_poses_path)
    current_fingerprint = build_pair_fingerprint(
        _component(current, "AA00"),
        _component(current, "AF00"),
        policy="zeroInterference",
    )
    reference_fingerprint = build_pair_fingerprint(
        _component(reference, "AA00"),
        _component(reference, "AF00"),
        policy="zeroInterference",
    )
    fingerprints_match = (
        current_fingerprint["cacheKey"] == reference_fingerprint["cacheKey"]
    )
    exact_payload = _load(exact_path)
    exact_row = next(
        row
        for row in exact_payload.get("exactChecks") or []
        if set(row.get("pair") or [])
        == {"FL9A24D063AA00.001-1", "FL9A24D063AF00.001-1"}
    )
    exact_result = dict(exact_row["result"])
    exact_accepted = (
        exact_result.get("ExactCheckComplete") is True
        and int(exact_result.get("FailedBodyPairCount") or 0) == 0
        and exact_result.get("HasInterference") is False
    )
    if not fingerprints_match or not exact_accepted:
        raise RuntimeError(
            "AA00/AF00 prior exact result cannot be reused for the final assembly pose."
        )
    exact_result["ReuseProvenance"] = {
        "sourceExactBatchPath": str(exact_path),
        "sourcePairDurationSeconds": float(
            (exact_row.get("timing") or {}).get("durationSeconds") or 0.0
        ),
        "currentPosePath": str(current_poses_path),
        "referencePosePath": str(reference_poses_path),
        "fingerprintsMatch": True,
    }
    normalized_evidence_path.write_text(
        json.dumps(exact_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    entry = {
        "pair": ["FL9A24D063AA00.001-1", "FL9A24D063AF00.001-1"],
        **build_cache_entry(
            current_fingerprint, normalized_evidence_path, exact_result
        ),
    }
    manifest = _load(cache_path)
    by_key = {
        str(row.get("cacheKey")): row for row in manifest.get("entries") or []
    }
    by_key[entry["cacheKey"]] = entry
    manifest["entries"] = list(by_key.values())
    manifest["entryCount"] = len(manifest["entries"])
    manifest["generatedAt"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(cache_path)
    audit = {
        "schemaVersion": "project03-fixed-base-pair-cache-import/v1",
        "success": True,
        "pair": entry["pair"],
        "fingerprintsMatch": fingerprints_match,
        "cacheKey": entry["cacheKey"],
        "exactResultAccepted": exact_accepted,
        "sourceExactDurationSeconds": float(
            (exact_row.get("timing") or {}).get("durationSeconds") or 0.0
        ),
        "sourceExactEvidencePath": str(exact_path),
        "normalizedEvidencePath": str(normalized_evidence_path),
        "cacheManifestPath": str(cache_path),
    }
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reuse prior full-static exact pairs after strict current-pose fingerprint checks."""

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


TOKENS = ("AI00", "AE00", "AG00", "AD00", "AJ00", "AH00")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _component(payload: dict, token: str) -> dict:
    return next(
        row
        for row in payload.get("components") or []
        if token in str(row.get("Name") or row.get("name") or "")
    )


def _pair_token(name: str) -> str:
    return next(
        token
        for token in ("AA00", *TOKENS)
        if token in name
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
    closure_path = root / "project03_full_hybrid_static_v1/interference_closure.json"
    cache_path = (
        root
        / "project03_live_adapter_four_step_jobs/pair_brep_cache_manifest_v3.json"
    )
    output_dir = root / "project03_live_adapter_full_jobs/independent_collision_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    current = _load(current_poses_path)
    reference = _load(reference_poses_path)
    exact = _load(exact_path)
    closure = _load(closure_path)
    comparisons = {
        frozenset(_pair_token(name) for name in row.get("pair") or []): row
        for row in (closure.get("collisionResult") or {}).get(
            "pairComparisons", []
        )
        if len(row.get("pair") or []) == 2
        and all(any(token in name for token in ("AA00", *TOKENS)) for name in row["pair"])
    }
    exact_rows = {
        frozenset(_pair_token(name) for name in row.get("pair") or []): row
        for row in exact.get("exactChecks") or []
        if len(row.get("pair") or []) == 2
        and all(any(token in name for token in ("AA00", *TOKENS)) for name in row["pair"])
    }
    manifest = _load(cache_path)
    by_key = {
        str(row.get("cacheKey")): row for row in manifest.get("entries") or []
    }
    imported = []
    for token in TOKENS:
        key = frozenset(("AA00", token))
        comparison = comparisons[key]
        exact_row = exact_rows[key]
        acceptance = comparison.get("acceptance") or {}
        baseline_value = (comparison.get("evidence") or {}).get(
            "prototypeBaseline"
        )
        baseline_path = Path(str(baseline_value)).resolve() if baseline_value else None
        policy = (
            "noNewInterferenceOverAcceptedBaseline"
            if baseline_path
            else "zeroInterference"
        )
        current_fingerprint = build_pair_fingerprint(
            _component(current, "AA00"),
            _component(current, token),
            policy=policy,
            baseline_path=baseline_path,
        )
        reference_fingerprint = build_pair_fingerprint(
            _component(reference, "AA00"),
            _component(reference, token),
            policy=policy,
            baseline_path=baseline_path,
        )
        fingerprints_match = (
            current_fingerprint["cacheKey"]
            == reference_fingerprint["cacheKey"]
        )
        accepted = acceptance.get("accepted") is True
        if not fingerprints_match or not accepted:
            raise RuntimeError(
                f"Prior exact pair AA00/{token} cannot be reused: "
                f"fingerprintsMatch={fingerprints_match}, accepted={accepted}"
            )
        normalized = dict(exact_row["result"])
        normalized["EffectiveExactCheckComplete"] = (
            acceptance.get("effectiveExactCheckComplete") is True
        )
        normalized["Acceptance"] = {
            "Accepted": True,
            "Policy": policy,
            "CandidateFailureFallback": acceptance.get(
                "candidateFailureFallback"
            ),
            "PriorClosureAcceptance": acceptance,
        }
        normalized["ReuseProvenance"] = {
            "sourceExactBatchPath": str(exact_path),
            "sourceClosurePath": str(closure_path),
            "sourcePairDurationSeconds": float(
                (exact_row.get("timing") or {}).get("durationSeconds") or 0.0
            ),
            "currentPosePath": str(current_poses_path),
            "referencePosePath": str(reference_poses_path),
            "fingerprintsMatch": True,
        }
        evidence_path = output_dir / f"AA00__{token}_exact_reused.json"
        evidence_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        entry = {
            "pair": list(exact_row["pair"]),
            **build_cache_entry(current_fingerprint, evidence_path, normalized),
        }
        by_key[entry["cacheKey"]] = entry
        imported.append(
            {
                "pair": entry["pair"],
                "cacheKey": entry["cacheKey"],
                "policy": policy,
                "baselinePath": str(baseline_path) if baseline_path else None,
                "fingerprintsMatch": True,
                "sourceExactDurationSeconds": float(
                    (exact_row.get("timing") or {}).get("durationSeconds") or 0.0
                ),
                "normalizedEvidencePath": str(evidence_path),
            }
        )

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
        "schemaVersion": "project03-prior-full-collision-cache-import/v1",
        "success": True,
        "importedPairCount": len(imported),
        "pairs": imported,
        "cacheManifestPath": str(cache_path),
        "reuseRule": (
            "Only same source hashes, configurations, relative pose, policy and "
            "prototype-baseline hash may reuse the prior exact result."
        ),
    }
    output = output_dir / "prior_full_collision_cache_import.json"
    output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

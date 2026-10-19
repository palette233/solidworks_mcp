from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "apps/demo-backend/src"))

from demo_backend.brep_evidence_cache import build_cache_entry, build_pair_fingerprint


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_pair(values: list[str]) -> tuple[str, str]:
    return tuple(sorted((str(values[0]), str(values[1])), key=str.casefold))


def module_token(value: str) -> str:
    upper = str(value).upper()
    if upper.startswith("T401"):
        return "T401"
    for token in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800"):
        if token in upper:
            return token
    return upper


def normalize_policy(policy: str, baseline_path: str | None) -> str:
    if baseline_path:
        return "noNewInterferenceOverAcceptedBaseline"
    return policy or "zeroInterference"


def batch_row_for_pair(batch_path: Path | None, pair: list[str]) -> dict:
    if batch_path is None or not batch_path.is_file():
        return {}
    wanted = canonical_pair(pair)
    rows = load(batch_path).get("pairs") or []
    exact = next(
        (
            row
            for row in rows
            if len(row.get("pair") or []) == 2
            and canonical_pair([str(value) for value in row["pair"]]) == wanted
        ),
        {},
    )
    if exact:
        return exact
    wanted_tokens = sorted(module_token(value) for value in pair)
    token_matches = [
        row
        for row in rows
        if len(row.get("pair") or []) == 2
        and sorted(module_token(str(value)) for value in row["pair"]) == wanted_tokens
    ]
    return token_matches[0] if len(token_matches) == 1 else {}


def closure_exact_rows(closure_path: Path) -> list[dict]:
    closure = load(closure_path)
    rows = []
    for row in (closure.get("interferenceGate") or {}).get("pairs") or []:
        pair = [str(value) for value in row.get("pair") or []]
        if len(pair) != 2 or row.get("accepted") is not True:
            continue
        if row.get("acceptancePolicy") == "strictTopLevelAabbSeparated":
            continue
        batch_path = Path(str(row.get("batchEvidencePath") or "")).resolve()
        batch_row = batch_row_for_pair(batch_path if batch_path.is_file() else None, pair)
        acceptance = batch_row.get("acceptance") or {}
        detail_path = Path(
            str(
                row.get("detailEvidencePath")
                or row.get("candidateDetailPath")
                or batch_row.get("outputPath")
                or ""
            )
        ).resolve()
        baseline_path = str(
            row.get("prototypeBaselineDetailPath")
            or acceptance.get("baselinePath")
            or ""
        ) or None
        rows.append(
            {
                "pair": pair,
                "accepted": True,
                "policy": normalize_policy(str(row.get("acceptancePolicy") or ""), baseline_path),
                "reportedPolicy": row.get("acceptancePolicy"),
                "baselinePath": baseline_path,
                "detailPath": detail_path,
                "batchEvidencePath": str(batch_path) if batch_path.is_file() else None,
                "candidateFailureFallback": row.get("candidateFailureFallback")
                or acceptance.get("candidateFailureFallback"),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build versioned pair-local cache entries from accepted exact B-rep batches."
    )
    parser.add_argument("--poses", type=Path, required=True)
    parser.add_argument("--batch", type=Path, action="append", default=[])
    parser.add_argument(
        "--closure",
        type=Path,
        help="Also import every accepted exact pair from a full-machine closure.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pose_payload = load(args.poses)
    poses = {
        str(row.get("Name") or row.get("name")): row
        for row in pose_payload.get("components") or []
    }
    entries = []
    rejected = []
    normalized_dir = args.output.parent / "normalized_pair_evidence"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for batch_path in args.batch:
        batch = load(batch_path)
        for row in batch.get("pairs") or []:
            pair = [str(value) for value in row.get("pair") or []]
            acceptance = row.get("acceptance") or {}
            if len(pair) != 2 or acceptance.get("accepted") is not True:
                rejected.append({"pair": pair, "reason": "batch row is not accepted"})
                continue
            if pair[0] not in poses or pair[1] not in poses:
                rejected.append({"pair": pair, "reason": "pair is absent from pose catalog"})
                continue
            detail_path = Path(str(row.get("outputPath") or ""))
            if not detail_path.is_file():
                rejected.append({"pair": pair, "reason": "exact detail is missing"})
                continue
            detail = load(detail_path)
            detail["Acceptance"] = {
                "Accepted": True,
                "Policy": acceptance.get("policy"),
                "BaselinePath": acceptance.get("baselinePath"),
            }
            normalized_path = normalized_dir / (
                "__".join(value.replace("/", "_").replace("\\", "_") for value in sorted(pair))
                + ".json"
            )
            normalized_path.write_text(
                json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            fingerprint = build_pair_fingerprint(
                poses[pair[0]],
                poses[pair[1]],
                policy=str(acceptance.get("policy") or "zeroInterference"),
                baseline_path=acceptance.get("baselinePath"),
            )
            entries.append(
                {
                    "pair": pair,
                    "batchEvidencePath": str(batch_path.resolve()),
                    **build_cache_entry(fingerprint, normalized_path, detail),
                }
            )

    if args.closure:
        for row in closure_exact_rows(args.closure):
            pair = row["pair"]
            if pair[0] not in poses or pair[1] not in poses:
                rejected.append({"pair": pair, "reason": "pair is absent from pose catalog"})
                continue
            detail_path = row["detailPath"]
            if not detail_path.is_file():
                rejected.append({"pair": pair, "reason": "closure exact detail is missing"})
                continue
            detail = load(detail_path)
            detail["EffectiveExactCheckComplete"] = True
            detail["Acceptance"] = {
                "Accepted": True,
                "Policy": row["reportedPolicy"],
                "BaselinePath": row["baselinePath"],
                "CandidateFailureFallback": row["candidateFailureFallback"],
            }
            normalized_path = normalized_dir / (
                "__".join(value.replace("/", "_").replace("\\", "_") for value in sorted(pair))
                + ".json"
            )
            normalized_path.write_text(
                json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            fingerprint = build_pair_fingerprint(
                poses[pair[0]],
                poses[pair[1]],
                policy=row["policy"],
                baseline_path=row["baselinePath"],
            )
            entries.append(
                {
                    "pair": pair,
                    "batchEvidencePath": row["batchEvidencePath"],
                    "closureEvidencePath": str(args.closure.resolve()),
                    **build_cache_entry(fingerprint, normalized_path, detail),
                }
            )

    deduplicated = {str(row["cacheKey"]): row for row in entries}
    entries = list(deduplicated.values())

    payload = {
        "schemaVersion": "pair-brep-cache-manifest/v2",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "poseCatalogPath": str(args.poses.resolve()),
        "entryCount": len(entries),
        "rejectedCount": len(rejected),
        "entries": entries,
        "rejected": rejected,
        "invalidationRule": (
            "Rebuild only when source CAD hash, referenced configuration, pair-relative pose, "
            "acceptance policy, baseline hash, checker version, or evidence hash changes."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "entryCount": len(entries), "rejected": rejected}, ensure_ascii=False))
    return 0 if not rejected else 2


if __name__ == "__main__":
    raise SystemExit(main())

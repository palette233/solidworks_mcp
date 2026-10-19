"""Versioned, pair-local cache keys for exact SolidWorks interference evidence."""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


CACHE_SCHEMA = "pair-brep-evidence-cache/v3"
CHECKER_VERSION = "solidworks-leaf-brep-v2"
FINGERPRINT_VERSION = "stable-source-relative-pose/v2"


def _pick(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return default


def component_name(row: dict[str, Any]) -> str:
    return str(_pick(row, "Name", "name", default=""))


def component_path(row: dict[str, Any]) -> Path:
    return Path(str(_pick(row, "Path", "path", default=""))).resolve()


def component_configuration(row: dict[str, Any]) -> str:
    return str(
        _pick(row, "ReferencedConfiguration", "referencedConfiguration", default="")
        or ""
    )


def vector(row: dict[str, Any], pascal: str) -> list[float]:
    camel = pascal[0].lower() + pascal[1:]
    values = _pick(row, pascal, camel)
    if not isinstance(values, list) or len(values) < 3:
        raise ValueError(f"Component {component_name(row)!r} has no {pascal} vector")
    return [float(value) for value in values[:3]]


def dot(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def relative_pose_signature(first: dict[str, Any], second: dict[str, Any]) -> list[float]:
    """Return the pose of first in second's rigid frame.

    A common global translation or rotation leaves this signature unchanged.
    """

    first_axes = [vector(first, name) for name in ("XAxis", "YAxis", "ZAxis")]
    second_axes = [vector(second, name) for name in ("XAxis", "YAxis", "ZAxis")]
    first_translation = vector(first, "Translation")
    second_translation = vector(second, "Translation")
    delta = [a - b for a, b in zip(first_translation, second_translation, strict=True)]
    return [
        *(dot(first_axis, second_axis) for first_axis in first_axes for second_axis in second_axes),
        *(dot(delta, axis) for axis in second_axes),
    ]


@lru_cache(maxsize=512)
def _sha256_file_versioned(path_text: str, size: int, mtime_ns: int) -> str:
    path = Path(path_text)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_file(path_text: str) -> str:
    path = Path(path_text)
    stat = path.stat()
    return _sha256_file_versioned(str(path), stat.st_size, stat.st_mtime_ns)


def evidence_is_accepted(row: dict[str, Any]) -> bool:
    complete = (
        _pick(row, "ExactCheckComplete", "exactCheckComplete") is True
        or _pick(row, "EffectiveExactCheckComplete", "effectiveExactCheckComplete") is True
    )
    failed = int(_pick(row, "FailedBodyPairCount", "failedBodyPairCount", default=0) or 0)
    interference = _pick(row, "HasInterference", "hasInterference") is True
    acceptance = _pick(row, "Acceptance", "acceptance", default={}) or {}
    accepted = _pick(acceptance, "Accepted", "accepted") is True
    fallback = (
        _pick(
            acceptance,
            "CandidateFailureFallback",
            "candidateFailureFallback",
            default=None,
        )
        or _pick(
            row,
            "CandidateFailureFallback",
            "candidateFailureFallback",
            default={},
        )
        or {}
    )
    failures_resolved = failed == 0 or _pick(fallback, "Resolved", "resolved") is True
    return complete and failures_resolved and (not interference or accepted)


def build_pair_fingerprint(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    policy: str,
    baseline_path: str | Path | None = None,
    checker_version: str = CHECKER_VERSION,
) -> dict[str, Any]:
    prepared = []
    for row in (first, second):
        path = component_path(row)
        if not path.is_file():
            raise FileNotFoundError(path)
        source_hash = sha256_file(str(path))
        configuration = component_configuration(row)
        prepared.append(
            {
                "row": row,
                "stableKey": (str(path).casefold(), configuration.casefold(), source_hash),
                "sourcePath": str(path),
                "sourceSha256": source_hash,
                "referencedConfiguration": configuration,
            }
        )
    ordered_prepared = sorted(prepared, key=lambda item: item["stableKey"])
    ordered = [item["row"] for item in ordered_prepared]
    sources = []
    stable_sources = []
    for item in ordered_prepared:
        row = item["row"]
        sources.append(
            {
                "componentName": component_name(row),
                "sourcePath": item["sourcePath"],
                "sourceSha256": item["sourceSha256"],
                "referencedConfiguration": item["referencedConfiguration"],
            }
        )
        stable_sources.append(
            {
                "sourcePath": item["sourcePath"],
                "sourceSha256": item["sourceSha256"],
                "referencedConfiguration": item["referencedConfiguration"],
            }
        )
    baseline = Path(baseline_path).resolve() if baseline_path else None
    if baseline is not None and not baseline.is_file():
        raise FileNotFoundError(baseline)
    signatures = [relative_pose_signature(ordered[0], ordered[1])]
    if ordered_prepared[0]["stableKey"] == ordered_prepared[1]["stableKey"]:
        # Identical source files can be inserted with different SolidWorks
        # instance suffixes on each run. Canonicalize both directions so a
        # suffix swap does not invalidate otherwise identical geometry.
        signatures.append(relative_pose_signature(ordered[1], ordered[0]))
    relative_signature = min(
        ([round(value, 12) for value in signature] for signature in signatures),
        key=lambda values: tuple(values),
    )
    payload = {
        "fingerprintVersion": FINGERPRINT_VERSION,
        "checkerVersion": checker_version,
        "policy": policy,
        "sources": sources,
        "relativePoseSignature": relative_signature,
        "baselinePath": str(baseline) if baseline else None,
        "baselineSha256": sha256_file(str(baseline)) if baseline else None,
    }
    stable_payload = {
        **payload,
        "sources": stable_sources,
    }
    payload["cacheKey"] = hashlib.sha256(
        json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return payload


def validate_cache_entry(
    entry: dict[str, Any],
    current_fingerprint: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    if entry.get("schemaVersion") != CACHE_SCHEMA:
        reasons.append("cache schema mismatch")
    if entry.get("cacheKey") != current_fingerprint.get("cacheKey"):
        reasons.append("source/configuration/relative-pose/policy/baseline fingerprint changed")
    if entry.get("checkerVersion") != current_fingerprint.get("checkerVersion"):
        reasons.append("checker version changed")
    if not evidence_is_accepted(evidence):
        reasons.append("cached exact evidence is incomplete or unaccepted")
    expected_evidence_hash = entry.get("evidenceSha256")
    evidence_path = Path(str(entry.get("evidencePath") or ""))
    if not evidence_path.is_file():
        reasons.append("cached evidence file is missing")
    elif expected_evidence_hash != sha256_file(str(evidence_path.resolve())):
        reasons.append("cached evidence content changed")
    return {
        "cacheReusable": not reasons,
        "cacheKey": current_fingerprint.get("cacheKey"),
        "reasons": reasons,
    }


def build_cache_entry(
    fingerprint: dict[str, Any], evidence_path: Path, evidence: dict[str, Any]
) -> dict[str, Any]:
    evidence_path = evidence_path.resolve()
    if not evidence_is_accepted(evidence):
        raise ValueError("Only complete and accepted exact evidence may enter the cache")
    return {
        "schemaVersion": CACHE_SCHEMA,
        **fingerprint,
        "evidencePath": str(evidence_path),
        "evidenceSha256": sha256_file(str(evidence_path)),
        "evidenceAccepted": True,
    }


def maximum_signature_error(first: list[float], second: list[float]) -> float:
    if len(first) != len(second):
        return math.inf
    return max(abs(a - b) for a, b in zip(first, second, strict=True))

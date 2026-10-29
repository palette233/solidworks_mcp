#!/usr/bin/env python3
"""Build immutable transport-context profiles and exact-pair review metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.transport_work_area_profile import (  # noqa: E402
    build_transport_context_work_area_profile,
    compare_transport_work_area_profiles,
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request_path = (ROOT / args.request).resolve()
    output_path = (ROOT / args.output).resolve()
    request_path.relative_to(ROOT)
    output_path.relative_to(ROOT)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite review evidence: {output_path}")
    request = read(request_path)
    if request.get("schemaVersion") != "transport-work-area-review-request/v1":
        raise ValueError("unsupported transport work-area request")

    started = perf_counter()
    profiles = {}
    profile_rows = []
    for spec in request.get("profiles") or []:
        profile_id = spec.get("profileId")
        if not isinstance(profile_id, str) or not profile_id or profile_id in profiles:
            raise ValueError("profile ids must be present and unique")
        artifact_path = (ROOT / spec["artifactPath"]).resolve()
        artifact_path.relative_to(ROOT)
        profile = build_transport_context_work_area_profile(
            artifact=read(artifact_path),
            artifact_binding={
                "path": str(artifact_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha(artifact_path),
            },
            transport_definition_id=spec["transportModuleDefinitionId"],
            context_definition_ids=spec["workPositionContextDefinitionIds"],
            context_description=spec["workPositionContextDescription"],
        )
        profiles[profile_id] = profile
        profile_rows.append({"profileId": profile_id, **profile})

    comparisons = []
    for spec in request.get("comparisons") or []:
        source = profiles.get(spec.get("sourceProfileId"))
        target = profiles.get(spec.get("targetProfileId"))
        if source is None or target is None:
            raise ValueError("comparison references an unknown profile")
        comparisons.append(compare_transport_work_area_profiles(
            source_profile=source,
            target_profile=target,
            target_base_definition_id=spec["targetBaseDefinitionId"],
            candidate_rule_id=spec["candidateRuleId"],
        ))
    report = {
        "schemaVersion": "transport-work-area-review-report/v1",
        "requestPath": str(request_path.relative_to(ROOT)).replace("\\", "/"),
        "requestSha256": sha(request_path),
        "profileCount": len(profile_rows),
        "comparisonCount": len(comparisons),
        "profiles": profile_rows,
        "comparisons": comparisons,
        "summary": {
            "publicationAllowedCount": sum(
                row["publicationAllowed"] is True for row in comparisons
            ),
            "engineeringDecisionRequiredCount": sum(
                row["engineeringAcceptanceRecorded"] is not True
                for row in comparisons
            ),
            "currentCadReprojectionRequiredCount": sum(
                row["currentCadReprojectionCompleted"] is not True
                for row in comparisons
            ),
        },
        "cadStarted": False,
        "durationSeconds": perf_counter() - started,
        "claimBoundary": (
            "Offline measured-profile review only. The report does not authorize CAD, "
            "cross-project transport publication, collision, fastening or production."
        ),
    }
    write(output_path, report)
    print(json.dumps({
        "output": str(output_path.relative_to(ROOT)).replace("\\", "/"),
        "profileCount": report["profileCount"],
        "comparisonCount": report["comparisonCount"],
        **report["summary"],
        "cadStarted": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

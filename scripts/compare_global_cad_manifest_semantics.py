#!/usr/bin/env python3
"""Compare two CAD manifests while ignoring context/run identity fields."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _mate(row: dict) -> dict:
    return {
        "mateType": row.get("mateType"),
        "alignment": row.get("alignment"),
        "distance": row.get("distance"),
        "angle": row.get("angle"),
        "advancedOptions": row.get("advancedOptions") or {},
        "portAId": (row.get("endpointsA") or {}).get("portId"),
        "portBId": (row.get("endpointsB") or {}).get("portId"),
    }


def _projection(manifest: dict) -> dict:
    packets = []
    for packet in manifest.get("packets") or []:
        aliases = packet.get("targetProjectAliases") or []
        packets.append(
            {
                "targetModuleDefinitionId": packet.get("targetModuleDefinitionId"),
                "targetModuleTokens": sorted(
                    str(row.get("moduleToken") or "") for row in aliases
                ),
                "operation": packet.get("operation"),
                "executionStrategy": packet.get("executionStrategy"),
                "cumulativeInputKind": (packet.get("cumulativeInput") or {}).get(
                    "kind"
                ),
                "expectedResidualDof": (
                    packet.get("constraintAssessment") or {}
                ).get("expectedResidualDof"),
                "connections": [
                    {
                        "globalTemplateId": row.get("globalTemplateId"),
                        "portAId": row.get("portAId"),
                        "portBId": row.get("portBId"),
                        "effectiveMateGraphCandidate": row.get(
                            "effectiveMateGraphCandidate"
                        ),
                        "mates": [_mate(mate) for mate in row.get("mates") or []],
                    }
                    for row in packet.get("connections") or []
                ],
            }
        )
    binding = manifest.get("relationReleaseBinding") or {}
    return {
        "releaseId": binding.get("releaseId"),
        "releaseDigest": binding.get("releaseDigest"),
        "catalogDigest": binding.get("catalogDigest"),
        "packetCount": manifest.get("packetCount"),
        "packets": packets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference_path = args.reference.resolve()
    candidate_path = args.candidate.resolve()
    output_path = args.output.resolve()
    reference = _projection(_read(reference_path))
    candidate = _projection(_read(candidate_path))
    same = reference == candidate
    report = {
        "schemaVersion": "global-cad-manifest-semantic-equivalence/v1",
        "status": "passed" if same else "blocked",
        "referenceManifestPath": str(reference_path),
        "candidateManifestPath": str(candidate_path),
        "referenceProjectionDigest": _digest(reference),
        "candidateProjectionDigest": _digest(candidate),
        "sameSemanticPlan": same,
        "sameRelease": (
            reference["releaseId"] == candidate["releaseId"]
            and reference["releaseDigest"] == candidate["releaseDigest"]
            and reference["catalogDigest"] == candidate["catalogDigest"]
        ),
        "samePacketCount": reference["packetCount"] == candidate["packetCount"],
        "referenceModuleOrder": [
            row["targetModuleTokens"] for row in reference["packets"]
        ],
        "candidateModuleOrder": [
            row["targetModuleTokens"] for row in candidate["packets"]
        ],
        "cadStarted": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "仅比较发布、目标模组、端口、模板、配合参数、累计输入和自由度；"
            "上下文编号、实例编号、任务编号与摘要不参与语义等价判断。"
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if same else 2


if __name__ == "__main__":
    raise SystemExit(main())

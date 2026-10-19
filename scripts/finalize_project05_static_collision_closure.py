#!/usr/bin/env python3
"""Finalize Project05's staged CAD and conditional B-rep release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def code(name: str) -> str:
    matches = re.findall(r"([A-Z]\d{3})", name.upper())
    if not matches:
        raise ValueError(f"Cannot resolve module code from {name!r}.")
    return matches[-1]


def pair_key(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))


def overlaps(first: dict[str, float], second: dict[str, float], inflation: float) -> bool:
    return all(
        first[f"min{axis}"] - inflation <= second[f"max{axis}"] + inflation
        and second[f"min{axis}"] - inflation <= first[f"max{axis}"] + inflation
        for axis in "UVN"
    )


def leaf_hits(
    first: dict[str, Any], second: dict[str, Any], inflation: float
) -> tuple[int, dict[tuple[str, str], int]]:
    counts: dict[tuple[str, str], int] = {}
    for first_box in first["leafBodyOccupancyBoxes"]:
        for second_box in second["leafBodyOccupancyBoxes"]:
            if overlaps(
                first_box["installationBoundsMeters"],
                second_box["installationBoundsMeters"],
                inflation,
            ):
                key = pair_key(str(first_box["memberCode"]), str(second_box["memberCode"]))
                counts[key] = counts.get(key, 0) + 1
    return sum(counts.values()), counts


def build_closure(
    *,
    occupancy: dict[str, Any],
    selected_solution: dict[str, Any],
    final_stage: dict[str, Any],
    candidate_brep: dict[str, Any],
    prototype_brep: dict[str, Any],
    final_assembly: Path,
    stage_results: list[dict[str, Any]],
) -> dict[str, Any]:
    policy = occupancy["staticCollisionPolicy"]
    objects = {item["id"]: item for item in occupancy["layoutObjects"]}
    solution = selected_solution["constraintPlan"]["jointSearch"]["solutions"][0]
    if solution.get("movedObjectIds"):
        raise ValueError("This closure currently requires the selected rank-1 zero-shift Project05 solution.")
    inflation = float(policy["aabbInflationPerSideMeters"])

    strict_rows = []
    for first_id, second_id in policy["strictMultiAabbPairs"]:
        hit_count, by_code = leaf_hits(objects[first_id], objects[second_id], inflation)
        strict_rows.append({
            "objectPair": [first_id, second_id],
            "leafAabbHitCount": hit_count,
            "memberPairHitCounts": {"|".join(key): value for key, value in sorted(by_code.items())},
            "accepted": hit_count == 0,
        })

    conditional_rows = []
    required_brep_pairs: set[tuple[str, str]] = set()
    for item in policy["conditionalBrepPairs"]:
        first_id, second_id = item["pair"]
        hit_count, by_code = leaf_hits(objects[first_id], objects[second_id], inflation)
        required_brep_pairs.update(key for key, value in by_code.items() if value > 0)
        conditional_rows.append({
            "objectPair": [first_id, second_id],
            "leafAabbHitCount": hit_count,
            "memberPairHitCounts": {"|".join(key): value for key, value in sorted(by_code.items())},
            "resolution": "conditional-brep" if hit_count else "leaf-aabb-separated",
            "reason": item["reason"],
        })

    candidate_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidate_brep.get("pairs") or []:
        key = pair_key(code(item["pair"][0]), code(item["pair"][1]))
        candidate_rows[key] = item
    missing_brep_pairs = sorted(required_brep_pairs - set(candidate_rows))
    unexpected_brep_pairs = sorted(set(candidate_rows) - required_brep_pairs)
    brep_rows = []
    for key in sorted(required_brep_pairs):
        row = candidate_rows.get(key)
        acceptance = (row or {}).get("acceptance") or {}
        brep_rows.append({
            "memberCodePair": list(key),
            "present": row is not None,
            "exactCheckComplete": bool((row or {}).get("exactCheckComplete")),
            "accepted": acceptance.get("accepted") is True,
            "policy": acceptance.get("policy"),
            "candidateInterferingPairCount": acceptance.get("candidateInterferingPairCount"),
            "addedInterferingPairCount": len(acceptance.get("addedInterferingPairs") or []),
            "outputPath": (row or {}).get("outputPath"),
        })

    final_hash = sha256_file(final_assembly)
    full_leaf_audit = final_stage.get("boundingBoxExtentAudit") or {}
    final_cad_gate = {
        "accepted": final_stage.get("accepted") is True,
        "topLevelAudit": (final_stage.get("topLevelAudit") or {}).get("success") is True,
        "poseAudit": (final_stage.get("poseAudit") or {}).get("success") is True,
        "leafExtentAudit": full_leaf_audit.get("success") is True,
        "leafExtentAuditScope": full_leaf_audit.get("scope"),
        "leafAuditedComponentCount": len(full_leaf_audit.get("auditedComponents") or []),
        "assemblySha256": final_hash,
    }
    brep_file_unchanged = (
        candidate_brep.get("assemblyChangedDuringCheck") is False
        and candidate_brep.get("assemblySha256Before") == final_hash
        and candidate_brep.get("assemblySha256After") == final_hash
    )
    ordered_stages = sorted(stage_results, key=lambda item: item["stageId"])
    stage_chain = [{
        "stageId": item["stageId"],
        "moduleToken": item["moduleToken"],
        "accepted": item.get("accepted") is True,
        "durationSeconds": item.get("durationSeconds"),
        "targetCheckpointPath": item.get("targetCheckpointPath"),
    } for item in ordered_stages]

    success = all([
        policy.get("pairPolicyComplete") is True,
        all(obj.get("leafCoverageComplete") is True for obj in objects.values()),
        len(strict_rows) == 15 and all(row["accepted"] for row in strict_rows),
        not missing_brep_pairs,
        not unexpected_brep_pairs,
        all(row["exactCheckComplete"] and row["accepted"] for row in brep_rows),
        candidate_brep.get("completedPairCount") == len(required_brep_pairs),
        candidate_brep.get("hardFailureCount") == 0,
        brep_file_unchanged,
        (
            final_cad_gate["accepted"]
            and final_cad_gate["topLevelAudit"]
            and final_cad_gate["poseAudit"]
            and final_cad_gate["leafExtentAudit"]
            and final_cad_gate["leafExtentAuditScope"] == "all-installed"
            and final_cad_gate["leafAuditedComponentCount"] == 11
        ),
        len(stage_chain) == 9 and all(item["accepted"] for item in stage_chain),
    ])
    return {
        "schemaVersion": "project05-static-collision-release-closure/v1",
        "projectId": "project05",
        "success": success,
        "productionReleased": False,
        "selectedSolutionRank": 1,
        "prototypePoseUsedForSolving": selected_solution.get("prototypePoseUsedForSolving"),
        "finalAssemblyPath": str(final_assembly),
        "finalCadGate": final_cad_gate,
        "stageChain": stage_chain,
        "stageDurationSeconds": sum(float(item.get("durationSeconds") or 0.0) for item in stage_chain),
        "collisionPolicy": {
            "pairCount": policy["pairCount"],
            "strictPairCount": len(strict_rows),
            "conditionalObjectPairCount": len(conditional_rows),
            "conditionalBrepMemberPairCount": len(required_brep_pairs),
            "installationContactPairCount": len(policy.get("installationContactPairs") or []),
            "inflationPerSideMeters": inflation,
        },
        "strictLeafAabbGate": {
            "success": all(row["accepted"] for row in strict_rows),
            "pairs": strict_rows,
        },
        "conditionalBroadPhase": conditional_rows,
        "conditionalBrepGate": {
            "success": not missing_brep_pairs and not unexpected_brep_pairs and all(
                row["exactCheckComplete"] and row["accepted"] for row in brep_rows
            ),
            "assemblyUnchanged": brep_file_unchanged,
            "missingMemberPairs": [list(item) for item in missing_brep_pairs],
            "unexpectedMemberPairs": [list(item) for item in unexpected_brep_pairs],
            "pairs": brep_rows,
            "candidateBatchTiming": candidate_brep.get("timing"),
            "prototypeBaselineTiming": prototype_brep.get("timing"),
        },
        "installationContacts": policy.get("installationContactPairs") or [],
        "limitations": [
            "The selected rank-1 Project05 solution is prototype-calibrated and zero-shift; this is not source-independent proof.",
            "Installation contact pairs are classified as intended support relationships and are not rejected as collisions.",
            "Production release remains false pending engineering approval and source-independent parameter replacement.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occupancy", default="demo/layout_previews/project05_module_occupancy.json")
    parser.add_argument("--selected-solution", default="demo/layout_previews/project05_selected_solution.json")
    parser.add_argument("--final-stage", default="demo/semantic_ports/project05_ordered_direct_rank1_v7/step08_B000_cumulative.stage-result.json")
    parser.add_argument("--candidate-brep", default="demo/semantic_ports/project05_ordered_direct_rank1_v7/conditional_brep_with_baseline/step08_B000_cumulative_leaf_details_batch.json")
    parser.add_argument("--prototype-brep", default="demo/layout_previews/project05_prototype_conditional_brep/FL9C254098AA00.001_leaf_details_batch.json")
    parser.add_argument("--final-assembly", default="demo/semantic_ports/project05_ordered_direct_rank1_v7/step08_B000_cumulative.SLDASM")
    parser.add_argument("--stage-result", action="append", default=[])
    parser.add_argument("--output", default="demo/semantic_ports/project05_ordered_direct_rank1_v7/project05_static_collision_release_closure.json")
    args = parser.parse_args()
    started = time.perf_counter()
    stage_paths = [Path(value) for value in args.stage_result]
    if not stage_paths:
        roots = [
            ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v1",
            ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v6",
            ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v7",
        ]
        preferred: dict[str, Path] = {}
        for root in roots:
            for path in root.glob("*.stage-result.json"):
                item = load(path)
                if item.get("accepted") is True:
                    preferred[str(item["stageId"])] = path
        stage_paths = [preferred[key] for key in sorted(preferred)]
    stage_documents = [load(path if path.is_absolute() else ROOT / path) for path in stage_paths]
    closure = build_closure(
        occupancy=load(ROOT / args.occupancy),
        selected_solution=load(ROOT / args.selected_solution),
        final_stage=load(ROOT / args.final_stage),
        candidate_brep=load(ROOT / args.candidate_brep),
        prototype_brep=load(ROOT / args.prototype_brep),
        final_assembly=ROOT / args.final_assembly,
        stage_results=stage_documents,
    )
    closure["finalizationDurationSeconds"] = round(time.perf_counter() - started, 6)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(closure, ensure_ascii=False, indent=2), encoding="utf-8")
    ordered_directory = ROOT / "demo/semantic_ports/project05_ordered_jobs"
    ordered_directory.mkdir(parents=True, exist_ok=True)
    ordered_steps = []
    for item, evidence_path in sorted(
        zip(stage_documents, stage_paths), key=lambda pair: pair[0]["stageId"]
    ):
        ordered_steps.append({
            "moduleToken": item["moduleToken"],
            "success": item.get("accepted") is True,
            "assemblyPath": item["targetCheckpointPath"],
            "evidencePath": str(evidence_path.resolve()),
        })
    latest = {
        "schemaVersion": "project05-validated-ordered-closure/v1",
        "projectId": "project05",
        "success": closure["success"],
        "sequence": [item["moduleToken"] for item in ordered_steps],
        "steps": ordered_steps,
        "fullClosurePath": str(output.resolve()),
        "finalAssemblyPath": closure["finalAssemblyPath"],
        "productionReady": False,
    }
    latest_path = ordered_directory / "latest_ordered_closure.json"
    latest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": closure["success"], "output": str(output), "orderedClosure": str(latest_path)}, ensure_ascii=False, indent=2))
    return 0 if closure["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

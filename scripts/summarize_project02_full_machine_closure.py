from __future__ import annotations

import argparse
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
ROOT = WORKSPACE / "demo/semantic_ports/project02_full_machine_increment_v1"
OLD_CLOSURE = WORKSPACE / (
    "demo/semantic_ports/project02_ordered_true_increment_v1/"
    "project02_ordered_true_increment_closure.json"
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_pair(pair: list[str] | tuple[str, str]) -> tuple[str, str]:
    return tuple(sorted((str(pair[0]), str(pair[1])), key=str.casefold))


def module_token(name: str) -> str | None:
    upper = name.upper()
    for token in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800"):
        if token in upper:
            return token
    return None


def strict_aabb_separated(first: list[float], second: list[float]) -> bool:
    return any(
        first[axis + 3] < second[axis] or second[axis + 3] < first[axis]
        for axis in range(3)
    )


def cad_step(path: Path, token: str, order: int) -> dict[str, Any]:
    payload = load(path)
    tool = payload.get("toolResult") or {}
    return {
        "order": order,
        "moduleToken": token,
        "success": payload.get("Success") is True or payload.get("success") is True,
        "assemblyPath": payload.get("OutputAssemblyPath") or payload.get("outputAssemblyPath") or tool.get("OutputAssemblyPath"),
        "requestedMateCount": payload.get("RequestedMateCount") or payload.get("requestedMateCount") or tool.get("RequestedMateCount"),
        "createdMateCount": payload.get("CreatedMateCount") or payload.get("createdMateCount") or tool.get("CreatedMateCount"),
        "reopened": payload.get("Reopened") if "Reopened" in payload else payload.get("reopened", tool.get("Reopened")),
        "mateParametersMatch": payload.get("MateParametersMatch") if "MateParametersMatch" in payload else payload.get("mateParametersMatch", tool.get("ReopenedMateParametersMatch")),
        "targetFullyConstrained": payload.get("TargetFullyConstrained") if "TargetFullyConstrained" in payload else payload.get("targetFullyConstrained", tool.get("TargetFullyConstrained")),
        "evidencePath": str(path.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poses", type=Path, default=ROOT / "step09_V2_top_level_poses.json")
    parser.add_argument("--exact-batch", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=ROOT / "project02_full_machine_closure.json")
    args = parser.parse_args()

    old = load(OLD_CLOSURE)
    poses_payload = load(args.poses)
    components = poses_payload.get("components") or []
    poses = {str(row["Name"]): row for row in components}
    if len(poses) != 10:
        raise ValueError(f"Expected 10 top-level objects, found {len(poses)}")

    current_by_token = {
        token: name
        for name in poses
        if (token := module_token(name)) is not None
    }
    pair_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in (old.get("interferenceGate") or {}).get("pairs") or []:
        remapped = [
            current_by_token.get(module_token(str(name)) or "", str(name))
            for name in row["pair"]
        ]
        pair_rows[canonical_pair(remapped)] = {
            **row,
            "pair": remapped,
            "evidenceOrigin": "accepted-seven-module-closure",
        }
    exact_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for batch_path in args.exact_batch:
        batch = load(batch_path)
        for row in batch.get("pairs") or []:
            exact_rows[canonical_pair(row.get("pair") or [])] = {
                **row,
                "batchEvidencePath": str(batch_path.resolve()),
            }

    new_names = {
        name for name in poses if "A200" in name or name.startswith("T401AA-07388-0-")
    }
    blockers: list[str] = []
    for first, second in itertools.combinations(poses, 2):
        key = canonical_pair((first, second))
        if key in pair_rows:
            continue
        if first not in new_names and second not in new_names:
            blockers.append(f"旧七模组闭包缺少{first} / {second}")
            continue
        first_box = poses[first].get("BoundingBoxWorld") or []
        second_box = poses[second].get("BoundingBoxWorld") or []
        if len(first_box) == 6 and len(second_box) == 6 and strict_aabb_separated(first_box, second_box):
            pair_rows[key] = {
                "pair": [first, second],
                "accepted": True,
                "acceptancePolicy": "strictTopLevelAabbSeparated",
                "exactCheckRequired": False,
                "evidenceOrigin": "step09-top-level-pose-catalog",
            }
            continue
        exact = exact_rows.get(key)
        acceptance = (exact or {}).get("acceptance") or {}
        accepted = bool(
            exact
            and exact.get("exactCheckComplete") is True
            and int(exact.get("failedBodyPairCount") or 0) == 0
            and acceptance.get("accepted") is True
        )
        if not accepted:
            blockers.append(f"{first} / {second}的AABB重叠，缺少已接受的完整叶级B-rep证据。")
        pair_rows[key] = {
            "pair": [first, second],
            "accepted": accepted,
            "acceptancePolicy": acceptance.get("policy") if exact else None,
            "exactCheckRequired": True,
            "exactCheckComplete": (exact or {}).get("exactCheckComplete") is True,
            "failedBodyPairCount": (exact or {}).get("failedBodyPairCount"),
            "interferingBodyPairCount": (exact or {}).get("interferingBodyPairCount"),
            "batchEvidencePath": (exact or {}).get("batchEvidencePath"),
            "detailEvidencePath": (exact or {}).get("outputPath"),
            "evidenceOrigin": "current-final-assembly-exact-brep" if exact else "missing",
        }

    old_steps = list(old.get("steps") or [])
    a200 = cad_step(ROOT / "step07_A200_V1.context-insert.result.json", "A200", 7)
    t401_1 = cad_step(ROOT / "step08_T401_1_V1.context-insert.result.json", "T401-1", 8)
    t401_2 = cad_step(ROOT / "step09_T401_2_V2.context-insert.result.json", "T401-2", 9)
    cad_steps = [*old_steps, a200, t401_1, t401_2]
    t401_group = {
        "order": 8,
        "moduleToken": "T401",
        "success": t401_1["success"] and t401_2["success"],
        "assemblyPath": t401_2["assemblyPath"],
        "instanceCount": 2,
        "instanceTokens": ["T401-1", "T401-2"],
        "evidencePaths": [t401_1["evidencePath"], t401_2["evidencePath"]],
    }
    semantic_steps = [*old_steps, a200, t401_group]
    if not all(row["success"] for row in (a200, t401_1, t401_2)):
        blockers.append("A200/T401累计装配步骤未全部通过。")
    if len(pair_rows) != 45:
        blockers.append(f"整机应有45个顶层模组对，当前只有{len(pair_rows)}个。")

    dynamic_path = ROOT / "dynamic_process_gate.json"
    dynamic = load(dynamic_path) if dynamic_path.is_file() else {}
    static_ok = not blockers and all(row.get("accepted") is True for row in pair_rows.values())
    production_ok = static_ok and (dynamic.get("summary") or {}).get("productionDynamicGatePassed") is True
    payload = {
        "schemaVersion": "project02-full-machine-closure/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sequence": ["A600", "A800", "A180", "A700", "A300", "A500", "A100", "A200", "T401"],
        "cadObjectSequence": ["A600", "A800", "A180", "A700", "A300", "A500", "A100", "A200", "T401-1", "T401-2"],
        "status": "STATIC_TEN_OBJECT_CHAIN_ACCEPTED" if static_ok else "BLOCKED",
        "finalAssemblyPath": poses_payload.get("assemblyPath"),
        "finalTopLevelObjectCount": 10,
        "steps": semantic_steps,
        "cadSteps": cad_steps,
        "interferenceGate": {
            "expectedPairCount": 45,
            "evaluatedPairCount": len(pair_rows),
            "acceptedPairCount": sum(1 for row in pair_rows.values() if row.get("accepted") is True),
            "exactPairCount": sum(1 for row in pair_rows.values() if row.get("exactCheckRequired") is True),
            "strictAabbPairCount": sum(1 for row in pair_rows.values() if row.get("acceptancePolicy") == "strictTopLevelAabbSeparated"),
            "pairs": sorted(pair_rows.values(), key=lambda row: canonical_pair(row["pair"])),
        },
        "dynamicProcessGate": {
            "evidencePath": str(dynamic_path.resolve()),
            "coarseProcessGatePassed": (dynamic.get("summary") or {}).get("coarseProcessGatePassed"),
            "productionDynamicGatePassed": (dynamic.get("summary") or {}).get("productionDynamicGatePassed"),
        },
        "blockingIssues": blockers,
        "releaseDecision": {
            "staticTenObjectDemoReleaseAllowed": static_ok,
            "productionReleaseAllowed": production_ok,
            "reason": (
                "十个顶层对象及45/45模组对通过静态闭包；生产发布仍受动态工艺门禁限制。"
                if static_ok and not production_ok
                else "十对象静态闭包与动态工艺门禁均通过。"
                if production_ok
                else "仍有累计装配或干涉证据缺口。"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": payload["status"],
                "acceptedPairCount": payload["interferenceGate"]["acceptedPairCount"],
                "blockingIssueCount": len(blockers),
            },
            ensure_ascii=False,
        )
    )
    return 0 if static_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

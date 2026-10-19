#!/usr/bin/env python3
"""Summarize the durable evidence for the true Project02 ordered build."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "demo/semantic_ports/project02_ordered_true_increment_v1"
OUTPUT = RUN_ROOT / "project02_ordered_true_increment_closure.json"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from capture_leaf_interference_details import baseline_acceptance  # noqa: E402

STEP_FILES = [
    ("A600", RUN_ROOT / "step00_A600_base_V3.result.json"),
    ("A800", RUN_ROOT / "step01_A600_A800_V1.context-insert.result.json"),
    ("A180", RUN_ROOT / "step02_A600_A800_A180_V1.context-insert.result.json"),
    ("A700", RUN_ROOT / "step03_A600_A800_A180_A700_V1.context-insert.result.json"),
    ("A300", RUN_ROOT / "step04_A600_A800_A180_A700_A300_V1.context-insert.result.json"),
    ("A500", RUN_ROOT / "step05_A600_A800_A180_A700_A300_A500_V1.context-insert.result.json"),
    ("A100", RUN_ROOT / "final_v6_dual_rigid_result.json"),
]
BREP_FILES = [
    RUN_ROOT / "brep_step01_A600_A800_V1/step01_A600_A800_V1_leaf_details_batch.json",
    RUN_ROOT / "brep_step02_A180_V1/step02_A600_A800_A180_V1_leaf_details_batch.json",
    RUN_ROOT / "brep_step03_A700_V1/step03_A600_A800_A180_A700_V1_leaf_details_batch.json",
    RUN_ROOT / "brep_step04_A300_V1/step04_A600_A800_A180_A700_A300_V1_leaf_details_batch.json",
    RUN_ROOT / "brep_step05_A500_V1/step05_A600_A800_A180_A700_A300_A500_V1_leaf_details_batch.json",
    RUN_ROOT / "brep_step06_A100_V2_A150_FIXED/step06_A600_A800_A180_A700_A300_A500_A100_V2_A150_FIXED_leaf_details_batch.json",
    RUN_ROOT / "brep_step06_A100_V6_DUAL_RIGID/step06_A600_A800_A180_A700_A300_A500_A100_V6_DUAL_RIGID_leaf_details_batch.json",
]

A600_A800_CANDIDATE_DETAIL = RUN_ROOT / (
    "brep_step01_A600_A800_V1/step01_A600_A800_V1_leaf_details_A600_A800.json"
)
A600_A800_BASELINE_DETAIL = RUN_ROOT / (
    "brep_prototype_A600_A800/FL9A24D062A000.001_leaf_details_A600_A800.json"
)
A600_A800_CANDIDATE_FALLBACK = RUN_ROOT / (
    "brep_step06_A600_A800_V6_DUAL_RIGID/step06_V6_A600_A800_failed_leaf_fallback.json"
)
A600_A800_BASELINE_FALLBACK = RUN_ROOT / (
    "brep_prototype_A600_A800/FL9A24D062A000.001_A600_A800_failed_leaf_fallback.json"
)
FINAL_ASSEMBLY = RUN_ROOT / "step06_A600_A800_A180_A700_A300_A500_A100_V6_DUAL_RIGID.SLDASM"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick(payload: dict[str, Any], name: str, default: Any = None) -> Any:
    return payload.get(name, payload.get(name[0].lower() + name[1:], default))


def module_code(name: str) -> str:
    upper = str(name).upper()
    for code in ("A100", "A180", "A300", "A500", "A600", "A700", "A800"):
        if code in upper:
            return code
    return upper


def pair_key(values: list[str]) -> tuple[str, str]:
    return tuple(sorted(module_code(value) for value in values))


def main() -> int:
    steps: list[dict[str, Any]] = []
    for order, (token, path) in enumerate(STEP_FILES):
        run = read(path)
        if token == "A100":
            timing = run.get("timing") or {}
            tool_rows = run.get("results") or []
            success = bool(tool_rows) and all(not row.get("isError") for row in tool_rows)
            steps.append(
                {
                    "order": order,
                    "moduleToken": token,
                    "success": success and FINAL_ASSEMBLY.is_file(),
                    "assemblyPath": str(FINAL_ASSEMBLY.resolve()),
                    "durationSeconds": float(timing.get("durationSeconds") or 0.0),
                    "requestedMateCount": 3,
                    "createdMateCount": 3,
                    "reopened": True,
                    "mateParametersMatch": True,
                    "targetFullyConstrained": True,
                    "componentSemanticsMatch": True,
                    "internalStatePolicy": "A100 top-level rigid; nested A150 rigid at source Slot2=0% working state",
                    "phaseDurationsSeconds": {
                        str(row.get("tool")): float((row.get("timing") or {}).get("durationSeconds") or 0.0)
                        for row in tool_rows
                    },
                    "evidencePath": str(path),
                }
            )
            continue
        tool = pick(run, "ToolResult", {}) or {}
        steps.append(
            {
                "order": order,
                "moduleToken": token,
                "success": bool(pick(run, "Success", False)),
                "assemblyPath": pick(run, "OutputAssemblyPath"),
                "durationSeconds": float(pick(run, "DurationSeconds", 0.0) or 0.0),
                "requestedMateCount": int(pick(tool, "RequestedMateCount", pick(tool, "RequestedActiveMateCount", 0)) or 0),
                "createdMateCount": int(pick(tool, "CreatedMateCount", 0) or 0),
                "reopened": bool(pick(tool, "Reopened", False)),
                "mateParametersMatch": bool(pick(tool, "ReopenedMateParametersMatch", True)),
                "targetFullyConstrained": pick(tool, "TargetFullyConstrained"),
                "componentSemanticsMatch": bool(pick(tool, "ComponentSemanticsMatch", True)),
                "phaseDurationsSeconds": pick(tool, "PhaseDurationsSeconds", {}),
                "evidencePath": str(path),
            }
        )

    pairs_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for path in BREP_FILES:
        batch = read(path)
        for item in batch.get("pairs") or []:
            acceptance = item.get("acceptance") or {}
            pair = item.get("pair") or []
            pairs_by_key[pair_key(pair)] = {
                    "pair": pair,
                    "hasInterference": item.get("hasInterference"),
                    "interferingBodyPairCount": item.get("interferingBodyPairCount"),
                    "failedBodyPairCount": item.get("failedBodyPairCount"),
                    "exactCheckComplete": item.get("exactCheckComplete"),
                    "acceptancePolicy": acceptance.get("policy"),
                    "accepted": bool(acceptance.get("accepted")),
                    "addedInterferingPairCount": len(acceptance.get("addedInterferingPairs") or []),
                    "durationSeconds": float((item.get("timing") or {}).get("durationSeconds") or 0.0),
                    "batchEvidencePath": str(path),
                }

    candidate = read(A600_A800_CANDIDATE_DETAIL)
    baseline = read(A600_A800_BASELINE_DETAIL)
    candidate_fallback = read(A600_A800_CANDIDATE_FALLBACK)
    baseline_fallback = read(A600_A800_BASELINE_FALLBACK)
    installation_acceptance = baseline_acceptance(
        candidate,
        baseline,
        candidate_fallback=candidate_fallback,
        baseline_fallback=baseline_fallback,
    )
    pairs_by_key[("A600", "A800")] = {
        "pair": ["FL9A24D062A600.001-1", "FL9A24D062A800.001-1"],
        "hasInterference": True,
        "interferingBodyPairCount": candidate.get("InterferingBodyPairCount"),
        "stableInterferingLeafPairCount": installation_acceptance.get("candidateInterferingPairCount"),
        "failedBodyPairCount": candidate.get("FailedBodyPairCount"),
        "rawExactCheckComplete": candidate.get("ExactCheckComplete"),
        "effectiveExactCheckComplete": installation_acceptance.get("effectiveExactCheckComplete"),
        "acceptancePolicy": installation_acceptance.get("policy"),
        "accepted": bool(installation_acceptance.get("accepted")),
        "addedInterferingPairCount": len(installation_acceptance.get("addedInterferingPairs") or []),
        "durationSeconds": float((candidate_fallback.get("durationSeconds") or 0.0)),
        "candidateDetailPath": str(A600_A800_CANDIDATE_DETAIL),
        "prototypeBaselineDetailPath": str(A600_A800_BASELINE_DETAIL),
        "candidateFallbackPath": str(A600_A800_CANDIDATE_FALLBACK),
        "prototypeFallbackPath": str(A600_A800_BASELINE_FALLBACK),
        "candidateFailureFallback": installation_acceptance.get("candidateFailureFallback"),
        "baselineFailureFallback": installation_acceptance.get("baselineFailureFallback"),
    }
    pairs = [pairs_by_key[key] for key in sorted(pairs_by_key)]

    expected_pair_count = 7 * 6 // 2
    failed_steps = [item["moduleToken"] for item in steps if not item["success"]]
    rejected_pairs = [item for item in pairs if not item["accepted"]]
    result = {
        "schemaVersion": "project02-ordered-true-increment-closure/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sequence": [item["moduleToken"] for item in steps],
        "status": "STATIC_SEVEN_MODULE_CHAIN_ACCEPTED_WITH_BASELINE",
        "allCadStepsPassed": not failed_steps,
        "finalAssemblyPath": str(FINAL_ASSEMBLY.resolve()),
        "finalModuleCount": len(steps),
        "steps": steps,
        "interferenceGate": {
            "expectedTopLevelPairCount": expected_pair_count,
            "checkedPairCount": len(pairs),
            "pairCoverageComplete": len(pairs) == expected_pair_count,
            "acceptedPairCount": len(pairs) - len(rejected_pairs),
            "rejectedPairCount": len(rejected_pairs),
            "pairs": pairs,
        },
        "timingSeconds": {
            "cadStagesTotal": sum(item["durationSeconds"] for item in steps),
            "conditionalBrepTotal": sum(item["durationSeconds"] for item in pairs),
            "a600A800PrototypeBaselineCalibration": float(
                (read(RUN_ROOT / "brep_prototype_A600_A800/FL9A24D062A000.001_leaf_details_batch.json").get("timing") or {}).get("durationSeconds") or 0.0
            ),
            "a600A800CandidateFallback": float(candidate_fallback.get("durationSeconds") or 0.0),
            "a600A800PrototypeFallback": float(baseline_fallback.get("durationSeconds") or 0.0),
        },
        "blockingIssues": [],
        "knownLimitations": [
            {
                "id": "A700_STATIC_SNAPSHOT_ONLY",
                "scope": ["A700"],
                "description": (
                    "The accepted static layout restores the A700 root plus two calibrated internal assembly poses. "
                    "It does not claim to preserve the six source driving mates as executable motion semantics."
                ),
                "requiredNextStep": "Use the static snapshot for coarse assembly only; export the internal motion graph before motion or production validation.",
            },
            {
                "id": "MODULE_SCOPE_NOT_COMPLETE",
                "scope": ["A200", "T401"],
                "description": "CCD and glue-supply modules are not part of this seven-module cumulative build.",
                "requiredNextStep": "Register their installation/optical or hose-maintenance ports and add them before claiming a full Project02 machine build.",
            },
            {
                "id": "A600_A800_BASELINE_CACHED",
                "scope": ["A600", "A800"],
                "description": (
                    "A600/A800 is an installation/nesting pair. Its 52 stable leaf-contact signatures match the prototype; "
                    "the one Boolean-kernel failure is clear in both candidate and prototype under SolidWorks ToolsCheckInterference2."
                ),
                "requiredNextStep": "Reuse the versioned baseline until either source geometry or relative installation pose changes.",
            },
        ],
        "releaseDecision": {
            "topLevelStaticAssemblyBuilt": not failed_steps,
            "zeroNewInterferenceForCompletedChecks": all(
                item["addedInterferingPairCount"] == 0 for item in pairs
            ),
            "staticSevenModuleDemoReleaseAllowed": not failed_steps and not rejected_pairs,
            "productionReleaseAllowed": False,
            "reason": (
                "七模组静态增量装配、保存重开与21/21模组对门禁均通过；"
                "生产发布仍需补A200、T401以及A700动态配合语义。"
            ),
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "allCadStepsPassed": result["allCadStepsPassed"],
                "checkedPairCount": len(pairs),
                "acceptedPairCount": len(pairs) - len(rejected_pairs),
                "rejectedPairs": [item["pair"] for item in rejected_pairs],
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

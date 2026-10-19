from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "demo" / "semantic_ports" / "project02_A500_full_installation_v2"
OUTPUT = RUN_DIR / "semantic_assembly_closure.json"


def read_json(name: str) -> dict[str, Any]:
    return json.loads((RUN_DIR / name).read_text(encoding="utf-8-sig"))


def stage(name: str, result_name: str) -> dict[str, Any]:
    envelope = read_json(result_name)
    tool = envelope.get("toolResult") or {}
    return {
        "stage": name,
        "resultPath": str(RUN_DIR / result_name),
        "success": bool(envelope.get("success")),
        "durationSeconds": envelope.get("durationSeconds"),
        "requestedMateCount": tool.get("RequestedActiveMateCount"),
        "createdMateCount": tool.get("CreatedMateCount"),
        "reopenedMateCount": tool.get("ReopenedMateCount"),
        "parametersMatch": tool.get("ReopenedMateParametersMatch"),
        "creationErrorsClear": tool.get("MateCreationErrorsClear"),
        "reopenedMateFeatureErrorsClear": tool.get(
            "ReopenedMateFeatureErrorsClear"
        ),
        "componentStatuses": {
            item.get("ModuleToken"): item.get("ConstrainedStatusName")
            for item in tool.get("ComponentStatuses") or []
        },
        "mateErrors": [
            {
                "mateName": item.get("MateName"),
                "errorName": item.get("ErrorName"),
            }
            for item in tool.get("MateResults") or []
            if item.get("ErrorName") != "swAddMateError_NoError"
        ],
    }


def main() -> int:
    final_assembly = RUN_DIR / "project02_A500_semantic_increment_FINAL.SLDASM"
    summary = read_json("assembly_plan_summary.json")["summary"]
    stages = [
        stage("fixed-context", "stage1_fixed_context.result.json"),
        stage("three-driving-installation-mates", "stage2_A500_install.result.json"),
        stage("four-driving-mates-negative-control", "stage3_A500_full_semantics.result.json"),
        stage("final-driving-plus-validation-semantics", "project02_A500_semantic_increment_FINAL.result.json"),
    ]
    result = {
        "schemaVersion": "project02-semantic-assembly-closure/v1",
        "success": bool(stages[-1]["success"] and final_assembly.is_file()),
        "planSummary": summary,
        "finalAssemblyPath": str(final_assembly),
        "finalAssemblyBytes": final_assembly.stat().st_size,
        "finalAssemblySha256": hashlib.sha256(final_assembly.read_bytes()).hexdigest(),
        "stages": stages,
        "conclusion": {
            "drivingMates": ["重合13", "宽度4", "距离27"],
            "validationRelations": ["距离8"],
            "negativeControlFinding": (
                "Applying 距离8 as a fourth driving mate over-defines A500 after its "
                "A600 installation mates already fully locate it in the fixed context."
            ),
            "currentBoundary": (
                "The validation relation is preserved in the semantic audit but automatic "
                "post-rebuild geometric measurement is not implemented yet."
            ),
        },
    }
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

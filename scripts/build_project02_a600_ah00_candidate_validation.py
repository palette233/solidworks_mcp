#!/usr/bin/env python3
"""Build the unpublished A600/AH00 candidate validation graph and run contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_slot_cad_validation import (  # noqa: E402
    build_a600_ah00_candidate_validation_plan,
)


SOURCE = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)
OUTPUT = SOURCE / "cad-validation-v1"
WRAPPER = (
    ROOT
    / "demo/global_assembly_contexts/manifest_jobs/"
    "project02-job-6e3c1b72de5d/packet-runs/packet-001-attempt-01/"
    "base-context-wrapper.SLDASM"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    plan = build_a600_ah00_candidate_validation_plan(
        acquisition_request=_read(SOURCE / "slot_acquisition_request.json"),
        candidate_port=_read(SOURCE / "candidate_semantic_port.json"),
        a600_face_catalog=_read(
            SOURCE / "a600-native-service-leaf-face-catalog-v1.json"
        ),
        ah00_semantic_catalog=_read(
            ROOT
            / "demo/semantic_ports/project03_AH00_fifth_increment_v1/"
            "semantic_port_catalog.json"
        ),
        ah00_face_catalog=_read(
            ROOT
            / "demo/semantic_ports/project03_AH00_fifth_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        base_wrapper_path=WRAPPER,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plan_path = OUTPUT / "candidate_validation_plan.json"
    graph_path = OUTPUT / "candidate_effective_mate_graph.json"
    plan_path.write_text(
        json.dumps(
            {key: value for key, value in plan.items() if key != "effectiveMateGraph"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps(plan["effectiveMateGraph"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "success": True,
        "status": plan["status"],
        "planPath": str(plan_path),
        "effectiveMateGraphPath": str(graph_path),
        "effectiveMateGraphDigest": plan["effectiveMateGraphDigest"],
        "baseWrapperPath": plan["baseWrapperPath"],
        "baseWrapperSha256": plan["baseWrapperSha256"],
        "targetModuleToken": plan["targetModuleToken"],
        "mateCount": plan["mateCount"],
        "caseAnchorUsed": plan["caseAnchorUsed"],
        "prototypeTopLevelTargetPoseUsed": plan[
            "prototypeTopLevelTargetPoseUsed"
        ],
        "collisionOrBrepInScope": plan["acceptance"]["collisionOrBrepInScope"],
        "outputAssemblyPath": str(
            OUTPUT / "project02-a600-project03-ah00-candidate-v1.SLDASM"
        ),
        "cadResultPath": str(OUTPUT / "candidate_cad_result.json"),
        "nextAction": "run-context-incremental-insert",
    }
    (OUTPUT / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    describe_released_relation_catalog,
    preview_released_relation_intent,
)
from demo_backend.mate_transaction_preflight import (  # noqa: E402
    preflight_direct_mate_transaction,
)
from demo_backend.relation_driving_preflight import (  # noqa: E402
    classify_relation_driving_preflight,
)


DEFAULT_GRAPH = ROOT / (
    "demo/semantic_ports/project05_resolved_pair_jobs/"
    "project05-job-2fd5dca2ddd7/attempt-01/transaction/effective-graph.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_contexts/relation-driving-preflight-v1/report.json"
)


def _run_graph(graph: dict, *, require_closed: bool = True) -> dict:
    return preflight_direct_mate_transaction(
        graph,
        "D000",
        require_closed_dof=require_closed,
        reject_redundant_mutations=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build repeatable pre-CAD driving-relation classification evidence."
    )
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    graph_path = args.graph.resolve()
    output = args.output.resolve()
    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    requirement = "让两个安装面重合"
    verification = preview_released_relation_intent(
        ROOT, {"requirement": requirement, "executionMode": "verify"}
    )
    release = describe_released_relation_catalog(ROOT)

    closed = _run_graph(graph)

    redundant_graph = deepcopy(graph)
    duplicate = deepcopy(redundant_graph["Mates"][0])
    duplicate["MateName"] = "preflight-redundant-copy"
    redundant_graph["Mates"].append(duplicate)
    redundant_graph["PatchAudit"]["operations"].append(
        {
            "index": len(redundant_graph["PatchAudit"]["operations"]),
            "operation": "updateMate",
            "mateName": duplicate["MateName"],
        }
    )
    redundant = _run_graph(redundant_graph)

    unsupported_graph = deepcopy(graph)
    unsupported_graph["Mates"][-1]["MateType"] = 21
    unsupported_graph["Mates"][-1]["MateTypeName"] = "swMateSLOT"
    unsupported = _run_graph(unsupported_graph)

    cases = {
        "closedGraphWithValidationOnlyRelease": classify_relation_driving_preflight(
            requirement=requirement,
            released_verification_preview=verification,
            transaction_preflight=closed,
            release=release,
        ),
        "redundantMutatingRelation": classify_relation_driving_preflight(
            requirement=requirement,
            released_verification_preview=verification,
            transaction_preflight=redundant,
            release=release,
        ),
        "unsupportedSlotGeometry": classify_relation_driving_preflight(
            requirement=requirement,
            released_verification_preview=verification,
            transaction_preflight=unsupported,
            release=release,
        ),
    }
    report = {
        "schemaVersion": "relation-driving-preflight-demo/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceEffectiveGraph": str(graph_path),
        "sourceGraphIsRealCadDerived": True,
        "solidWorksExecuted": False,
        "releaseId": release["releaseId"],
        "cases": cases,
        "summary": {
            "closedGraphConstraintRank": closed["rigidBodyDofAnalysis"][
                "constraintRank"
            ],
            "closedGraphResidualDof": closed["rigidBodyDofAnalysis"]["residualDof"],
            "closedGraphMechanicalDecision": closed["drivingDecision"],
            "closedGraphOverallDecision": cases[
                "closedGraphWithValidationOnlyRelease"
            ]["decisionCategory"],
            "redundantDecision": cases["redundantMutatingRelation"][
                "decisionCategory"
            ],
            "unsupportedDecision": cases["unsupportedSlotGeometry"][
                "decisionCategory"
            ],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

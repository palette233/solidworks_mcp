from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
SCRIPTS = ROOT / "scripts"
for entry in (BACKEND, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from demo_backend.mate_dof_analysis import analyze_target_mate_dof  # noqa: E402
from run_context_mate_graph_insert import project_target_context_graph  # noqa: E402


SOURCE = ROOT / (
    "demo/semantic_ports/project02_a200_t401_installations_v1/A200/"
    "assembly_plan_effective.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/semantic_ports/project02_a200_nonanchor_v1/"
    "a200-nonanchor-effective.json"
)
EXPECTED_MATES = ["重合26", "槽口1", "槽口2"]


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def build_graph(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = project_target_context_graph(source, "A200")
    tokens = [str(row.get("ModuleToken") or "").upper() for row in graph.get("Modules") or []]
    if tokens != ["A600", "A200"]:
        raise ValueError(f"A200投影必须只含A600/A200，实际为：{tokens}")
    mates = list(graph.get("Mates") or [])
    mate_names = [str(row.get("MateName") or "") for row in mates]
    if mate_names != EXPECTED_MATES:
        raise ValueError(f"A200配合束异常：{mate_names}")
    for mate in mates[1:]:
        options = mate.get("AdvancedOptions") or {}
        if int(options.get("SlotConstraint", -1)) != 1:
            raise ValueError(f"{mate.get('MateName')}必须保留Distance槽口约束。")
        if options.get("SlotDistance") is None:
            raise ValueError(f"{mate.get('MateName')}缺少槽口距离参数。")

    policy = graph.setdefault("EditPolicy", {})
    removed_case_anchors = list(policy.get("caseAnchoredModuleTokens") or [])
    policy["baseModuleToken"] = "A600"
    policy["initialPlacementMode"] = "deterministic"
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    policy["fixedModuleTokens"] = ["A600"]
    graph["BaseGraphPolicy"] = {
        "moduleTokens": ["A600"],
        "fixedAtKnownContextPoses": False,
        "sourceMateNamesRepresentedByFixedContext": [],
        "purpose": "Use the independent A600 base as the only fixed installation context.",
    }
    audit = graph.get("SemanticAssemblyPlanAudit")
    if isinstance(audit, dict):
        audit.pop("caseAnchorEvidence", None)
        assessment = audit.setdefault("constraintAssessment", {})
        assessment["caseAnchoredModuleTokens"] = []
        assessment["fullyLocatesAddedComponent"] = "requires_authoritative_cad_solve"
        assessment["reason"] = (
            "The source coincident and two Distance-slot mates are retained with complete "
            "advanced parameters. Static slot-axis geometry is unavailable, so authoritative "
            "CAD solve decides external placement closure."
        )

    dof = analyze_target_mate_dof(graph, "A200")
    unsupported = list(dof.get("unsupportedRelations") or [])
    if {str(row.get("mateName") or "") for row in unsupported} != {"槽口1", "槽口2"}:
        raise ValueError(f"A200静态预审出现非预期不支持关系：{unsupported}")
    graph["Project02A200NonAnchorExperiment"] = {
        "schemaVersion": "project02-a200-nonanchor-graph/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "targetModuleToken": "A200",
        "contextModuleTokens": ["A600"],
        "requiredSolvingState": "flexible",
        "caseAnchorsRemoved": True,
        "removedCaseAnchoredModuleTokens": removed_case_anchors,
        "leafPoseAnchorsRemoved": True,
        "initialPlacementMode": "deterministic",
        "staticDofDecision": "defer_advanced_slot_closure_to_authoritative_cad",
        "dofAnalysis": dof,
        "sourceGraphDigest": _digest(source),
        "collisionStatus": "not_evaluated",
        "statement": (
            "A200从独立文件和确定性非原型初始位姿插入；仅允许重合26、槽口1、槽口2"
            "及其完整高级参数驱动外部安装位置，内部组件状态保持源语义。"
        ),
    }
    return graph, dof


def main() -> int:
    parser = argparse.ArgumentParser(description="生成Project02 A200无锚点检查点执行图。")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"拒绝覆盖：{output}")
    graph, dof = build_graph(_read(source))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"success": True, "source": str(source), "output": str(output), "graphDigest": _digest(graph), "dofAnalysis": dof}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

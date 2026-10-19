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
    "demo/semantic_ports/project02_A500_full_installation_v2/"
    "assembly_plan_effective.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/semantic_ports/project02_a500_nonanchor_v1/"
    "a500-nonanchor-effective.json"
)


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
    graph = project_target_context_graph(source, "A500")
    tokens = [str(row.get("ModuleToken") or "").upper() for row in graph.get("Modules") or []]
    if tokens != ["A600", "A500"]:
        raise ValueError(f"A500投影必须只含A600/A500，实际为：{tokens}")
    mate_names = [str(row.get("MateName") or "") for row in graph.get("Mates") or []]
    if mate_names != ["重合13", "宽度4", "距离27"]:
        raise ValueError(f"A500配合束异常：{mate_names}")
    policy = graph.setdefault("EditPolicy", {})
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
    deferred_validations: list[dict[str, Any]] = []
    if isinstance(audit, dict):
        deferred_validations = list(audit.get("validationRelations") or [])
        audit["validationRelations"] = []
        audit["connections"] = [
            row
            for row in audit.get("connections") or []
            if row.get("generatedMateNames")
        ]
    dof = analyze_target_mate_dof(graph, "A500")
    residual_dof = dof.get("residualDof")
    if dof.get("closed") is not True or residual_dof is None or int(residual_dof) != 0:
        raise ValueError("A500三配合束未通过静态刚体自由度预审。")
    graph["Project02A500NonAnchorExperiment"] = {
        "schemaVersion": "project02-a500-nonanchor-graph/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "targetModuleToken": "A500",
        "contextModuleTokens": ["A600"],
        "caseAnchorsRemoved": True,
        "leafPoseAnchorsRemoved": True,
        "initialPlacementMode": "deterministic",
        "dofAnalysis": dof,
        "deferredReadOnlyValidations": deferred_validations,
        "deferredValidationReason": (
            "A500/A700 50 mm spacing is a process validation and cannot be measured "
            "until A700 is present; it does not drive the A500/A600 installation."
        ),
        "sourceGraphDigest": _digest(source),
        "collisionStatus": "not_evaluated",
        "statement": (
            "A500从独立文件和确定性非原型初始位姿插入；仅允许重合13、宽度4、"
            "距离27驱动其相对A600的位置。"
        ),
    }
    return graph, dof


def main() -> int:
    parser = argparse.ArgumentParser(description="生成Project02 A500无锚点检查点执行图。")
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
    print(
        json.dumps(
            {
                "success": True,
                "source": str(source),
                "output": str(output),
                "graphDigest": _digest(graph),
                "dofAnalysis": dof,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

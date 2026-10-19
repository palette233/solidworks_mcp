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
    "demo/semantic_ports/project02_service_installations_v1/A100/"
    "top_level_installation_effective.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/semantic_ports/project02_a100_nonanchor_v1/"
    "a100-nonanchor-effective.json"
)
EXPECTED_MATES = ["重合8", "重合9", "距离9"]


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
    graph = project_target_context_graph(source, "A100")
    tokens = [str(row.get("ModuleToken") or "").upper() for row in graph.get("Modules") or []]
    if tokens != ["A600", "A100"]:
        raise ValueError(f"A100投影必须只含A600/A100，实际为：{tokens}")
    mate_names = [str(row.get("MateName") or "") for row in graph.get("Mates") or []]
    if mate_names != EXPECTED_MATES:
        raise ValueError(f"A100外部安装配合束异常：{mate_names}")

    modules = {
        str(row.get("ModuleToken") or "").upper(): row
        for row in graph.get("Modules") or []
    }
    if modules["A100"].get("SolvingStateName") != "swComponentFlexibleSolving":
        raise ValueError("A100必须保留柔性求解状态，不能把内部运动状态冻结为外部安装条件。")

    policy = graph.setdefault("EditPolicy", {})
    removed_leaf_anchors = list(policy.get("targetLeafPoseAnchors") or [])
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
        assessment = audit.setdefault("constraintAssessment", {})
        assessment["caseAnchoredModuleTokens"] = []
        assessment["fullyLocatesAddedComponent"] = True
        assessment["reason"] = (
            "The two coincident mates and one distance mate close the six external rigid-body "
            "degrees of freedom. A100 remains flexible so internal motion is not promoted to "
            "an external installation requirement."
        )
        motion = audit.setdefault("motionStatePolicy", {})
        motion["status"] = "external-installation-only-internal-motion-preserved"
        motion["topLevelInstallationMayRelease"] = True
        motion["internalProcessPoseMayRelease"] = False

    dof = analyze_target_mate_dof(graph, "A100")
    residual_dof = dof.get("residualDof")
    if dof.get("closed") is not True or residual_dof is None or int(residual_dof) != 0:
        raise ValueError("A100三配合外部安装束未通过静态刚体自由度预审。")
    graph["Project02A100NonAnchorExperiment"] = {
        "schemaVersion": "project02-a100-nonanchor-graph/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "targetModuleToken": "A100",
        "contextModuleTokens": ["A600"],
        "requiredSolvingState": "flexible",
        "caseAnchorsRemoved": True,
        "leafPoseAnchorsRemoved": True,
        "removedLeafPoseAnchorCount": len(removed_leaf_anchors),
        "initialPlacementMode": "deterministic",
        "externalInstallationDofAnalysis": dof,
        "internalMotionStatePolicy": "preserve_source_flexible_state_not_release_authority",
        "sourceGraphDigest": _digest(source),
        "collisionStatus": "not_evaluated",
        "statement": (
            "A100从独立文件和确定性非原型初始位姿插入；仅允许重合8、重合9、距离9"
            "驱动龙门根组件相对A600的位置，内部运动机构继续按柔性子装配体求解。"
        ),
    }
    return graph, dof


def main() -> int:
    parser = argparse.ArgumentParser(description="生成Project02 A100无锚点外部安装检查点执行图。")
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

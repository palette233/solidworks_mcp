from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "demo/semantic_ports/project05_p000_locator_discovery_v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_closure(
    discovery: dict[str, Any],
    free_result: dict[str, Any],
    closed_result: dict[str, Any],
    closed_assembly: Path,
) -> dict[str, Any]:
    free_tool = free_result.get("toolResult") or {}
    closed_tool = closed_result.get("toolResult") or {}
    free_gate = {
        "expectedUnderConstrained": True,
        "independentComponentInserted": _pick(free_tool, "IndependentComponentInserted") is True,
        "createdMateCount": int(_pick(free_tool, "CreatedMateCount", 0)),
        "mateParametersMatchAfterReopen": _pick(free_tool, "ReopenedMateParametersMatch") is True,
        "targetFullyConstrained": _pick(free_tool, "TargetFullyConstrained") is True,
        "passed": (
            _pick(free_tool, "IndependentComponentInserted") is True
            and int(_pick(free_tool, "CreatedMateCount", 0)) == 3
            and _pick(free_tool, "ReopenedMateParametersMatch") is True
            and _pick(free_tool, "TargetFullyConstrained") is False
        ),
    }
    closed_gate = {
        "success": closed_result.get("success") is True,
        "independentComponentInserted": _pick(closed_tool, "IndependentComponentInserted") is True,
        "createdMateCount": int(_pick(closed_tool, "CreatedMateCount", 0)),
        "mateParametersMatchAfterReopen": _pick(closed_tool, "ReopenedMateParametersMatch") is True,
        "targetFullyConstrained": _pick(closed_tool, "TargetFullyConstrained") is True,
        "targetCaseAnchored": _pick(closed_tool, "TargetCaseAnchored") is True,
        "requestedLeafPoseAnchorCount": int(
            _pick(closed_tool, "RequestedTargetLeafPoseAnchorCount", 0)
        ),
        "passed": (
            closed_result.get("success") is True
            and _pick(closed_tool, "IndependentComponentInserted") is True
            and int(_pick(closed_tool, "CreatedMateCount", 0)) == 4
            and _pick(closed_tool, "ReopenedMateParametersMatch") is True
            and _pick(closed_tool, "TargetFullyConstrained") is True
            and _pick(closed_tool, "TargetCaseAnchored") is False
            and int(_pick(closed_tool, "RequestedTargetLeafPoseAnchorCount", 0)) == 0
        ),
    }
    static_gate = {
        "freeSlotRank": discovery["sourceFreeSlotDofAnalysis"]["constraintRank"],
        "freeSlotResidualDof": discovery["sourceFreeSlotDofAnalysis"]["residualDof"],
        "closedRank": discovery["derivedDistanceDofAnalysis"]["constraintRank"],
        "closedResidualDof": discovery["derivedDistanceDofAnalysis"]["residualDof"],
        "passed": (
            discovery["sourceFreeSlotDofAnalysis"]["constraintRank"] == 5
            and discovery["sourceFreeSlotDofAnalysis"]["residualDof"] == 1
            and discovery["derivedDistanceDofAnalysis"]["constraintRank"] == 6
            and discovery["derivedDistanceDofAnalysis"]["residualDof"] == 0
        ),
    }
    success = static_gate["passed"] and free_gate["passed"] and closed_gate["passed"]
    return {
        "schemaVersion": "project05-p000-nonanchor-locator-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project05",
        "moduleToken": "P000",
        "status": "PROJECT05_P000_NONANCHOR_STATIC_CLOSED" if success else "PROJECT05_P000_BLOCKED",
        "success": success,
        "staticDofGate": static_gate,
        "sourceFreeSlotCadGate": free_gate,
        "derivedDistanceCadGate": closed_gate,
        "derivedInstallationParameter": discovery["derivedDistanceDatum"],
        "outputAssemblyPath": str(closed_assembly.resolve()),
        "outputAssemblySha256": _sha256(closed_assembly),
        "timingSeconds": {
            "freeSlotCad": float(free_result.get("durationSeconds") or 0.0),
            "derivedDistanceCad": float(closed_result.get("durationSeconds") or 0.0),
            "totalCad": float(free_result.get("durationSeconds") or 0.0)
            + float(closed_result.get("durationSeconds") or 0.0),
        },
        "collisionStatus": "not_evaluated_by_current_acceptance_policy",
        "limitations": [
            "345.122535 mm的X向安装距离来自原型真实面测量，不是厂商尺寸。",
            "原型Free槽口本身有意保留一个沿槽平移自由度。",
            "全量顶层位姿枚举因大型装配性能不足而未作为本次硬门禁。",
            "碰撞/B-rep不是当前自然语言模组自由组合主线的验收项。",
        ],
        "meaning": (
            "P000可从确定性的非原型初始位姿，仅凭三个原型关系加一个显式安装距离完成独立插入、"
            "保存、关闭和重开；不再需要完整原型Transform2或叶级姿态锚点。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总Project05 P000去锚点定位闭环。")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    closed_assembly = root / "cad/project05-p000-derived-x-distance-nonanchor-v1.SLDASM"
    closure = build_closure(
        _read(root / "project05-p000-locator-discovery.json"),
        _read(root / "cad/project05-p000-source-free-slot-nonanchor-v2.result.json"),
        _read(root / "cad/project05-p000-derived-x-distance-nonanchor-v1.result.json"),
        closed_assembly,
    )
    output = (args.output or root / "project05-p000-nonanchor-closure.json").resolve()
    output.write_text(
        json.dumps(closure, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(closure, ensure_ascii=False, indent=2))
    return 0 if closure["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

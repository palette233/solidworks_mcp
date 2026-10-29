#!/usr/bin/env python3
"""Finalize the Project05 P000 -> Project02 A600 datum-placement demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps/demo-backend/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_backend.cross_project_wastecup_datum_closure import (  # noqa: E402
    close_project05_p000_to_project02_a600_datum_demo,
)


DEFAULT_ROOT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _markdown(value: dict) -> str:
    timing = value["timingSeconds"]
    support_demo = value.get("mode") == "support_position_demo"
    base_token = value.get("targetBaseToken", "A600")
    extra = []
    if support_demo:
        parameters = value["positionParametersMeters"]
        extra = [
            "## 支承面＋位置参数 Demo（本轮边界）", "",
            f"- 支承面重合；纵向距离 {parameters['longitudinal']*1000:g} mm，横向距离 {parameters['lateral']*1000:g} mm。",
            "- 距离是所选语义基准面之间的显式设计参数，不是孔距或厂商安装尺寸。",
            f"- 重开只读核查：仅{base_token}固定，P000未固定，三条指定配合均未压缩且无错误。",
            "- 孔位匹配不是本Demo硬性条件；**实际固定方式暂未验证**。",
            "- 本轮P000 SourceTransform已改为identity占位；旧ExternalPlacementEquivalencePassed=false表示与占位变换不相等，不是定位验证失败。",
            "- 验收的是支承面、两个显式距离、真实激活配合、目标完全约束和保存重开，不是复刻原型坐标。", "",
            "## CAD分阶段耗时", "",
            *[f"- `{name}`：{seconds:.3f} s" for name, seconds in timing["phases"].items()], "",
        ]
    return "\n".join(
        [
            f"# Project05 P000 → {value.get('targetProjectId', 'project02')} {base_token} 跨项目基准定位闭环",
            "",
            f"- 状态：`{value['status']}`",
            "- 结论：非原型初始位姿、无顶层位姿锚点、无叶级锚点，3/3真实配合创建成功。",
            "- 保存重开：通过；目标组件完全约束；配合求解干净。",
            f"- CAD墙钟耗时：{timing['wallClock']:.3f} s",
            f"- CAD工具内部耗时：{timing['cadToolInternal']:.3f} s",
            f"- 输出装配体：`{value['outputAssemblyPath']}`",
            "- 碰撞/B-rep：未评估（当前主线独立后验项）。",
            "",
            *extra,
            "## 能力边界",
            "",
            "- 已证明：WasteCup角色可通过三个正交语义基准面完成跨项目基准定位。",
            "- 未证明：孔系、紧固件、实体转接件或直接机械互换兼容。",
            "- P000面恢复使用BodyFaceIndex回退，源拓扑改变后需要重新登记或复验。",
            "- 因此该结果可作为第三类跨项目基准定位Demo，不能计入直接机械替换角色。",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    summary_path = root / "build-summary.json"
    summary = _read(summary_path) if summary_path.is_file() else {}
    assembly = Path(summary.get("outputAssemblyPath") or root / "project02-A600-project05-P000-datum-v1.SLDASM").resolve()
    if assembly.parent != root:
        raise ValueError("汇总输出装配体必须位于指定run目录内。")
    state_path = root / "read-only-state-verification.json"
    audit = _read(root / "candidate_audit.json")
    base_token = audit.get("targetBaseToken", "A600")
    value = close_project05_p000_to_project02_a600_datum_demo(
        candidate_audit=audit,
        cad_result=_read(assembly.with_suffix(".context-insert.result.json")),
        effective_graph_path=root / "candidate_effective_mate_graph.json",
        output_assembly_path=assembly,
        read_only_state=_read(state_path) if state_path.is_file() else None,
        expected_context_module_tokens=(base_token,),
        target_base_token=base_token,
        target_project_id=audit.get("targetProjectId", "project02"),
    )
    json_path = root / "datum-placement-demo-closure.json"
    markdown_path = root / "datum-placement-demo-closure-CN.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError("拒绝覆盖已有CAD闭环报告。")
    json_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(value), encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

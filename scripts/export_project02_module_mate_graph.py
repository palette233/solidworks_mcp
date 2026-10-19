#!/usr/bin/env python3
"""Export Project 02's read-only module-level mate graph and a reviewable summary."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)
DEFAULT_SOURCE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目02\01-项目3D图纸\FL9A24D062A000.001\FL9A24D062A000.001.SLDASM"
)
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_module_mate_graph_v4_semantics.json"
DEFAULT_TOKENS = ["A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--tokens", nargs="+", default=DEFAULT_TOKENS)
    parser.add_argument("--project-label", default="项目02")
    parser.add_argument(
        "--from-json",
        action="store_true",
        help="Regenerate only the Markdown summary from an existing --output JSON without opening SolidWorks.",
    )
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument("--force-new-instance", action="store_true")
    parser.add_argument("--timeout", type=float, default=1200.0)
    parser.add_argument(
        "--close-source-after-export",
        action="store_true",
        help="Close the exported source assembly after the graph is durable, preserving other open documents.",
    )
    return parser.parse_args()


def pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def mermaid_id(value: str) -> str:
    return "M_" + re.sub(r"[^A-Za-z0-9_]", "_", value)


def make_summary(graph: dict[str, Any], project_label: str = "项目02") -> str:
    modules = pick(graph, "Modules", []) or []
    bundles = pick(graph, "MateBundles", []) or []
    diagnostics = pick(graph, "Diagnostics", []) or []
    lines = [
        f"# {project_label}模组级配合图审计",
        "",
        f"- Schema：`{pick(graph, 'SchemaVersion', '')}`",
        f"- 原型：`{pick(graph, 'SourceAssemblyPath', '')}`",
        f"- 已识别模组实例：{pick(graph, 'ModuleCount', len(modules))}",
        f"- 跨模组配合：{pick(graph, 'InterModuleMateCount', 0)}",
        f"- 配合束：{pick(graph, 'MateBundleCount', len(bundles))}",
        f"- 忽略的模组内部配合：{pick(graph, 'IgnoredIntraModuleMateCount', 0)}",
        f"- 未解析/多端模组配合：{pick(graph, 'IgnoredUnresolvedMateCount', 0)}",
        "",
        "> 本图表达原型中的无向设计关系，不直接等价于机械装配顺序。",
        "",
        "## 模组关系图",
        "",
        "```mermaid",
        "graph LR",
    ]
    for module in modules:
        token = str(pick(module, "ModuleToken", "UNKNOWN"))
        name = str(pick(module, "Name", token)).replace('"', "'")
        hierarchy = str(pick(module, "HierarchyPath", name))
        lines.append(f'  {mermaid_id(hierarchy)}["{token}<br/>{name}"]')
    for bundle in bundles:
        first = str(pick(bundle, "FirstModuleToken", "UNKNOWN"))
        second = str(pick(bundle, "SecondModuleToken", "UNKNOWN"))
        first_path = str(pick(bundle, "FirstModuleHierarchyPath", first))
        second_path = str(pick(bundle, "SecondModuleHierarchyPath", second))
        count = int(pick(bundle, "MateCount", 0))
        types = ", ".join(pick(bundle, "MateTypes", []) or [])
        label = f"{first}–{second}: {count}条 | {types}".replace('"', "'")
        lines.append(f'  {mermaid_id(first_path)} ---|"{label}"| {mermaid_id(second_path)}')
    lines.extend(["```", "", "## 配合束明细", ""])
    lines.append("| 模组对 | 配合数 | 可重建基础面配合 | 类型 | 初步判断 |")
    lines.append("|---|---:|---:|---|---|")
    for bundle in bundles:
        pair = f"{pick(bundle, 'FirstModuleToken', '')}–{pick(bundle, 'SecondModuleToken', '')}"
        types = ", ".join(pick(bundle, "MateTypes", []) or [])
        lines.append(
            f"| {pair} | {pick(bundle, 'MateCount', 0)} | "
            f"{pick(bundle, 'BasicTwoFaceRebuildableMateCount', 0)} | {types} | "
            f"`{pick(bundle, 'InstallationRelationAssessment', '')}` |"
        )
    lines.extend(["", "## 诊断", ""])
    lines.extend(f"- {message}" for message in diagnostics)
    lines.extend(
        [
            "",
            "## 人工复核重点",
            "",
            "1. A600–A800是否存在完整的位置与方向配合束；",
            "2. A180是否通过直接或中间安装件与A600/A800建立关系；",
            "3. A500、A700、A300位于操作面侧或对侧的关系能否从图中观察；",
            "4. A100与A800及功能模组的关系是直接装配关系，还是仅由最终位姿体现；",
            "5. 配合图中缺失的扫描视场、工作位、服务点和点胶行程仍需语义标注。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    source = args.source.resolve()
    output = args.output.resolve()
    summary = (args.summary or output.with_suffix(".summary.md")).resolve()
    if args.from_json:
        graph = json.loads(output.read_text(encoding="utf-8"))
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(make_summary(graph, args.project_label), encoding="utf-8")
        print(json.dumps({"success": True, "graph": str(output), "summary": str(summary), "mode": "from-json"}, ensure_ascii=False))
        return 0
    if not exe.exists():
        raise FileNotFoundError(f"MCP executable not found: {exe}")
    if not source.exists():
        raise FileNotFoundError(f"Source assembly not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    with McpClient(
        exe,
        client_name="Project02ModuleMateGraphAudit",
        request_timeout=args.timeout,
        framing="newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "export_module_mate_graph" not in tools:
            raise RuntimeError("Published MCP build is missing export_module_mate_graph")
        graph = client.call_tool(
            "ExportModuleMateGraph",
            {
                "sourceAssemblyPath": str(source),
                "moduleTokens": args.tokens,
                "outputPath": str(output),
                "saveJson": True,
            },
        )
        close_warning = None
        if args.close_source_after_export:
            try:
                client.call_tool_text("close_document", {"path": str(source)})
            except RuntimeError as exc:
                close_warning = str(exc)

    # The tool owns the canonical JSON. The script adds a human-reviewable Mermaid summary.
    summary.write_text(make_summary(graph, args.project_label), encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "graph": str(output),
                "summary": str(summary),
                "moduleCount": pick(graph, "ModuleCount", 0),
                "interModuleMateCount": pick(graph, "InterModuleMateCount", 0),
                "mateBundleCount": pick(graph, "MateBundleCount", 0),
                "closeWarning": close_warning,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run Project 02 module-mate reconstruction experiments A, B, and C in order."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
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
DEFAULT_DIR = ROOT / "demo/mate_reconstruction_experiments"
TOKENS = ["A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--phase", choices=["A", "B", "C", "all"], default="all")
    parser.add_argument("--b-result", type=Path)
    parser.add_argument("--residual-anchors", nargs="*")
    parser.add_argument(
        "--output-tag",
        default="v6",
        help="Unique filename suffix; use a new tag for every CAD run to avoid SolidWorks title collisions.",
    )
    parser.add_argument("--timeout", type=float, default=3600.0)
    return parser.parse_args()


def pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def phase_paths(output_dir: Path, phase: str, output_tag: str = "v6") -> tuple[Path, Path]:
    safe_tag = "".join(character for character in output_tag if character.isalnum() or character in "-_")
    if not safe_tag:
        raise ValueError("--output-tag must contain at least one filename-safe character")
    names = {
        "A": f"project02_mate_reconstruction_A_source_pose_{safe_tag}",
        "B": f"project02_mate_reconstruction_B_mate_only_{safe_tag}",
        "C": f"project02_mate_reconstruction_C_residual_anchors_{safe_tag}",
    }
    stem = output_dir / names[phase]
    return stem.with_suffix(".SLDASM"), stem.with_suffix(".result.json")


def derive_residual_anchors(b_result: dict[str, Any]) -> list[str]:
    anchors: list[str] = []
    base_token = str(pick(b_result, "BaseModuleToken", "A600"))
    for component in pick(b_result, "ComponentResults", []) or []:
        token = str(pick(component, "ModuleToken", ""))
        hierarchy = str(pick(component, "SourceHierarchyPath", ""))
        constrained = str(pick(component, "ConstrainedStatusName", ""))
        matches = bool(pick(component, "MatchesSourcePose", False))
        if token.casefold() == base_token.casefold():
            continue
        if constrained != "swFullyConstrained" or not matches:
            anchors.append(hierarchy or token)
    return list(dict.fromkeys(anchors))


def run_phase(
    client: McpClient,
    source: Path,
    output_dir: Path,
    phase: str,
    residual_anchors: list[str] | None = None,
    output_tag: str = "v6",
) -> dict[str, Any]:
    output, result_path = phase_paths(output_dir, phase, output_tag)
    if output.exists() or result_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite experiment {phase}; remove or choose a new --output-dir: {output}"
        )
    mode = {"A": "source_pose", "B": "mate_only", "C": "residual_anchors"}[phase]
    print(
        json.dumps(
            {
                "event": "phase-start",
                "phase": phase,
                "mode": mode,
                "output": str(output),
                "residualAnchors": residual_anchors or [],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    result = client.call_tool(
        "RunModuleMateReconstructionExperiment",
        {
            "sourceAssemblyPath": str(source),
            "outputAssemblyPath": str(output),
            "mode": mode,
            "baseModuleToken": "A600",
            "moduleTokens": TOKENS,
            "residualAnchorModuleSelectors": residual_anchors or [],
            "poseToleranceMeters": 1e-5,
            "rotationTolerance": 1e-6,
        },
    )
    result["RunTiming"] = {
        "startedAtUtc": started_at,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": round(time.perf_counter() - started, 6),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "event": "phase-finish",
                "phase": phase,
                "success": pick(result, "Success", False),
                "createdMates": pick(result, "CreatedMateCount", 0),
                "sourceMates": pick(result, "SourceMateCount", 0),
                "poseMatches": pick(result, "PoseMatchCount", 0),
                "sourceModules": pick(result, "SourceModuleCount", 0),
                "result": str(result_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return result


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    if not exe.exists():
        raise FileNotFoundError(f"MCP executable not found: {exe}")
    if not source.exists():
        raise FileNotFoundError(f"Source assembly not found: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)

    phases = ["A", "B", "C"] if args.phase == "all" else [args.phase]
    with McpClient(
        exe,
        client_name="Project02MateReconstructionABC",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "run_module_mate_reconstruction_experiment" not in tools:
            raise RuntimeError("Published MCP build is missing run_module_mate_reconstruction_experiment")

        b_result: dict[str, Any] | None = None
        for phase in phases:
            anchors: list[str] | None = None
            if phase == "C":
                if args.residual_anchors is not None:
                    anchors = list(args.residual_anchors)
                elif b_result is not None:
                    anchors = derive_residual_anchors(b_result)
                else:
                    b_path = (args.b_result or phase_paths(output_dir, "B", args.output_tag)[1]).resolve()
                    if not b_path.exists():
                        raise FileNotFoundError(
                            "Experiment C requires --residual-anchors or an existing B result."
                        )
                    anchors = derive_residual_anchors(json.loads(b_path.read_text(encoding="utf-8")))
            result = run_phase(client, source, output_dir, phase, anchors, args.output_tag)
            if phase == "B":
                b_result = result

    summary = {
        "source": str(source),
        "outputDir": str(output_dir),
        "phases": phases,
        "outputTag": args.output_tag,
        "results": {phase: str(phase_paths(output_dir, phase, args.output_tag)[1]) for phase in phases},
    }
    summary_path = output_dir / "project02_mate_reconstruction_ABC_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"event": "all-finish", "summary": str(summary_path)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

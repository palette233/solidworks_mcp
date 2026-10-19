#!/usr/bin/env python3
"""Export non-destructive internal isometric review images for B/C assemblies."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_assembly_entity_annotations import McpClient  # noqa: E402

BACKEND_SRC = ROOT / "apps/demo-backend/src"
sys.path.insert(0, str(BACKEND_SRC))
from demo_backend.pipeline_timing import PipelineTiming, utc_now_iso  # noqa: E402


def main() -> int:
    timer = PipelineTiming("project02.dependency-ablation-internal-review-views")
    mcp = ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    variants = {
        "B": ROOT / "demo/FL9A24D062A000_dependency_B_rank1_direct_20260908.SLDASM",
        "C": ROOT / "demo/FL9A24D062A000_dependency_C_rank1_direct_20260908.SLDASM",
    }
    results: list[dict[str, Any]] = []
    with McpClient(
        mcp,
        client_name="CodexProject02AblationInternalViews",
        request_timeout=180,
        framing="newline",
        direct_stdio=True,
    ) as client:
        client.call_tool("solid_works_connect", {})
        for variant, assembly in variants.items():
            started_at = utc_now_iso()
            started = time.perf_counter()
            output = ROOT / f"demo/project02_dependency_{variant}_rank1_internal_isometric_20260908.png"
            client.call_tool("open_document", {"path": str(assembly)})
            components = client.call_tool("list_components", {})
            names = [str(item.get("Name") or "") for item in components]
            keep = [name for name in names if "D062A600" not in name]
            if len(names) != 9 or len(keep) != 8:
                raise RuntimeError(f"Unexpected top-level component set for variant {variant}")
            try:
                client.call_tool(
                    "hide_top_level_components_except",
                    {"keepComponentNames": keep, "rebuild": False},
                )
                client.call_tool_text("show_standard_view", {"view": "isometric"})
                client.call_tool(
                    "export_current_view_png",
                    {
                        "outputPath": str(output),
                        "width": 1600,
                        "height": 900,
                        "includeBase64Data": False,
                        "fitToView": True,
                    },
                )
            finally:
                client.call_tool(
                    "hide_top_level_components_except",
                    {"keepComponentNames": names, "rebuild": False},
                )
            results.append(
                {
                    "variant": variant,
                    "assemblyPath": str(assembly),
                    "outputPath": str(output),
                    "topLevelComponentCount": len(names),
                    "hiddenForReview": "A600",
                    "savedAssemblyModified": False,
                    "startedAtUtc": started_at,
                    "finishedAtUtc": utc_now_iso(),
                    "durationSeconds": round(time.perf_counter() - started, 6),
                }
            )
    timing = timer.finish()
    payload = {
        "success": all(Path(item["outputPath"]).is_file() for item in results),
        "results": results,
        "timing": timing,
    }
    output_path = (
        ROOT
        / "demo/layout_previews/project02_dependency_ablation/cad/internal_review_views_result.json"
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

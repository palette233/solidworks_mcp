#!/usr/bin/env python3
"""Build the complete non-anchored Project03 AB00 installation candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project03_ab00_port_completion import (  # noqa: E402
    build_project03_ab00_complete_port_candidate,
)


DEFAULT_GRAPH = WORKSPACE / "demo/layout_previews/project03_module_mate_graph.json"
DEFAULT_PROTOTYPE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目03\01-项目3D图纸\FL9A24D063A000.001-0415\FL9A24D063A000.001.SLDASM"
)
DEFAULT_OUTPUT = WORKSPACE / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--prototype", type=Path, default=DEFAULT_PROTOTYPE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    started = perf_counter()
    packet = build_project03_ab00_complete_port_candidate(
        _read(args.graph.resolve()), args.prototype.resolve()
    )
    output = args.output.resolve()
    names = {
        "pathAudit": "path_recovery_audit.json",
        "endpointCatalog": "face_endpoint_catalog.json",
        "semanticCatalog": "semantic_port_catalog.json",
        "baseGraph": "base_context_graph.json",
        "request": "assembly_plan_request.json",
        "patch": "assembly_plan_patch.json",
        "effectiveGraph": "assembly_plan_effective.json",
        "summary": "work_packet_summary.json",
    }
    for key, name in names.items():
        _write(output / name, packet[key])
    summary = dict(packet["summary"])
    summary["buildDurationSeconds"] = round(perf_counter() - started, 6)
    summary["outputDirectory"] = str(output)
    _write(output / "build_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

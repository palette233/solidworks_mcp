#!/usr/bin/env python3
"""Finalize the Project03 AB00 port after bounded real-CAD validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project03_ab00_port_completion import (  # noqa: E402
    finalize_project03_ab00_complete_port,
)


DEFAULT_ROOT = WORKSPACE / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    semantic_path = root / "semantic_port_catalog.json"
    summary_path = root / "work_packet_summary.json"
    result_path = root / "cad/project03_AB00_complete_nonanchor_v1.result.json"
    effective_path = root / "assembly_plan_effective.json"
    semantic, summary, validation = finalize_project03_ab00_complete_port(
        _read(semantic_path),
        _read(summary_path),
        _read(result_path),
        effective_graph_path=str(effective_path.relative_to(WORKSPACE)).replace("\\", "/"),
        validation_evidence_path=str(result_path.relative_to(WORKSPACE)).replace("\\", "/"),
    )
    _write(semantic_path, semantic)
    _write(summary_path, summary)
    _write(root / "live_validation_summary.json", validation)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.mate_reconstruction_pipeline import analyze_project02_top_level_dof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--rebuild-result", required=True, type=Path)
    parser.add_argument("--prior-mate-only-result", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite DOF report: {output}")
    result = analyze_project02_top_level_dof(
        json.loads(args.graph.resolve().read_text(encoding="utf-8-sig")),
        json.loads(args.rebuild_result.resolve().read_text(encoding="utf-8-sig")),
        json.loads(args.prior_mate_only_result.resolve().read_text(encoding="utf-8-sig"))
        if args.prior_mate_only_result else None,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": result["success"], "status": result["status"], "totalDof": result["totalResidualTopLevelRigidPoseDof"], "output": str(output)}, ensure_ascii=False))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

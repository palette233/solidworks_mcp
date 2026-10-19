from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.multi_project_assembly_pipeline_audit import audit_multi_project_assembly_pipeline


def main() -> int:
    result = audit_multi_project_assembly_pipeline(ROOT)
    output = ROOT / "demo/layout_previews/multi_project_assembly_pipeline_audit.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

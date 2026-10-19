from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.assembly_release_contract import build_assembly_release_contract
from demo_backend.project_assembly_profile import ProjectAssemblyProfileError


PROJECT_IDS = ("project01", "project02", "project03", "project05", "project06")


def main() -> int:
    rows: list[dict] = []
    for project_id in PROJECT_IDS:
        try:
            rows.append(build_assembly_release_contract(ROOT, project_id))
        except (ProjectAssemblyProfileError, OSError, ValueError, TypeError) as exc:
            rows.append(
                {
                    "projectId": project_id,
                    "available": False,
                    "error": str(exc),
                    "release": {
                        "staticDemoAllowed": False,
                        "liveCadAllowed": False,
                        "productionAllowed": False,
                    },
                }
            )

    payload = {
        "schemaVersion": "multi-project-assembly-release-contract/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projects": rows,
        "summary": {
            "projectCount": len(rows),
            "staticDemoAllowedProjects": [
                row["projectId"]
                for row in rows
                if row["release"]["staticDemoAllowed"]
            ],
            "liveCadAllowedProjects": [
                row["projectId"]
                for row in rows
                if row["release"]["liveCadAllowed"]
            ],
            "productionAllowedProjects": [
                row["projectId"]
                for row in rows
                if row["release"]["productionAllowed"]
            ],
        },
    }
    output = ROOT / "demo/layout_previews/multi_project_assembly_release_contract_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

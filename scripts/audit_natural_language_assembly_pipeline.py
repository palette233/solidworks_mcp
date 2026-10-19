from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.assembly_pipeline_audit import audit_project02_assembly_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the Project02 natural-language-to-CAD assembly pipeline."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project02_full_machine_increment_v1/"
        "natural_language_pipeline_audit.json",
    )
    args = parser.parse_args()
    result = audit_project02_assembly_pipeline(ROOT)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["readyForValidatedArtifactReplay"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

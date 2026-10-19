from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_manifest_orchestrator import build_manifest_job_plan  # noqa: E402
from demo_backend.global_manifest_seed_import import (  # noqa: E402
    build_external_manifest_seed_evidence,
)


def _load(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind a signed historical checkpoint as a manifest suffix seed."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--start-order", type=int, required=True)
    parser.add_argument("--packet-limit", type=int)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--historical-import", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = build_manifest_job_plan(
        ROOT,
        args.manifest.resolve(),
        start_order=args.start_order,
        packet_limit=args.packet_limit,
    )
    evidence = build_external_manifest_seed_evidence(
        plan=plan,
        context=_load(args.context),
        catalog=_load(args.catalog),
        historical_import=_load(args.historical_import),
        historical_import_path=args.historical_import,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "ready",
                "output": str(output),
                "packetId": evidence["packetId"],
                "assembly": evidence["outputAssemblyPath"],
                "evidenceDigest": evidence["evidenceDigest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project05_complete_cumulative_chain import (  # noqa: E402
    DEFAULT_RELEASE_ID,
    audit_complete_chain_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Project05 complete chain for source-pose and anchor shortcuts."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/project05-complete-seven-addon-v2.cad-transaction-manifest.json",
    )
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = (ROOT / manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    report = audit_complete_chain_manifest(
        ROOT,
        manifest,
        expected_release_id=args.release_id,
    )
    output = args.output or manifest_path.with_name(
        manifest_path.name.replace(".cad-transaction-manifest.json", ".preflight-audit.json")
    )
    if not output.is_absolute():
        output = (ROOT / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({**report, "outputPath": str(output)}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

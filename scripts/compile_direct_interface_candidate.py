"""Thin JSON entry point for the existing direct-interface CAD compiler.

This command only writes a validation candidate; it neither runs CAD nor
authorizes a release. Source files and endpoint catalogs are explicit inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.direct_interface_validation import compile_direct_interface_validation_package
from demo_backend.direct_interface_relation_release import load_materialized_direct_interface_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8-sig"))
    request = read(args.request)
    if request.get("schemaVersion") != "direct-interface-candidate-request/v1":
        raise ValueError("unsupported direct interface request schema")
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    kwargs = dict(request["compilerInputs"])
    for key in ("contract_catalog", "module_face_catalog", "slot_face_catalog"):
        kwargs[key] = read(kwargs[key])
    package = compile_direct_interface_validation_package(**kwargs)
    output.mkdir(parents=True)
    artifacts = {}
    for key, filename in (("effectiveMateGraph", "effective-mate-graph.json"),
                          ("selectedEndpointCatalog", "selected-face-endpoint-catalog.json")):
        path = output / filename
        path.write_text(json.dumps(package.pop(key), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifacts["effectiveGraph" if key == "effectiveMateGraph" else key] = {
            "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    package["artifacts"] = artifacts
    timing = {"startedAtUtc": started_at,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": time.perf_counter() - started}
    (output / "validation-package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_materialized_direct_interface_package(output)
    (output / "compilation-report.json").write_text(
        json.dumps({"timing": timing, "cadExecuted": False}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outputDir": str(output), "status": package["status"],
        "timing": timing}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

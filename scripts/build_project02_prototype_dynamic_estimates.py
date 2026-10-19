#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project02_prototype_dynamic_estimates import build_estimate


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    request_path = ROOT / "demo/FL9A24D062A000_real_process_request.json"
    envelope_path = ROOT / "demo/layout_previews/project02_prototype_A700_leaf_envelopes.json"
    closure_path = ROOT / "demo/semantic_ports/project02_full_machine_increment_v1/project02_full_machine_closure.json"
    service_path = ROOT / "demo/layout_previews/project02_service_access_audit.json"
    reach_path = ROOT / "demo/layout_previews/project02_dual_valve_reach_audit.json"
    envelope = load(envelope_path)
    capture = next(
        row
        for row in envelope.get("captures") or []
        if "A700" in str((row.get("TopLevelComponent") or {}).get("Name") or "")
    )
    closure = load(closure_path)
    service = load(service_path)
    reach = load(reach_path)
    result = build_estimate(
        load(request_path),
        capture,
        static_closure_passed=bool(
            (closure.get("releaseDecision") or {}).get("staticTenObjectDemoReleaseAllowed")
            or (closure.get("summary") or {}).get("allPairsAccepted")
        ),
        service_access_passed=service.get("success") is True,
        reach_audit_passed=reach.get("success") is True,
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result["sources"] = {
        "request": str(request_path),
        "a700LeafBodies": str(envelope_path),
        "staticClosure": str(closure_path),
        "serviceAccessAudit": str(service_path),
        "reachAudit": str(reach_path),
    }
    output = ROOT / "demo/semantic_ports/project02_full_machine_increment_v1/prototype_dynamic_estimates.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **result["gate"]}, ensure_ascii=False))
    return 0 if result["gate"]["prototypeEstimatedDynamicDemoPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

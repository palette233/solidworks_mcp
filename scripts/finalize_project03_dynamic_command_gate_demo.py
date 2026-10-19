from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from demo_backend.ordered_assembly_planner import preview_ordered_assembly


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "demo/semantic_ports/project03_dynamic_command_gate_demo_v1.json"
)
BASE = (
    "项目03：先添加AE00，再添加AD00，然后添加AI00，接着添加AG00，"
    "再添加AH00，然后添加AJ00，最后添加AB00"
)


def main() -> int:
    cases = [
        ("static-assembly", BASE + "。"),
        ("verified-discrete-15", BASE + "，并验证AD20在15度静态状态。"),
        ("rejected-discrete-16", BASE + "，并验证AD20在16度静态状态。"),
        ("rejected-discrete-20", BASE + "，并验证AD20在20度静态状态。"),
        ("rejected-continuous-0-to-15", BASE + "，并将AD20从0度翻转到15度。"),
    ]
    rows = []
    started = perf_counter()
    for case_id, command in cases:
        case_started = perf_counter()
        preview = preview_ordered_assembly("project03", command)
        plan = preview["plan"]
        rows.append(
            {
                "caseId": case_id,
                "command": command,
                "orderValid": plan["summary"]["orderValid"],
                "safeToStartCad": plan["executionBoundary"]["safeToStartCad"],
                "executionReason": plan["executionBoundary"]["reason"],
                "dynamicProcessGate": plan.get("dynamicProcessGate"),
                "planDigest": plan.get("planDigest"),
                "durationSeconds": round(perf_counter() - case_started, 6),
            }
        )
    expected = {
        "static-assembly": True,
        "verified-discrete-15": True,
        "rejected-discrete-16": False,
        "rejected-discrete-20": False,
        "rejected-continuous-0-to-15": False,
    }
    passed = all(row["safeToStartCad"] is expected[row["caseId"]] for row in rows)
    payload = {
        "schemaVersion": "project03-dynamic-command-gate-demo/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project03",
        "success": passed,
        "status": (
            "PASSED_PROJECT03_DYNAMIC_COMMAND_PREFLIGHT_GATE"
            if passed
            else "FAILED_PROJECT03_DYNAMIC_COMMAND_PREFLIGHT_GATE"
        ),
        "cadExecuted": False,
        "caseCount": len(rows),
        "cases": rows,
        "durationSeconds": round(perf_counter() - started, 6),
        "limitations": [
            "15度只放行已验证离散静态姿态，不放行0到15度连续运动。",
            "动态闭包的运动增量来自原型配置推断，尚非厂商权威参数。",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTEXTS = ROOT / "demo/global_assembly_contexts"
OUTPUT = CONTEXTS / "project05-release-order-compatibility-v1/report.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _job(job_id: str) -> dict:
    return _read(CONTEXTS / "manifest_jobs" / job_id / "job.json")


def _tokens(job: dict) -> list[str]:
    return [str(step.get("moduleToken") or "") for step in job.get("steps") or []]


def main() -> int:
    released = _read(
        CONTEXTS
        / "project05-a000-d000-release-bound-compat-v2.natural-language-compilation.json"
    )
    order_a = _read(
        CONTEXTS / "project05-nonfixed-order-a-v1.natural-language-compilation.json"
    )
    order_b = _read(
        CONTEXTS / "project05-nonfixed-order-b-v1.natural-language-compilation.json"
    )
    released_job = _job(str(released.get("jobId") or ""))
    order_a_job = _job(str(order_a.get("jobId") or ""))
    order_b_job = _job(str(order_b.get("jobId") or ""))
    tokens_a = _tokens(order_a_job)
    tokens_b = _tokens(order_b_job)
    checks = {
        "releasedCompilationSucceeded": released.get("success") is True,
        "releasedAuthorityVerified": (
            (released_job.get("plan") or {}).get("releaseAuthority") or {}
        ).get("status")
        == "verified",
        "releasedCommandAuditComplete": (
            (released_job.get("plan") or {}).get("commandAudit") or {}
        ).get("status")
        == "complete",
        "releasedPacketIsD000": _tokens(released_job) == ["D000"],
        "orderACompiled": order_a.get("success") is True,
        "orderBCompiled": order_b.get("success") is True,
        "bothOrdersHaveFourPackets": len(tokens_a) == len(tokens_b) == 4,
        "ordersAreDifferent": tokens_a != tokens_b,
        "orderAExact": tokens_a == ["M000", "F000", "P000", "G000"],
        "orderBExact": tokens_b == ["G000", "P000", "F000", "M000"],
        "noCadStarted": all(
            report.get("cadStarted") is False
            for report in (released, order_a, order_b)
        ),
    }
    report = {
        "schemaVersion": "project05-release-order-compatibility/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "releaseBoundCase": {
            "contextId": released.get("contextId"),
            "jobId": released.get("jobId"),
            "moduleOrder": _tokens(released_job),
            "releaseManifestPath": released.get("releaseManifestPath"),
        },
        "nonFixedOrderCases": [
            {
                "contextId": order_a.get("contextId"),
                "jobId": order_a.get("jobId"),
                "moduleOrder": tokens_a,
                "releaseBound": False,
            },
            {
                "contextId": order_b.get("contextId"),
                "jobId": order_b.get("jobId"),
                "moduleOrder": tokens_b,
                "releaseBound": False,
            },
        ],
        "releasedPermutationCoverage": (
            "not_demonstrated_because_project05_has_only_one_independently_"
            "authorized_addon_template"
        ),
        "cadStarted": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "Project05发布绑定A000→D000编译通过；同一项目的四个未发布附加模组"
            "可按两种顺序生成语义任务，但不得据此宣称它们已获得发布级CAD执行授权。"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

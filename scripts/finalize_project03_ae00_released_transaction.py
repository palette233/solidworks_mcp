from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import (  # noqa: E402
    assess_driving_insert_evidence,
)


RUN = ROOT / "demo/global_assembly_contexts/project03-aa00-ae00-v11-driving-v1"
TEMPLATE_ID = "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def main() -> int:
    compile_report_path = RUN / "report.json"
    envelope_path = RUN / "cad-run-packet-001/execution-envelope.json"
    cad_result_path = RUN / "cad-run-packet-001/cad-result.json"
    compile_report = _read(compile_report_path)
    envelope = _read(envelope_path)
    cad_result = _read(cad_result_path)
    assessment = assess_driving_insert_evidence(
        cad_result,
        expected_mate_count=3,
    )
    release_authority = envelope.get("releaseAuthority") or {}
    checks = {
        "naturalLanguageTransactionCompiled": (
            compile_report.get("status") == "ready_for_generic_cad_executor"
        ),
        "commandAuditComplete": (
            compile_report.get("commandAuditStatus") == "complete"
        ),
        "genericPacketExecutionPassed": envelope.get("success") is True,
        "releaseAuthorityVerified": release_authority.get("status") == "verified",
        "onlyAuthorizedAe00TemplateUsed": (
            release_authority.get("usedDrivingTemplateIds") == [TEMPLATE_ID]
        ),
        "sourceAssemblyUnchanged": envelope.get("sourceAssemblyUnchanged") is True,
        "checkpointCadEvidencePassed": assessment.get("checkpointPassed") is True,
        "outputAssemblySaved": Path(
            str(envelope.get("outputAssemblyPath") or "")
        ).is_file(),
    }
    status = "passed" if all(checks.values()) else "blocked"
    report = {
        "schemaVersion": "project03-released-generic-cad-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "releaseId": compile_report.get("releaseId"),
        "checks": checks,
        "naturalLanguageCommands": compile_report.get("naturalLanguageCommands"),
        "selectedTemplateId": TEMPLATE_ID,
        "cadAssessment": assessment,
        "outputAssemblyPath": envelope.get("outputAssemblyPath"),
        "cadDurationSeconds": cad_result.get("durationSeconds"),
        "phaseDurationsSeconds": (cad_result.get("toolResult") or {}).get(
            "PhaseDurationsSeconds"
        ),
        "collisionStatus": "not_evaluated",
        "evidence": {
            "compileReportPath": str(compile_report_path),
            "executionEnvelopePath": str(envelope_path),
            "cadResultPath": str(cad_result_path),
        },
        "statement": (
            "Project03的自然语言命令、受控关系发布、项目无关数据包执行、"
            "非原型初始位姿插入以及保存重开复核已形成闭环。"
        ),
    }
    output = RUN / "closure-report.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
